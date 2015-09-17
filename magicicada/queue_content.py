# queue_content.py
#
# Author: Facundo Batista <facundo@taniquetil.com.ar>
#
# Copyright 2010-2011 Chicharreros
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The structure for the operations in the queue."""

import collections
import logging
import time
import os

# kind of node in the tree structure
KIND_UNKNOWN, KIND_FILE, KIND_DIR = "Unknown File Dir".split()

# type of roots (so far, only home)
ROOT_HOME = ""  # this string will appear next to the home icon in the GUI

# action that happened with the operation
ACTION_ADDED, ACTION_REMOVED = "Added Removed".split()

# operations that are for node
OP_MOVE, OP_MAKEDIR, OP_MAKEFILE, OP_UNLINK, OP_UPLOAD, OP_DOWNLOAD = \
    "Move MakeDir MakeFile Unlink Upload Download".split()
NODE_OPS = OP_MOVE, OP_MAKEDIR, OP_MAKEFILE, OP_UNLINK, OP_UPLOAD, OP_DOWNLOAD
DONE = '__done__'

# where the path lives in the operation data
PATH_DEFAULT = 'path'
PATH_SPECIALS = {OP_MOVE: 'path_from'}

# type of operations
NODE_OP, INTERNAL_OP = "Node Internal".split()

# log!
logger = logging.getLogger('magicicada.queue_content')


class Node(object):
    """A node in the tree structure."""

    def __init__(self, name, parent, kind, last_modified=None,
                 operations=None, done=None):
        self.kind = kind
        self.last_modified = last_modified
        self.operations = [] if operations is None else operations
        self.done = done
        self.children = {}
        self.parent = parent
        self.name = name

    def __str__(self):
        return ("<Node %(name)s %(kind)r last_modified=%(last_modified)s "
                "done=%(done)s operations=%(operations)s "
                "children=%(children)s>" % self.__dict__)
    __repr__ = __str__


# pylint: disable=C0103
# it's camel case because it mimics a class
Internal = collections.namedtuple("Collections",
                                  "timestamp op_name op_id op_data action")


class QueueContent(object):
    """Structure to support a tree from the content of the request queue."""

    def __init__(self, home):
        self.home = home
        self.share_real = None
        self.share_link = None
        self._node_ops = {}
        self.internal_ops = []
        self._transferring = set()

    def _get_node_ops(self):
        """Return the node ops without the home root."""
        # search for the home root, if any
        nodes = self._node_ops[''].children if self._node_ops else {}
        return [(ROOT_HOME, nodes)]

    node_ops = property(_get_node_ops)

    def _get_transferring(self):
        """Tell if we're transferring something."""
        return bool(self._transferring)

    transferring = property(_get_transferring)

    def clear(self):
        """Clear the finished commands."""

        def inspect(children):
            """Inspect recursively."""

            for _, data in children.items():
                if data.done:
                    if data.children:
                        # just fix ops and state, and leave it
                        data.done = None
                        data.operations[:] = []
                    else:
                        # remove it, and go backwards
                        while data.parent is not None:
                            parent = data.parent
                            del parent.children[data.name]
                            if parent.done is not None or parent.children:
                                break
                            data = data.parent
                        else:
                            # special root handling
                            if not children:
                                del self._node_ops['']
                inspect(data.children)

        inspect(self._node_ops)

    def set_shares_dirs(self, share_link, share_real):
        """Set shares dirs."""
        if (not share_link.startswith(self.home) or
                not share_real.startswith(self.home)):
            raise ValueError("Both shares directories need to be under home")
        self.share_real = share_real
        self.share_link = share_link

    def set_content(self, data):
        """Set the whole structures with the received data."""
        for op_info in data:
            self.add(*op_info)

    def _get_path_elements(self, op_name, data):
        """Extract the path from data and adjust it."""
        path_id = PATH_SPECIALS.get(op_name, PATH_DEFAULT)
        path = data[path_id]
        if self.share_real is not None and path.startswith(self.share_real):
            path = self.share_link + path[len(self.share_real):]
        if path.startswith(self.home):
            path = path[len(self.home):]
        if not path.startswith(os.path.sep):
            path = os.path.sep + path
        elements = path.split(os.path.sep)
        return elements

    def add(self, op_name, op_id, op_data):
        """Add an operation to the structures."""
        f = self._add_node if op_name in NODE_OPS else self._add_internal
        return f(op_name, op_id, op_data)

    def _add_internal(self, op_name, op_id, op_data):
        """Add an internal operation."""
        op = Internal(op_name=op_name, op_id=op_id, op_data=op_data,
                      timestamp=time.time(), action=ACTION_ADDED)
        self.internal_ops.append(op)
        return INTERNAL_OP

    def _add_node(self, op_name, op_id, op_data):
        """Add a node operation."""
        # if a transfer operation, keep account of it
        if op_name == OP_UPLOAD or op_name == OP_DOWNLOAD:
            self._transferring.add(op_id)

        elements = self._get_path_elements(op_name, op_data)

        # loop on all except the last one just to get the final one or create
        # all needed in the middle
        children = self._node_ops
        node = None   # root parent ;)
        for elem in elements[:-1]:
            if elem in children:
                node = children[elem]
            else:
                node = Node(elem, node, KIND_DIR)
                children[elem] = node

            children = node.children

        elem = elements[-1]
        op_data = op_data.copy()
        op_data[DONE] = False
        operation = (op_id, op_name, op_data)
        if op_name == OP_MAKEFILE:
            this_kind = KIND_FILE
        elif op_name == OP_MAKEDIR:
            this_kind = KIND_DIR
        else:
            this_kind = KIND_UNKNOWN

        if elem in children:
            node = children[elem]
            node.last_modified = time.time()
            if node.kind is KIND_UNKNOWN and this_kind is not KIND_UNKNOWN:
                node.kind = this_kind

            # if node was already done, start clean with the operations
            if node.done:
                node.operations[:] = [operation]
                node.done = False
            else:
                node.operations.append(operation)
        else:
            node = Node(elem, node, this_kind, last_modified=time.time(),
                        done=False, operations=[operation])
            children[elem] = node
        return NODE_OP

    def remove(self, op_name, op_id, op_data):
        """Remove an operation from the structures."""
        f = self._remove_node if op_name in NODE_OPS else self._remove_internal
        return f(op_name, op_id, op_data)

    def _remove_internal(self, op_name, op_id, op_data):
        """Mark as finished one internal operation."""
        op = Internal(op_name=op_name, op_id=op_id, op_data=op_data,
                      timestamp=time.time(), action=ACTION_REMOVED)
        self.internal_ops.append(op)
        return INTERNAL_OP

    def _remove_node(self, op_name, op_id, op_data):
        """Mark as finished one operation in the structure"""
        # if a transfer operation, keep account of it
        if op_name == OP_UPLOAD or op_name == OP_DOWNLOAD:
            self._transferring.discard(op_id)

        elements = self._get_path_elements(op_name, op_data)

        # loop on all except the last one just to get the final one or create
        # all needed in the middle
        children = self._node_ops
        for elem in elements:
            try:
                node = children[elem]
            except KeyError:
                logger.warning("Element %r (from %r) not in children %s",
                               elem, elements, children)
                return

            children = node.children

        # search for the operation in the list
        ops = [x for x in node.operations if x[0] == op_id]
        if len(ops) != 1:
            logger.error("Operation %s [%s] found %d times in node %s",
                         op_name, op_id, len(ops), node)
            return

        # fix the operation
        op_dict = ops[0][2]
        op_dict[DONE] = True

        # check if all the operations finished
        if all(x[2][DONE] for x in node.operations):
            node.done = True

        # adjust last modified time
        node.last_modified = time.time()
        return NODE_OP
