# -*- coding: utf-8 -*-
#
# Copyright 2010-2012 Chicharreros
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

"""Tests for the Operations widget."""

# pylint: disable=E0611
from gi.repository import Gtk
# pylint: enable=E0611

from magicicada.gui.gtk.tests import BaseTestCase
from magicicada.gui.gtk import operations

# Instance of 'A' has no 'y' member
# pylint: disable=E1101

# Instance of 'A' has no 'y' member (but some types could not be inferred)
# pylint: disable=E1103

# Invalid name Node
# pylint: disable=C0103

# Access to a protected member
# pylint: disable=W0212

# Example of info sent from backend is:
#[('Root',
#  {u'Ubuntu One':
#   <Node Ubuntu One 'Dir' last_modified=None done=None operations=[]
#    children={u'1.txt':
#              <Node 1.txt 'File' last_modified=1313966619.14 done=False
#               operations=[(dbus.String(u'99537584'),
#                            dbus.String(u'MakeFile'), {})]
#               children={}>}>})]

Node = operations.queue_content.Node
DONE_OPS = {operations.queue_content.DONE: True}
UNDONE_OPS = {operations.queue_content.DONE: False}


class FakeTransfer(object):
    """A fake transfer."""
    def __init__(self, path, transfered, total):
        self.__dict__.update(locals())


