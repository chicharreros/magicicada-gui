# Tests for the QueueContent interface
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

"""Tests for the QueueContent structure."""

import logging
import unittest

from ubuntuone.devtools.handlers import MementoHandler

from magicicada.queue_content import (
    KIND_DIR,
    KIND_FILE,
    KIND_UNKNOWN,
    ROOT_HOME,
    ACTION_ADDED,
    ACTION_REMOVED,
    NODE_OP,
    INTERNAL_OP,
    QueueContent,
)


# pylint: disable=W0212


class TwoStructuresTestCase(unittest.TestCase):
    """Tests that we change the corresponding structure."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/a/b')

    def test_set_empty(self):
        """Set nothing."""
        self.qc.set_content([])
        self.assertFalse(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_node_makefile(self):
        """Set one node with a file op."""
        self.qc.set_content([('MakeFile', '123', {'path': '/a/b/foo'})])
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_node_makedir(self):
        """Set one node with a file op."""
        self.qc.set_content([('MakeDir', '123', {'path': '/a/b/foo'})])
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_node_unlink(self):
        """Set one node with a file op."""
        self.qc.set_content([('Unlink', '123', {'path': '/a/b/foo'})])
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_node_move(self):
        """Set one node with a file op."""
        self.qc.set_content([('Move', '123', {'path_from': '/a/b/foo'})])
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_node_upload(self):
        """Set one node with a file op."""
        self.qc.set_content([('Upload', '123', {'path': '/a/b/foo'})])
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_node_download(self):
        """Set one node with a file op."""
        self.qc.set_content([('Download', '123', {'path': '/a/b/foo'})])
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)

    def test_set_one_internal(self):
        """Set one internal op."""
        self.qc.set_content([('ListShares', '456', {})])
        self.assertFalse(self.qc._node_ops)
        self.assertTrue(self.qc.internal_ops)

    def test_set_mixed_ops(self):
        """Set a couple of node and internal ops."""
        self.qc.set_content([('MakeFile', '123', {'path': 'foo'}),
                             ('ListShares', '456', {})])
        self.assertTrue(self.qc._node_ops)
        self.assertTrue(self.qc.internal_ops)

    def test_set_is_several_adds(self):
        """Check that one set are several adds."""
        called = []
        self.qc.add = lambda *a: called.append(a)
        self.qc.set_content([('MakeFile', '123', {'path': 'foo'}),
                             ('ListShares', '456', {})])
        self.assertTrue(called[0], ('MakeFile', '123', {'path': 'foo'}))
        self.assertTrue(called[1], ('ListShares', '456', {}))

    def test_add_one_node(self):
        """Add one node op."""
        r = self.qc.add('Unlink', '456', {'path': 'foo'})
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)
        self.assertEqual(r, NODE_OP)

    def test_add_one_internal(self):
        """Add one internal op."""
        r = self.qc.add('ListShares', '456', {})
        self.assertFalse(self.qc._node_ops)
        self.assertTrue(self.qc.internal_ops)
        self.assertEqual(r, INTERNAL_OP)

    def test_remove_one_node(self):
        """Remove one node op."""
        self.qc.add('Unlink', '456', {'path': 'foo'})
        r = self.qc.remove('Unlink', '456', {'path': 'foo'})
        self.assertTrue(self.qc._node_ops)
        self.assertFalse(self.qc.internal_ops)
        self.assertEqual(r, NODE_OP)

    def test_remove_one_internal(self):
        """Remove one internal op."""
        self.qc.add('ListShares', '456', {})
        r = self.qc.remove('ListShares', '456', {})
        self.assertFalse(self.qc._node_ops)
        self.assertTrue(self.qc.internal_ops)
        self.assertEqual(r, INTERNAL_OP)


class NodeStructureTestCase(unittest.TestCase):
    """Tests that we store the node commands ok."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/')
        self.handler = MementoHandler()
        self.handler.setLevel(logging.DEBUG)
        logger = logging.getLogger('magicicada.queue_content')
        logger.addHandler(self.handler)
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.removeHandler, self.handler)

    def test_one_node_file(self):
        """Add one node with a file op."""
        self.qc.set_content([('MakeFile', '123', {'path': '/a/b/foo'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['b']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['foo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('123', 'MakeFile',
                     {'path': '/a/b/foo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_one_node_dir(self):
        """Add one node with a dir op."""
        self.qc.set_content([('MakeDir', '123', {'path': '/a/boo'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['boo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('123', 'MakeDir', {'path': '/a/boo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_one_node_unknown(self):
        """Add one node with a unknown op."""
        self.qc.set_content([('Unlink', '123', {'path': '/a/boo'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['boo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_UNKNOWN)
        expected = [('123', 'Unlink', {'path': '/a/boo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_one_node_known_unknown(self):
        """Add one node known op with a later unknown op."""
        self.qc.set_content([('MakeFile', '123', {'path': '/a'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('123', 'MakeFile', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        self.qc.set_content([('Unlink', '456', {'path': '/a'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('123', 'MakeFile', {'path': '/a', '__done__': False}),
                    ('456', 'Unlink', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_one_node_unknown_known(self):
        """Add one node unknown op with a later known op."""
        self.qc.set_content([('Unlink', '123', {'path': '/a'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_UNKNOWN)
        expected = [('123', 'Unlink', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        self.qc.set_content([('MakeDir', '456', {'path': '/a'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('123', 'Unlink', {'path': '/a', '__done__': False}),
                    ('456', 'MakeDir', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_several_nodes_mixed(self):
        """Add some nodes with different combinations."""
        # add /a/b
        self.qc.set_content([('MakeDir', '12', {'path': '/a/b'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        node = self.qc._node_ops[''].children['a']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['b']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # add /a/b/foo
        self.qc.set_content([('MakeDir', '34', {'path': '/a/b/foo'})])
        node = self.qc._node_ops[''].children['a']

        node = node.children['b']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 1)

        node = node.children['foo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('34', 'MakeDir', {'path': '/a/b/foo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # add /a/b/bar
        self.qc.set_content([('MakeDir', '45', {'path': '/a/b/bar'})])
        node = self.qc._node_ops[''].children['a']

        node = node.children['b']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 2)

        node = node.children['bar']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('45', 'MakeDir', {'path': '/a/b/bar', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # add /a/b/foo/fighters
        self.qc.set_content([('MakeFile', '67',
                              {'path': '/a/b/foo/fighters'})])
        node = self.qc._node_ops[''].children['a']

        node = node.children['b']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 2)

        node = node.children['foo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('34', 'MakeDir', {'path': '/a/b/foo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 1)

        node = node.children['fighters']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('67', 'MakeFile',
                     {'path': '/a/b/foo/fighters', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # other /a/b/foo/fighters
        self.qc.set_content([('Unlink', '89', {'path': '/a/b/foo/fighters'})])
        node = self.qc._node_ops[''].children['a']

        node = node.children['b']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 2)

        node = node.children['foo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('34', 'MakeDir', {'path': '/a/b/foo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 1)

        node = node.children['fighters']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        p = '/a/b/foo/fighters'
        expected = [('67', 'MakeFile', {'path': p, '__done__': False}),
                    ('89', 'Unlink', {'path': p, '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_finishing_nothing(self):
        """Finish something that is not there."""
        r = self.qc.remove('MakeDir', '34', {'path': '/a/bar'})
        self.assertEqual(r, None)
        self.assertTrue(self.handler.check_warning(
                        "Element ''", "['', 'a', 'bar']", 'not in children'))

    def test_operation_error_nothing(self):
        """Finish an operation that is not there."""
        # create a node and break it on purpose
        self.qc.add('MakeDir', '12', {'path': '/a'})
        self.assertEqual(len(self.qc._node_ops), 1)
        node = self.qc._node_ops[''].children['a']
        node.operations = []

        # remove the operation and check
        r = self.qc.remove('MakeDir', '12', {'path': '/a'})
        self.assertEqual(r, None)
        self.assertTrue(self.handler.check_error(
                        "found 0 times", "MakeDir", "12"))

    def test_operation_error_several(self):
        """Finish an operation that is more than once."""
        # create a node and break it on purpose
        self.qc.add('MakeDir', '12', {'path': '/a'})
        self.assertEqual(len(self.qc._node_ops), 1)
        node = self.qc._node_ops[''].children['a']
        node.operations = node.operations * 2

        # remove the operation and check
        r = self.qc.remove('MakeDir', '12', {'path': '/a'})
        self.assertEqual(r, None)
        self.assertTrue(self.handler.check_error(
                        "found 2 times", "MakeDir", "12"))

    def test_two_ops_finishing_one(self):
        """Add some nodes with different combinations."""
        # create two dirs
        self.qc.set_content([('MakeDir', '12', {'path': '/a/foo'}),
                             ('MakeDir', '34', {'path': '/a/bar'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        # all inited properly
        root = self.qc._node_ops[''].children['a']
        self.assertEqual(root.last_modified, None)
        self.assertEqual(root.kind, KIND_DIR)
        self.assertEqual(root.operations, [])
        self.assertEqual(root.done, None)
        self.assertEqual(len(root.children), 2)

        node = root.children['foo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a/foo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        node = root.children['bar']
        bar_created_timestamp = node.last_modified
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('34', 'MakeDir', {'path': '/a/bar', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # finish the second make dir and check again
        self.qc.remove('MakeDir', '34', {'path': '/a/bar'})
        self.assertTrue(node.last_modified > bar_created_timestamp)
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('34', 'MakeDir', {'path': '/a/bar', '__done__': True})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, True)
        self.assertEqual(len(node.children), 0)

    def test_two_ops_finishing_both(self):
        """Add two ops to the same node and finish both."""
        # create two dirs
        self.qc.set_content([('MakeFile', '12', {'path': '/a'}),
                             ('Upload', '34', {'path': '/a'})])
        self.assertEqual(len(self.qc._node_ops), 1)

        # all inited properly
        node = self.qc._node_ops[''].children['a']
        node_created_tstamp = node.last_modified
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('12', 'MakeFile', {'path': '/a', '__done__': False}),
                    ('34', 'Upload', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # finish one
        self.qc.remove('MakeFile', '12', {'path': '/a'})
        node_changed_tstamp = node.last_modified
        self.assertTrue(node.last_modified > node_created_tstamp)
        expected = [('12', 'MakeFile', {'path': '/a', '__done__': True}),
                    ('34', 'Upload', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)

        # finish the second
        self.qc.remove('Upload', '34', {'path': '/a'})
        self.assertTrue(node.last_modified > node_changed_tstamp)
        expected = [('12', 'MakeFile', {'path': '/a', '__done__': True}),
                    ('34', 'Upload', {'path': '/a', '__done__': True})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, True)

    def test_one_op_finishes_startsagain(self):
        """Add an op, finish it, add another one."""
        self.qc.add('MakeFile', '12', {'path': '/a'})
        self.assertEqual(len(self.qc._node_ops), 1)

        # all inited properly
        node = self.qc._node_ops[''].children['a']
        node_created_tstamp = node.last_modified
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('12', 'MakeFile', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

        # finish the op
        self.qc.remove('MakeFile', '12', {'path': '/a'})
        node_changed_tstamp = node.last_modified
        self.assertTrue(node.last_modified > node_created_tstamp)
        expected = [('12', 'MakeFile', {'path': '/a', '__done__': True})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, True)

        # send other one to the same node
        self.qc.add('Upload', '34', {'path': '/a'})
        self.assertTrue(node.last_modified > node_changed_tstamp)
        expected = [('34', 'Upload', {'path': '/a', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)


class GetPathTestCase(unittest.TestCase):
    """Test how we get the path from the operation."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/')

    def test_makefile(self):
        """Get path from makefile."""
        r = self.qc._get_path_elements('MakeFile', dict(path='foo'))
        self.assertEqual(r, ['', 'foo'])

    def test_makedir(self):
        """Get path from makedir."""
        r = self.qc._get_path_elements('MakeDir', dict(path='foo'))
        self.assertEqual(r, ['', 'foo'])

    def test_move(self):
        """Get path from Move."""
        r = self.qc._get_path_elements('Move',
                                       dict(path_from='foo', path_to='bar'))
        self.assertEqual(r, ['', 'foo'])

    def test_unlink(self):
        """Get path from unlink."""
        r = self.qc._get_path_elements('Unlink', dict(path='foo'))
        self.assertEqual(r, ['', 'foo'])

    def test_upload(self):
        """Get path from upload."""
        r = self.qc._get_path_elements('Upload', dict(path='foo'))
        self.assertEqual(r, ['', 'foo'])

    def test_download(self):
        """Get path from download."""
        r = self.qc._get_path_elements('Download', dict(path='foo'))
        self.assertEqual(r, ['', 'foo'])


class ClearNodesTestCase(unittest.TestCase):
    """Clear the nodes on request."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/')

    def test_empty_structure(self):
        """Empty structure."""
        self.qc.clear()
        self.assertFalse(self.qc._node_ops)

    def test_nothing_to_clear(self):
        """Commands that are not done."""
        self.qc.add('MakeFile', '12', {'path': '/a'})
        self.qc.clear()
        self.assertIn('a', self.qc._node_ops[''].children)

    def test_one_to_clear(self):
        """Commands that can be removed."""
        self.qc.add('MakeFile', '12', {'path': '/a'})
        self.qc.remove('MakeFile', '12', {'path': '/a'})
        self.qc.clear()
        self.assertNotIn('', self.qc._node_ops)
        self.assertFalse(self.qc._node_ops)

    def test_one_to_alter(self):
        """Commands that are not done."""
        self.qc.add('MakeDir', '12', {'path': '/a'})
        self.qc.add('MakeFile', '23', {'path': '/a/b'})
        self.qc.remove('MakeDir', '12', {'path': '/a'})

        node = self.qc._node_ops[''].children['a']
        self.assertEqual(node.kind, KIND_DIR)
        expected = [('12', 'MakeDir', {'path': '/a', '__done__': True})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, True)
        self.assertEqual(len(node.children), 1)

        node = node.children['b']
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('23', 'MakeFile', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)

        # clear and check again
        self.qc.clear()
        node = self.qc._node_ops[''].children['a']
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['b']
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('23', 'MakeFile', {'path': '/a/b', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)

    def test_one_fixed_and_two_to_clear(self):
        """Commands that can be removed."""
        # create them  all
        self.qc.add('MakeDir', '12', {'path': '/a/b'})
        self.qc.add('MakeDir', '23', {'path': '/a/h'})
        self.qc.add('MakeFile', '45', {'path': '/a/b/c'})

        node_a = self.qc._node_ops[''].children['a']
        self.assertEqual(node_a.done, None)

        node_b = node_a.children['b']
        self.assertEqual(node_b.done, False)

        node_h = node_a.children['h']
        self.assertEqual(node_h.done, False)

        node_c = node_b.children['c']
        self.assertEqual(node_c.done, False)

        # remove the makedir and makefile
        self.qc.remove('MakeDir', '12', {'path': '/a/b'})
        self.qc.remove('MakeFile', '45', {'path': '/a/b/c'})
        self.assertEqual(node_b.done, True)
        self.assertEqual(node_c.done, True)

        # clear and check
        self.qc.clear()

        node_a = self.qc._node_ops[''].children['a']
        self.assertEqual(node_a.done, None)

        node_h = node_a.children['h']
        self.assertEqual(node_h.done, False)

        self.assertNotIn('b', node_a.children)


class DeliverNodeDataTestCase(unittest.TestCase):
    """Send the node data without the home."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/a/b')
        self.qc.set_shares_dirs('/a/b/link', '/a/b/real')

    def test_share_link_inside_home(self):
        """Assure the share link is inside home."""
        self.assertRaises(ValueError, self.qc.set_shares_dirs,
                          share_link='/a/k', share_real='/a/b/r')

    def test_share_real_inside_home(self):
        """Assure the share real is inside home."""
        self.assertRaises(ValueError, self.qc.set_shares_dirs,
                          share_link='/a/b/r', share_real='/a/k')

    def test_none(self):
        """Test getting with nothing."""
        self.assertEqual(self.qc.node_ops[0][0], ROOT_HOME)
        self.assertEqual(self.qc.node_ops[0][1], {})

    def test_one_home(self):
        """Test getting with one in home."""
        self.qc.add('MakeFile', '67', {'path': '/a/b/foo/fighters'})
        self.assertEqual(self.qc.node_ops[0][0], ROOT_HOME)
        node = self.qc.node_ops[0][1]['foo']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

    def test_two_home(self):
        """Test getting with two in home."""
        self.qc.set_content([('MakeFile', '67',
                             {'path': '/a/b/foo/fighters'})])
        self.qc.set_content([('MakeFile', '99', {'path': '/a/b/bar'})])
        self.assertEqual(self.qc.node_ops[0][0], ROOT_HOME)
        self.assertEqual(len(self.qc.node_ops[0][1]), 2)

        # first node
        node = self.qc.node_ops[0][1]['foo']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        # second node
        node = self.qc.node_ops[0][1]['bar']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('99', 'MakeFile',
                     {'path': '/a/b/bar', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_one_share(self):
        """Test getting with one share."""
        self.qc.set_content([('MakeFile', '12', {'path': '/a/b/real/foo'})])
        self.assertEqual(self.qc.node_ops[0][0], ROOT_HOME)

        node = self.qc.node_ops[0][1]['link']
        self.assertEqual(node.last_modified, None)
        self.assertEqual(node.kind, KIND_DIR)
        self.assertEqual(node.operations, [])
        self.assertEqual(node.done, None)
        self.assertEqual(len(node.children), 1)

        node = node.children['foo']
        self.assertTrue(isinstance(node.last_modified, float))
        self.assertEqual(node.kind, KIND_FILE)
        expected = [('12', 'MakeFile',
                     {'path': '/a/b/real/foo', '__done__': False})]
        self.assertEqual(node.operations, expected)
        self.assertEqual(node.done, False)
        self.assertEqual(len(node.children), 0)

    def test_several_mixed(self):
        """Test mixing two nodes in the same share, other share, and home."""
        self.qc.set_content([('MakeDir', '0', {'path': '/a/b/j'})])
        self.qc.set_content([('MakeDir', '1', {'path': '/a/b/real/foo/bar1'})])
        self.qc.set_content([('MakeDir', '2', {'path': '/a/b/real/foo/bar2'})])
        self.qc.set_content([('MakeDir', '3', {'path': '/a/b/real/othr/baz'})])
        self.assertEqual(self.qc.node_ops[0][0], ROOT_HOME)
        self.assertIn('j', self.qc.node_ops[0][1])
        link_dir = self.qc.node_ops[0][1]['link']
        self.assertIn('othr', link_dir.children)
        foo_dir = link_dir.children['foo']
        self.assertIn('bar1', foo_dir.children)
        self.assertIn('bar2', foo_dir.children)


class InternalStructureTestCase(unittest.TestCase):
    """Tests that we store the internal commands ok."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/a/b')

    def test_none(self):
        """No operations added."""
        self.assertFalse(self.qc.internal_ops)

    def test_one_added(self):
        """Add one op."""
        self.qc.add('ListShares', '456', {'a': 3})
        data = self.qc.internal_ops[0]
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'ListShares')
        self.assertEqual(data.op_id, '456')
        self.assertEqual(data.op_data, {'a': 3})
        self.assertEqual(data.action, ACTION_ADDED)

    def test_one_removed(self):
        """Remove one op."""
        self.qc.remove('ListShares', '456', {'a': 3})
        data = self.qc.internal_ops[0]
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'ListShares')
        self.assertEqual(data.op_id, '456')
        self.assertEqual(data.op_data, {'a': 3})
        self.assertEqual(data.action, ACTION_REMOVED)

    def test_same_added_removed(self):
        """Add and remove the same op."""
        self.qc.add('ListShares', '456', {'a': 3})
        self.qc.remove('ListShares', '456', {'a': 3})

        data = self.qc.internal_ops[0]
        op_added_tstamp = data.timestamp
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'ListShares')
        self.assertEqual(data.op_id, '456')
        self.assertEqual(data.op_data, {'a': 3})
        self.assertEqual(data.action, ACTION_ADDED)

        data = self.qc.internal_ops[1]
        self.assertTrue(data.timestamp > op_added_tstamp)
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'ListShares')
        self.assertEqual(data.op_id, '456')
        self.assertEqual(data.op_data, {'a': 3})
        self.assertEqual(data.action, ACTION_REMOVED)

    def test_several_mixed(self):
        """Add and remove several operations."""
        self.qc.add('ListShares', '456', {'a': 3})
        self.qc.add('GetDelta', '789', {'b': 5})
        self.qc.remove('ListShares', '123', {'c': 7})

        data = self.qc.internal_ops[0]
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'ListShares')
        self.assertEqual(data.op_id, '456')
        self.assertEqual(data.op_data, {'a': 3})
        self.assertEqual(data.action, ACTION_ADDED)

        data = self.qc.internal_ops[1]
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'GetDelta')
        self.assertEqual(data.op_id, '789')
        self.assertEqual(data.op_data, {'b': 5})
        self.assertEqual(data.action, ACTION_ADDED)

        data = self.qc.internal_ops[2]
        self.assertTrue(isinstance(data.timestamp, float))
        self.assertEqual(data.op_name, 'ListShares')
        self.assertEqual(data.op_id, '123')
        self.assertEqual(data.op_data, {'c': 7})
        self.assertEqual(data.action, ACTION_REMOVED)


class TransferringFlagTestCase(unittest.TestCase):
    """Tests that check the transferring flag."""

    def setUp(self):
        """Set up the test."""
        self.qc = QueueContent(home='/a/b')

    def test_init(self):
        """Of course, at start time we're not transferring."""
        self.assertFalse(self.qc.transferring)

    def test_add_non_transferring_op(self):
        """Add a non transferring op."""
        self.qc.add('ListShares', '456', {'a': 3})
        self.assertFalse(self.qc.transferring)

    def test_add_download(self):
        """Add a download."""
        self.qc.add('Download', '456', {'path': 'foo'})
        self.assertTrue(self.qc.transferring)

    def test_add_remove_download(self):
        """Add and remove a download."""
        self.qc.add('Download', '456', {'path': 'foo'})
        self.qc.remove('Download', '456', {'path': 'foo'})
        self.assertFalse(self.qc.transferring)

    def test_add_upload(self):
        """Add a download."""
        self.qc.add('Upload', '456', {'path': 'foo'})
        self.assertTrue(self.qc.transferring)

    def test_add_remove_upload(self):
        """Add and remove a download."""
        self.qc.add('Upload', '456', {'path': 'foo'})
        self.qc.remove('Upload', '456', {'path': 'foo'})
        self.assertFalse(self.qc.transferring)

    def test_add_different_combinations(self):
        """Different combinations."""
        self.qc.add('Upload', '1', {'path': 'foo'})
        self.assertTrue(self.qc.transferring)

        self.qc.add('ListShares', '2', {'a': 3})
        self.assertTrue(self.qc.transferring)

        self.qc.add('Download', '3', {'path': 'foo'})
        self.assertTrue(self.qc.transferring)

        self.qc.remove('Upload', '1', {'path': 'foo'})
        self.assertTrue(self.qc.transferring)

        self.qc.remove('Download', '3', {'path': 'foo'})
        self.assertFalse(self.qc.transferring)

        self.qc.remove('ListShares', '2', {'a': 3})
        self.assertFalse(self.qc.transferring)
