# -*- coding: utf-8 -*-

# Copyright 2011-2012 Chicharreros
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

"""Magicicada GTK UI."""

from __future__ import division

import logging
import time

# pylint: disable=E0611
from gi.repository import Gtk
# pylint: enable=E0611

from magicicada import queue_content, syncdaemon
from magicicada.helpers import humanize_bytes
from magicicada.gui.gtk.helpers import Buildable

# pylint: disable=E0602

ELLIPSIS = u'...'
EXPAND_THRESHOLD = 15
FILE_ICON_NAME = u'text-x-generic'
FOLDER_ICON_NAME = u'folder'
HOME_ICON_NAME = u'user-home'
OPS_COMPLETED = _(u'Completed %s ago (%s)')
OPS_MARKUP = u'<span foreground="#808080">%s</span>'
MAX_OP_LEN = 30
REMOTE_ICON_NAME = u'folder-remote'
TIME_UNITS = {0: _(u'second'), 1: _(u'minute'), 2: _(u'hour'), 3: _(u'day')}
TRANSFER_OPS = (u'Upload', u'Download')
TRANSFER_TEXT = _('{transfered} of {total} ({percent:.1f}%)')


logger = logging.getLogger('magicicada.gui.gtk.operations')


# Instance of 'A' has no 'y' member
# pylint: disable=E1101

# Unused argument, we need them for GTK callbacks
# pylint: disable=W0613


def pixbuf_from_icon_name(name):
    """Build a pixbuf for a given icon name."""
    icon = Gtk.IconTheme()
    flags = (Gtk.IconLookupFlags.GENERIC_FALLBACK |
             Gtk.IconLookupFlags.USE_BUILTIN)
    pixbuf = icon.load_icon(name, 24, flags)
    return pixbuf