class NodeOpsTestCase(BaseTestCase):
    """UI test cases for the node ops tree views."""

    ui_class = operations.Operations

    def assert_store_correct(self, items, store=None):
        """Test that 'store' has 'items' as content."""
        store = self.ui.ops_store
        super(NodeOpsTestCase, self).assert_store_correct(items, store)

    def test_itself_is_packed(self):
        """The main widget is packed."""
        self.assertIs(self.ui.itself, self.ui.get_child())

    def test_syncdaemon_instance(self):
        """The syncadaemon instance is stored."""
        self.assertIs(self.ui.sd, self.sd)

    def test_callback_is_connected(self):
        """The on_node_ops_changed callback is connected."""
        self.assertEqual(self.sd.on_node_ops_changed_callback,
                         self.ui.on_node_ops_changed)

    def test_is_visible(self):
        """Is visible at startup."""
        self.assertTrue(self.ui.get_visible())

    def test_model_is_bind(self):
        """The store is bind to the view."""
        self.assertEqual(self.ui.ops_store, self.ui.ops_view.get_model())

    def test_clear_button_is_disabled(self):
        """Can not clear listing at startup."""
        self.assertFalse(self.ui.clear_button.is_sensitive(),
                         'Clear button must be disabled.')

    def test_on_node_ops_changed_roots_only(self):
        """On on_node_ops_changed the view is updated."""
        sd_items = [(operations.queue_content.ROOT_HOME, {}),
                    (u'Yadda', {}), (u'Yodda', {})]
        self.sd.on_node_ops_changed_callback(sd_items)

        root = [u'', u'', None, operations.HOME_ICON_NAME,
                Gtk.IconSize.LARGE_TOOLBAR]
        yada = [u'Yadda', u'', None, operations.REMOTE_ICON_NAME,
                Gtk.IconSize.LARGE_TOOLBAR]
        yoda = [u'Yodda', u'', None, operations.REMOTE_ICON_NAME,
                Gtk.IconSize.LARGE_TOOLBAR]

        self.assert_store_correct([(root, []), (yada, []), (yoda, [])])
        self.assertFalse(self.ui.clear_button.is_sensitive(),
                         'Clear button must be disabled.')

    def test_on_node_ops_changed_root_info(self):
        """On on_node_ops_changed the view is updated."""
        node = Node(name=u'some node', parent=None,
                    kind=operations.queue_content.KIND_DIR)
        sd_items = [(u'Yadda', {node.name: node})]
        self.sd.on_node_ops_changed_callback(sd_items)

        yada = [u'Yadda', u'', None, operations.REMOTE_ICON_NAME,
                Gtk.IconSize.LARGE_TOOLBAR]
        node_row = [node.name, u'', None,
                    operations.FOLDER_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR]
        expected = [(yada, [(node_row, [])])]

        self.assert_store_correct(expected)
        self.assertFalse(self.ui.clear_button.is_sensitive(),
                         'Clear button must be disabled.')

    def test_on_node_ops_changed_dir_and_file(self):
        """On on_node_ops_changed the view is updated."""
        file_node = Node(name=u'a_file.txt', parent=None,
                         kind=operations.queue_content.KIND_FILE)
        file_node.operations = [(object(), u'foo', UNDONE_OPS),
                                (object(), u'bar', DONE_OPS),
                                (object(), u'baz', UNDONE_OPS)]
        dir_node = Node(name=u'a_dir', parent=None,
                        kind=operations.queue_content.KIND_DIR)
        dir_node.operations = [(object(), u'doo', UNDONE_OPS),
                               (object(), u'bar', UNDONE_OPS)]
        node = Node(name=u'some node', parent=None,
                    kind=operations.queue_content.KIND_DIR)
        node.children = {file_node.name: file_node, dir_node.name: dir_node}
        sd_items = [(u'Yadda', {node.name: node})]
        self.sd.on_node_ops_changed_callback(sd_items)

        yada = [u'Yadda', u'', None, operations.REMOTE_ICON_NAME,
                Gtk.IconSize.LARGE_TOOLBAR]
        node_row = [node.name, u'', None,
                    operations.FOLDER_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR]
        file_row = [file_node.name, operations.OPS_MARKUP % u'foo, baz', None,
                    operations.FILE_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR]
        dir_row = [dir_node.name, operations.OPS_MARKUP % u'doo, bar', None,
                   operations.FOLDER_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR]
        expected = [(yada, [(node_row, [(file_row, []), (dir_row, [])])])]

        self.assert_store_correct(expected)
        self.assertFalse(self.ui.clear_button.is_sensitive(),
                         'Clear button must be disabled.')

    def test_on_node_ops_changed_all_done(self):
        """On on_node_ops_changed the view is updated."""
        fixed_time = 12345678
        self.patch(operations.time, 'time', lambda: fixed_time)
        delta = fixed_time - (60 * 60 * 5)
        file_node = Node(name=u'a_file.txt', parent=None, last_modified=delta,
                         kind=operations.queue_content.KIND_FILE)
        long_op_name = u'x' * (operations.MAX_OP_LEN + 1)
        file_node.operations = [(object(), u'foo', DONE_OPS),
                                (object(), u'bar', DONE_OPS),
                                (object(), long_op_name, DONE_OPS)]
        sd_items = [(u'Yadda', {file_node.name: file_node})]
        self.sd.on_node_ops_changed_callback(sd_items)

        yada = [u'Yadda', u'', None, operations.REMOTE_ICON_NAME,
                Gtk.IconSize.LARGE_TOOLBAR]
        op_name = u'foo, bar, ' + long_op_name
        op_name = op_name[:operations.MAX_OP_LEN - len(operations.ELLIPSIS)]
        op_name += operations.ELLIPSIS
        ago = u'5 hours'
        op_name = operations.OPS_COMPLETED % (ago, op_name)
        file_row = [file_node.name, operations.OPS_MARKUP % op_name, None,
                    operations.FILE_ICON_NAME, Gtk.IconSize.SMALL_TOOLBAR]
        expected = [(yada, [(file_row, [])])]

        self.assert_store_correct(expected)
        self.assertTrue(self.ui.clear_button.is_sensitive(),
                        'Clear button must be enabled.')

        # can not clear any longer
        self.sd.on_node_ops_changed_callback([])
        self.assertFalse(self.ui.clear_button.is_sensitive(),
                         'Clear button must be disabled.')

    def test_on_node_ops_changed_handles_none(self):
        """On on_node_ops_changed handles None as items."""
        self.sd.on_node_ops_changed_callback(None)
        self.assert_store_correct([])

    def test_model_is_cleared_before_updating(self):
        """The model is cleared before upadting with a new set of data."""
        sd_items = [(operations.queue_content.ROOT_HOME, {}),
                    (u'Yadda', {}), (u'Yodda', {})]
        self.sd.on_node_ops_changed_callback(sd_items)

        self.sd.on_node_ops_changed_callback([], clear=True)
        self.assertEqual(len(self.ui.ops_store), 0)

    def test_model_is_not_cleared_before_updating(self):
        """The model is not cleared before upadting with a new set of data."""
        sd_items = [(operations.queue_content.ROOT_HOME, {}),
                    (u'Yadda', {}), (u'Yodda', {})]
        self.sd.on_node_ops_changed_callback(sd_items)

        self.sd.on_node_ops_changed_callback([])
        self.assertEqual(len(self.ui.ops_store), 3)

    def test_load(self):
        """Calling load will query the backend."""
        expected = object()
        self.patch(self.ui.sd.queue_content, 'node_ops', expected)
        self.patch(self.ui, 'on_node_ops_changed', self._set_called)

        self.ui.load()

        self.assertEqual(self._called, ((expected,), {}))

    def test_clear_button_clicked(self):
        """When the clear button was clicked, the store is cleared."""
        self.patch(self.ui, 'on_node_ops_changed', self._set_called)
        sd_items = [(operations.queue_content.ROOT_HOME, {}),
                    (u'Yadda', {}), (u'Yodda', {})]
        self.sd.on_node_ops_changed_callback(sd_items)

        self.ui.clear_button.clicked()

        self.assertEqual(len(self.ui.sd.queue_content), 0)
        self.assertEqual(self._called, (([],), {'clear': True}))

    def test_on_transfers_bad_data(self):
        """Something informed that's not there."""
        ops = self.ui_class()
        tx = FakeTransfer("path", 123, 1234)
        assert "path" not in ops._store_idx
        ops.on_transfers([tx])

    def test_on_transfers_one_value(self):
        """Updating one transfer."""
        ops = self.ui_class()
        tx = FakeTransfer("path", 123, 1234)
        ops._store_idx["path"] = "row"

        # patch to record value
        called = []
        self.patch(ops.ops_store, 'set_value', lambda *a: called.append(a))

        # call and check
        ops.on_transfers([tx])
        text = operations.TRANSFER_TEXT.format(transfered="123 bytes",
                                               total="1.2 KiB",
                                               percent=9.98)
        self.assertEqual(called[0], ("row", 5, 9))
        self.assertEqual(called[1], ("row", 7, text))

    def test_on_transfers_several_values(self):
        """Updating one transfer."""
        ops = self.ui_class()
        tx1 = FakeTransfer("path1", 123, 1234)
        tx2 = FakeTransfer("path2", 456, 4567)
        ops._store_idx["path1"] = "row1"
        ops._store_idx["path2"] = "row2"

        # patch to record value
        called = []
        self.patch(ops.ops_store, 'set_value', lambda *a: called.append(a))

        # call and check
        ops.on_transfers([tx1, tx2])
        text1 = operations.TRANSFER_TEXT.format(transfered="123 bytes",
                                                total="1.2 KiB",
                                                percent=9.98)
        text2 = operations.TRANSFER_TEXT.format(transfered="456 bytes",
                                                total="4.5 KiB",
                                                percent=9.998)
        self.assertEqual(called[0], ("row1", 5, 9))
        self.assertEqual(called[1], ("row1", 7, text1))
        self.assertEqual(called[2], ("row2", 5, 9))
        self.assertEqual(called[3], ("row2", 7, text2))