class Operations(Buildable, Gtk.Alignment):
    """The list of operations over files/folders."""

    filename = 'operations.ui'

    def __init__(self, syncdaemon_instance=None):
        Buildable.__init__(self)
        Gtk.Alignment.__init__(self, xscale=1, yscale=1)
        self.add(self.itself)
        self.ops_store = self.builder.get_object('ops_store')
        self._can_clear = False
        self._store_idx = {}

        if syncdaemon_instance is not None:
            self.sd = syncdaemon_instance
        else:
            self.sd = syncdaemon.SyncDaemon()
        self.sd.on_node_ops_changed_callback = self.on_node_ops_changed
        self.sd.on_transfers_callback = self.on_transfers

        self.clear_button.set_sensitive(False)
        self.show_all()

    def _process_operations(self, info):
        """Return the string to be shown as operations summary.

        The result may contain pango markup.

        """
        if not info.operations:
            return ''

        result = ', '.join([i[1] for i in info.operations
                            if not i[2][queue_content.DONE]])
        if not result:
            ops = ', '.join([i[1] for i in info.operations])
            if len(ops) > MAX_OP_LEN:
                ops = ops[:MAX_OP_LEN - len(ELLIPSIS)] + ELLIPSIS
            ago = int(time.time() - info.last_modified)
            unit = 0
            while ago >= 60:
                ago = ago // 60
                unit += 1
                if unit not in TIME_UNITS:
                    break

            ago = "%s %s%s" % (ago, TIME_UNITS[unit], 's' if ago != 1 else '')

            result = OPS_COMPLETED % (ago, ops)
            self._can_clear = True

        return OPS_MARKUP % result

    def _append_row(self, parent_iter, row, row_info=None):
        """Append 'row' to the ops store, having 'parent_iter' as parent."""
        row_key = None
        transfer_ops = []
        show_transfer = False
        current_children = []

        if parent_iter is None:
            # parent being None complicates how the children are get
            nch = self.ops_store.iter_n_children(None)
            current_children = [self.ops_store[i] for i in range(nch)]
        else:
            # get the items at this level (chidren from parent)
            current_children = list(self.ops_store[parent_iter].iterchildren())

        if row_info is not None:
            transfer_ops = filter(lambda op: op[1] in TRANSFER_OPS,
                                  row_info.operations)

        if transfer_ops:
            row_key = transfer_ops[0][2]['path']
            all_done = all(op[2][queue_content.DONE] for op in transfer_ops)
            show_transfer = not all_done

        for child in current_children:
            if row[0] == child[0].decode("utf8"):
                # row in current children, let's just modify it
                child[1] = row[1]
                child[6] = show_transfer
                tree_iter = child.iter
                break
        else:
            # not there in current children, let's add it
            row = row + (0, show_transfer, '')
            tree_iter = self.ops_store.append(parent_iter, row)

        if row_key is not None:
            self._store_idx[row_key] = tree_iter

        return tree_iter

    def _append_file_row(self, file_name, file_info, parent):
        """Append a new row to the store representing a file."""
        assert file_info.children == {}
        row = (file_name, self._process_operations(file_info),
               None, FILE_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR)
        self._append_row(parent, row, file_info)

    def _append_folder_row(self, folder_name, folder_info, parent):
        """Append a new row to the store representing a folder."""
        row = (folder_name, self._process_operations(folder_info),
               None, FOLDER_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR)
        parent = self._append_row(parent, row, folder_info)

        self._append_root_row(folder_info.children, parent)

        ## Expanding/collpasing is not working properly yet
        ##tree_path = self.ops_store.get_path(parent)
        ##children = len(folder_info.children)
        ##if children <= EXPAND_THRESHOLD:
        ##    self.ops_view.expand_to_path(tree_path)
        ##else:
        ##    self.ops_view.collapse_row(tree_path)

    def _append_root_row(self, root_info, parent):
        """Append a new row to the store representing a root share."""
        info = sorted(root_info.iteritems(),
                      key=lambda (name, data): (data.kind, name))
        for child_name, child_info in info:
            if child_info.kind == queue_content.KIND_DIR:
                self._append_folder_row(child_name, child_info, parent)
            else:
                self._append_file_row(child_name, child_info, parent)

    def on_node_ops_changed(self, items, clear=False):
        """Callback'ed when syncadaemon's node ops info changed."""
        if not items:
            items = []

        self.ops_view.set_model(None)
        if clear:
            self.ops_store.clear()
        self._can_clear = False

        for root_kind, root_info in items:
            icon_name = (HOME_ICON_NAME
                         if root_kind == queue_content.ROOT_HOME
                         else REMOTE_ICON_NAME)
            row = (root_kind, '', None, icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            parent = self._append_row(None, row)
            self._append_root_row(root_info, parent)

        self.ops_view.set_model(self.ops_store)
        #self.ops_view.expand_row('0', False)
        self.ops_view.expand_all()

        self.clear_button.set_sensitive(self._can_clear)

        self.show_all()

    def on_clear_button_clicked(self, button):
        """The clear button was clicked, remove all complete operations."""
        self.sd.queue_content.clear()
        self.on_node_ops_changed(self.sd.queue_content.node_ops, clear=True)

    def load(self):
        """Update UI based on SD current state."""
        self.sd.get_current_transfers()
        self.on_node_ops_changed(self.sd.queue_content.node_ops)

    def on_transfers(self, transfers):
        """Process progress for uploads and downloads."""
        for transf in transfers:
            try:
                row_iter = self._store_idx[transf.path]
            except KeyError:
                logger.exception('on_transfers: failed to retrive node from '
                                 'local index to process transfer progress:')
            else:
                transfered = transf.transfered
                transfer = (transfered / float(transf.total)) * 100
                self.ops_store.set_value(row_iter, 5, int(transfer))
                text = TRANSFER_TEXT.format(
                    transfered=humanize_bytes(transfered),
                    total=humanize_bytes(transf.total),
                    percent=transfer)
                self.ops_store.set_value(row_iter, 7, text)
