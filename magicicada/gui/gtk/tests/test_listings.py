# -*- coding: utf-8 -*-
#
# Authors: Natalia Bidart <nataliabidart@gmail.com>
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

"""Tests for the listings widgets."""

# pylint: disable=E0611
from gi.repository import Gtk
# pylint: enable=E0611

from twisted.internet import defer

from magicicada.gui.gtk.listings import (
    ADD_NEW_FOLDER,
    ARE_YOU_SURE,
    ARE_YOU_SURE_REMOVE_FOLDER,
    ARE_YOU_SURE_REMOVE_FOLDER_SECONDARY_TEXT,
    ERROR_MESSAGE,
    ERROR_MESSAGE_MARKUP,
    FoldersButton,
    FoldersDialog,
    ListingDialog,
    ListingButton,
    PublicFilesButton,
    PublicFilesDialog,
    SharesToMeButton,
    SharesToMeDialog,
    SharesToOthersButton,
    SharesToOthersDialog,
)
from magicicada.gui.gtk.tests import (
    BaseTestCase,
    SAMPLE_FOLDERS,
    SAMPLE_SHARES_TO_ME,
    SAMPLE_SHARES_TO_OTHERS,
    SAMPLE_PUBLIC_FILES,
)
from magicicada.tests import Recorder


# Access to a protected member _called of a client class
# pylint: disable=W0212


TEST_UI = """
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <requires lib="gtk+" version="2.24"/>
  <!-- interface-naming-policy project-wide -->
  <object class="GtkScrolledWindow" id="root">
    <child>
      <object class="GtkTreeView" id="view">
        <property name="model">store</property>
        <child>
          <object class="GtkTreeViewColumn" id="col1">
            <child>
              <object class="GtkCellRendererText" id="cellrenderertext1"/>
              <attributes>
                <attribute name="text">0</attribute>
              </attributes>
            </child>
          </object>
        </child>
        <child>
          <object class="GtkTreeViewColumn" id="col2">
            <child>
              <object class="GtkCellRendererText" id="cellrenderertext2"/>
              <attributes>
                <attribute name="text">1</attribute>
              </attributes>
            </child>
          </object>
        </child>
      </object>
    </child>
  </object>
  <object class="GtkListStore" id="store">
    <columns>
      <!-- column-name test1 -->
      <column type="gchararray"/>
      <!-- column-name test2 -->
      <column type="gchararray"/>
    </columns>
  </object>
</interface>
"""


class TestDataField(object):
    """A generic data field."""

    def __init__(self, attrs=2, prefix='foo'):
        self._attrs = attrs
        for i in xrange(attrs):
            attr_name = 'attr%i' % i
            setattr(self, attr_name, u'%s-%i' % (prefix, i))

    def __len__(self):
        return self._attrs


class FakeDialog(Recorder):
    """A Fake Dialog that knows how to run and hide itself."""

    response = Gtk.ResponseType.NONE
    no_wrap = ['_called', 'response', 'args', 'kwargs']

    def __init__(self, *args, **kwargs):
        super(FakeDialog, self).__init__()
        self.args = args
        self.kwargs = kwargs
        self.get_filename = lambda: None

    def run(self):
        """Fake the run."""
        return self.response


class ListingDialogTestCase(BaseTestCase):
    """Test case for the ListingDialog widget."""

    items = [TestDataField(), TestDataField(), TestDataField()]
    ui_class = ListingDialog

    @defer.inlineCallbacks
    def setUp(self):
        self.patch(Gtk, 'FileChooserDialog', FakeDialog)
        self.patch(Gtk, 'MessageDialog', FakeDialog)

        if self.ui_class.data_fields is None:
            fakes = (('attr0', lambda s: u''.join(reversed(s))),
                     ('attr1', lambda s: s.replace(u'-', u' ❥ ')))
            self.patch(self.ui_class, 'data_fields', fakes)

        if self.ui_class.sd_attr is None:
            self.patch(self.ui_class, 'sd_attr', 'fake_sd_attr')

        if self.ui_class.filename is None:
            builder = Gtk.Builder()
            builder.add_from_string(TEST_UI)
            self.kwargs['builder'] = builder
            self.addCleanup(self.kwargs.pop, 'builder')

        yield super(ListingDialogTestCase, self).setUp()

        setattr(self.ui.sd, self.ui.sd_attr, self.items)
        self.store = self.ui.store

    def data_fields_to_store_item(self, item):
        """Tranform a list of pairs (field, transformer) into a store item."""
        result = []
        for (i, f) in self.ui.data_fields:
            value = getattr(item, i)
            if f is not None:
                value = f(value)
            result.append(value)

        return (result, [])

    def assert_sort_order_correct(self, column, idx, expected_order):
        """Check that sort order is correctly set for 'self.store'."""
        assert self.store is not None, 'class must provide a store'

        msg0 = 'Store sort id must be %r (got %r instead).'
        msg1 = 'Store sort order must be %r (got %r instead).'
        msg3 = 'Column sort order must be %r (got %r instead).'

        actual_id, actual_order = self.store.get_sort_column_id()

        # store sort column id and order
        self.assertEqual(idx, actual_id, msg0 % (idx, actual_id))
        self.assertEqual(expected_order, actual_order,
                         msg1 % (expected_order, actual_order))

        # column sort order
        actual_order = column.get_sort_order()
        self.assertEqual(expected_order, actual_order,
                         msg3 % (expected_order, actual_order))

    def assert_sort_indicator_correct(self, column):
        """Check that sort indicator is correctly set."""
        assert self.ui.view is not None, 'class must provide a view'

        msg = 'Column %s must have sort indicator %s.'
        colname = column.get_name()
        # column sort indicator
        self.assertTrue(column.get_sort_indicator(), msg % (colname, 'on'))

        # all the other columns must not have the sort indicator on
        for other_column in self.ui.view.get_columns():
            if other_column.get_name() == colname:
                continue
            self.assertFalse(other_column.get_sort_indicator(),
                             msg % (other_column.get_name(), 'off'))

    def assert_on_toggle_renderer_toggled(self, path, value, column, item_id,
                                          activate_op, deactivate_op,
                                          toggled_cb):
        """When a toggle renderer is toggled, the backend is called.

        - 'path' is the tree path to the row being tested.

        - 'column' is the model column to get the toggle value from.

        - 'value' is the value from the items list for the row being tested.

        - 'activate_op' and 'deactivate_op' are the ops that will be checked to
           be present in the self.ui.sd._called sequence, along with 'item_id'.

        """
        self.ui.load()
        assert getattr(self.ui.sd, self.ui.sd_attr) == self.items

        toggled_cb(object(), path)

        op = deactivate_op if value else activate_op
        self.assert_method_called(self.ui.sd, op, item_id)

        tree_iter = self.ui.store.get_iter_from_string(path)
        value = not value
        self.assertEqual(value,
                         self.ui.store.get_value(tree_iter, column))

        toggled_cb(object(), path)

        op = deactivate_op if value else activate_op
        self.assert_method_called(self.ui.sd, op, item_id)

    def test_dialog_properties(self):
        """The dialog has correct properties."""
        self.assert_dialog_properties(dialog=self.ui,
                                      title=self.ui_class.title)

    def test_syncdaemon_instance(self):
        """The syncdaemon_instance is correct."""
        self.assertIs(self.ui.sd, self.sd)

    def test_visible(self):
        """The widget is not visible."""
        self.assertFalse(self.ui.get_visible())

    def test_button(self):
        """The buttons are correct."""
        # only one button
        buttons = self.ui.get_action_area().get_children()
        self.assertTrue(len(buttons) > 0)

        # with the Gtk.STOCK_CLOSE stock
        close_button = buttons[-1]
        self.assertIs(self.ui.close_button, close_button)
        self.assertTrue(close_button.get_use_stock())
        stock = close_button.get_image().get_stock()
        self.assertEqual(stock, (Gtk.STOCK_CLOSE, Gtk.IconSize.BUTTON))

        # that emits Gtk.ResponseType.CLOSE when clicked
        widget = self.ui.get_widget_for_response(Gtk.ResponseType.CLOSE)
        self.assertIs(widget, close_button)

    def test_warning_label(self):
        """The warning_label is packed and empty."""
        self.assertTrue(self.ui.warning_label.get_visible())
        self.assertTrue(self.ui.warning_label.get_selectable())
        self.assertTrue(self.ui.warning_label.get_line_wrap())
        self.assertEqual(self.ui.warning_label.get_text(), '')
        self.assertEqual(self.ui.get_content_area().get_children()[0],
                         self.ui.warning_label)

    def test_root_is_packed(self):
        """The root widget is the content area."""
        self.assertEqual(self.ui.get_content_area().get_children()[1],
                         self.ui.root)

    def test_size_request(self):
        """The size is correct."""
        self.assertEqual(self.ui.get_size_request(), self.ui.default_size)

    def test_load(self):
        """Calling load() populates the store."""
        expected = [self.data_fields_to_store_item(item)
                    for item in self.items]

        self.ui.load()

        self.assert_store_correct(expected)

    def test_load_twice(self):
        """Calling load() twice clears the store between calls."""
        self.test_load()
        self.test_load()

    def test_load_handles_none(self):
        """When querying syncdaemon for data, None is properly handled."""
        self.patch(self.ui.sd, self.ui.sd_attr, None)
        self.ui.load()
        self.assert_store_correct([])

    def test_columns_not_sorted_at_start(self):
        """The columns are not sorted at start."""
        msg = 'Column %s must not have the sort indicator on.'
        for col in self.ui.view.get_columns():
            self.assertFalse(col.get_sort_indicator(), msg % col.get_name())

    def test_columns_are_clickable(self):
        """The columns are clickable."""
        msg = 'Column %s must be clickable.'
        for col in self.ui.view.get_columns():
            self.assertTrue(col.get_clickable(), msg % col.get_name())

    def test_columns_clicked_signal(self):
        """The columns clicks signal is properly connected."""
        msg = 'Column %s must be connected to on_store_sort_column_changed.'
        for col in self.ui.view.get_columns():
            self.assertTrue(col.get_clickable(), msg % col.get_name())

    def test_sorting(self):
        """The panel can be re-sorted."""
        for idx, col in enumerate(self.ui.view.get_columns()):
            col.clicked()  # click on the column
            self.assert_sort_order_correct(col, idx, Gtk.SortType.ASCENDING)
            self.assert_sort_indicator_correct(col)

            col.clicked()  # click on the column, sort order must change
            self.assert_sort_order_correct(col, idx, Gtk.SortType.DESCENDING)

            col.clicked()  # click again, sort order must be the first one
            self.assert_sort_order_correct(col, idx, Gtk.SortType.ASCENDING)

    def test_view_selection_single(self):
        """The view selection's mode is SINGLE."""
        self.assertEqual(self.ui.view.get_selection().get_mode(),
                         Gtk.SelectionMode.SINGLE)

    def test_on_error(self, exc=None):
        """On error 'exc', show a error dialog."""
        if exc is None:
            exc = TypeError('foo')
            self.ui.on_error(exc)

        self.assertTrue(self.ui.warning_label.get_visible())
        error_msg = ERROR_MESSAGE % dict(details=' (%s)' % exc)
        self.assertEqual(self.ui.warning_label.get_text(), error_msg)
        self.assertEqual(self.ui.warning_label.get_label(),
                         ERROR_MESSAGE_MARKUP % error_msg)

    def test_confirm_dialog(self):
        """The confirm dialog dialog is properly created."""
        self.assertIsInstance(self.ui.confirm_dialog, Gtk.MessageDialog)

    def test_confirm_dialog_creation_params(self):
        """The confirm dialog dialog is created with the expected params."""
        self.assertEqual(self.ui.confirm_dialog.args, ())
        flags = Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
        kwargs = dict(parent=self.ui,
                      flags=flags,
                      type=Gtk.MessageType.QUESTION,
                      buttons=Gtk.ButtonsType.YES_NO)
        self.assertEqual(self.ui.confirm_dialog.kwargs, kwargs)

    def test_confirm_dialog_title(self):
        """The confirm dialog dialog title is correct."""
        self.assert_method_called(self.ui.confirm_dialog, 'set_title',
                                  ARE_YOU_SURE)

    @defer.inlineCallbacks
    def test_call_async_disables_ui(self):
        """While calling an async operation, the UI is disabled."""
        self.patch(self.ui, 'load', self._set_called)

        def check():
            """Check ui sensibility."""
            result = self.ui.is_sensitive()
            return defer.succeed(result)

        self.assertTrue(self.ui.is_sensitive(),
                        'The ui must be enabled before calling the op.')

        was_sensitive = yield self.ui.call_async(check)

        self.assertFalse(was_sensitive,
                         'The ui must be disabled while calling the op.')
        self.assertTrue(self.ui.is_sensitive(),
                        'The ui must be enabled after calling the op.')
        self.test_warning_label()  # the warning_label is cleared
        self.assertEqual(self._called, ((), {}), 'load was called')

    @defer.inlineCallbacks
    def test_call_async_handles_errors(self):
        """While calling an async operation, errors are catched and logged."""
        self.patch(self.ui, 'load', self._set_called)
        msg = 'Crash boom bang'
        exc = AssertionError(msg)

        def fail_zaraza():
            """Throw any error."""
            return defer.fail(exc)

        result = yield self.ui.call_async(fail_zaraza)

        self.assertEqual(result, None)
        self.assertTrue(self.memento.check_exception(exc.__class__, msg))
        self.assertTrue(self.memento.check_error(fail_zaraza.__name__))
        self.test_on_error(exc=exc)
        self.assertEqual(self._called, ((), {}), 'load was called')

    @defer.inlineCallbacks
    def test_call_async_success_after_error(self):
        """Warning messages are cleared after an error."""
        yield self.ui.call_async(lambda: defer.fail(ValueError()))
        yield self.test_call_async_disables_ui()


class FoldersDialogTestCase(ListingDialogTestCase):
    """UI test cases for folders."""

    items = SAMPLE_FOLDERS
    ui_class = FoldersDialog

    def test_file_chooser(self):
        """The file chooser dialog is properly created."""
        self.assertIsInstance(self.ui.file_chooser, Gtk.FileChooserDialog)

        self.assertEqual(self.ui.file_chooser.args, ())
        kwargs = dict(title=ADD_NEW_FOLDER, parent=None,
                      action=Gtk.FileChooserAction.SELECT_FOLDER,
                      buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                               Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))
        self.assertEqual(self.ui.file_chooser.kwargs, kwargs)

    def test_on_subscribed_renderer_toggled(self):
        """When subscribed is toggled, the backend is called."""
        path = '1'
        subscribed = self.items[int(path)].subscribed
        item_id = self.items[int(path)].volume
        self.assert_on_toggle_renderer_toggled(
            path=path, column=1,
            value=subscribed, item_id=item_id,
            activate_op='subscribe_folder', deactivate_op='unsubscribe_folder',
            toggled_cb=self.ui.on_subscribed_renderer_toggled)

    @defer.inlineCallbacks
    def test_on_add_folder_button_clicked_file_chooser_cancel(self):
        """When the file choosing is canceled, the backend is not called."""
        self.patch(self.ui.file_chooser, 'response', Gtk.ResponseType.CANCEL)
        yield self.ui.add_folder_button.clicked()

        self.assert_methods_called(self.ui.file_chooser, ['run', 'hide'])
        self.assert_no_method_called(self.ui.sd)
        self.assertTrue(self.ui.is_sensitive())

    @defer.inlineCallbacks
    def test_on_add_folder_button_clicked_file_chooser_close(self):
        """When the file choosing is closed, the backend is not called."""
        self.patch(self.ui.file_chooser, 'response', Gtk.ResponseType.CLOSE)
        yield self.ui.add_folder_button.clicked()

        self.assert_methods_called(self.ui.file_chooser, ['run', 'hide'])
        self.assert_no_method_called(self.ui.sd)
        self.assertTrue(self.ui.is_sensitive())

    @defer.inlineCallbacks
    def test_on_add_folder_button_clicked_file_chooser_accept(self):
        """When the add_folder_button is clicked, the backend is called."""
        self.patch(self.ui, 'load', self._set_called)
        self.patch(self.ui.file_chooser, 'response', Gtk.ResponseType.ACCEPT)

        def check():
            """Perform a middle check."""
            self.assertFalse(self.ui.is_sensitive())

        self.patch(self.ui.sd, 'create_folder', check)

        path = '~/foo/test/me'
        self.patch(self.ui.file_chooser, 'get_filename', lambda: path)

        yield self.ui.add_folder_button.clicked()

        expected = ['get_filename', 'run', 'hide']
        self.assert_methods_called(self.ui.file_chooser, expected)
        self.assert_method_called(self.ui.sd, 'create_folder', path)
        self.assertEqual(self._called, ((), {}), 'load() was called.')
        self.assertTrue(self.ui.is_sensitive())

    def test_on_folder_op_error_callback(self):
        """The on_folder_op_error_callback is defined and connected."""
        self.assertEqual(self.ui.sd.on_folder_op_error_callback,
                         self.ui.on_error)

    def test_remove_folder_button_disabled(self):
        """At startup, the remove button is disabled."""
        self.ui.load()
        self.assertFalse(self.ui.remove_folder_button.get_sensitive())


class FoldersDialogRemoveFolderTestCase(FoldersDialogTestCase):
    """Test case for folder removal."""

    @defer.inlineCallbacks
    def setUp(self):
        yield super(FoldersDialogRemoveFolderTestCase, self).setUp()
        self.ui.load()
        idx = 0  # the testing folder
        self.ui.view.set_cursor(idx)
        _, _, self.path, _, self.volume_id = SAMPLE_FOLDERS[idx]

    def test_remove_folder_button_disabled(self):
        """When there is no folder selected, the remove button is disabled."""
        self.ui.view.get_selection().unselect_all()
        self.ui.on_view_cursor_changed()
        self.assertFalse(self.ui.remove_folder_button.get_sensitive())

    def test_remove_folder_button_enabled(self):
        """When there is a folder selected, the remove button is enabled."""
        self.assertTrue(self.ui.remove_folder_button.get_sensitive())

    @defer.inlineCallbacks
    def test_on_remove_folder_button_clicked_confirm_dialog_is_shown(self):
        """On remove_folder_button clicked, the confirm_dialog is shown."""
        yield self.ui.remove_folder_button.clicked()

        msg = ARE_YOU_SURE_REMOVE_FOLDER % self.path
        self.assert_method_called(self.ui.confirm_dialog, 'set_markup', msg)
        self.assert_method_called(self.ui.confirm_dialog,
                                  'format_secondary_text',
                                  ARE_YOU_SURE_REMOVE_FOLDER_SECONDARY_TEXT)
        self.assert_method_called(self.ui.confirm_dialog, 'run')
        self.assert_method_called(self.ui.confirm_dialog, 'hide')

    @defer.inlineCallbacks
    def test_on_remove_folder_button_clicked_closes_dialog(self):
        """If the user closes the dialog, nothing is done."""
        self.patch(self.ui.confirm_dialog, 'response',
                   Gtk.ResponseType.DELETE_EVENT)
        yield self.ui.remove_folder_button.clicked()

        self.assert_no_method_called(self.ui.sd)
        self.assertTrue(self.ui.is_sensitive())

    @defer.inlineCallbacks
    def test_on_remove_folder_button_clicked_answers_no(self):
        """If the user answers no, nothing is done."""
        self.patch(self.ui.confirm_dialog, 'response', Gtk.ResponseType.NO)
        yield self.ui.remove_folder_button.clicked()

        self.assert_no_method_called(self.ui.sd)
        self.assertTrue(self.ui.is_sensitive())

    @defer.inlineCallbacks
    def test_on_remove_folder_button_clicked_answers_yes(self):
        """If the user answers yes, sd.delete_folder is called."""
        self.patch(self.ui.confirm_dialog, 'response', Gtk.ResponseType.YES)

        def check():
            """Perform a middle check."""
            self.assertFalse(self.ui.is_sensitive())

        self.patch(self.ui.sd, 'delete_folder', check)

        yield self.ui.remove_folder_button.clicked()

        self.assert_method_called(self.ui.sd, 'delete_folder', self.volume_id)
        self.assertTrue(self.ui.is_sensitive())


class SharesToMeDialogTestCase(ListingDialogTestCase):
    """UI test cases for shares_to_me."""

    items = SAMPLE_SHARES_TO_ME
    ui_class = SharesToMeDialog

    def test_on_accepted_renderer_toggled(self):
        """When accepted is toggled, the backend is called."""
        path = '0'
        accepted = self.items[int(path)].accepted
        item_id = self.items[int(path)].volume_id
        self.assert_on_toggle_renderer_toggled(
            path=path, column=2,
            value=accepted, item_id=item_id,
            activate_op='accept_share', deactivate_op='reject_share',
            toggled_cb=self.ui.on_accepted_renderer_toggled)

    def test_on_subscribed_renderer_toggled(self):
        """When subscribed is toggled, the backend is called."""
        path = '0'
        subscribed = self.items[int(path)].subscribed
        item_id = self.items[int(path)].volume_id
        self.assert_on_toggle_renderer_toggled(
            path=path, column=3,
            value=subscribed, item_id=item_id,
            activate_op='subscribe_share',
            deactivate_op='unsubscribe_share',
            toggled_cb=self.ui.on_subscribed_renderer_toggled)


class SharesToOthersDialogTestCase(ListingDialogTestCase):
    """UI test cases for shares_to_others."""

    items = SAMPLE_SHARES_TO_OTHERS
    ui_class = SharesToOthersDialog


class PublicFilesDialogTestCase(ListingDialogTestCase):
    """UI test cases for public files."""

    items = SAMPLE_PUBLIC_FILES
    ui_class = PublicFilesDialog


class ListingButtonTestCase(BaseTestCase):
    """Test case for the ListingButton widget."""

    label = None
    stock_id = None
    ui_class = ListingButton

    @defer.inlineCallbacks
    def setUp(self):
        self.patch(self.ui_class, 'dialog_class', FakeDialog)
        yield super(ListingButtonTestCase, self).setUp()

    def test_label(self):
        """The label is correct."""
        self.assertEqual(self.ui.get_label(), self.label)

    def test_stock_id(self):
        """The stock_id is correct."""
        self.assertEqual(self.ui.get_stock_id(), self.stock_id)

    def test_dialog(self):
        """The dialog is correct."""
        self.assertIsInstance(self.ui.dialog, FakeDialog)
        self.assertEqual(self.ui.dialog.args, (self.sd,))
        self.assertEqual(self.ui.dialog.kwargs, {})

    def test_visible(self):
        """The widget is visible."""
        self.assertTrue(self.ui.get_visible())

    def test_clicked_connected(self):
        """When the button is clicked, self.ui.on_clicked is called."""
        self.patch(self.ui_class, 'on_clicked', self._set_called)
        self.ui = self.ui_class(**self.kwargs)
        self.ui.emit('clicked')

        self.assertEqual(self._called, ((self.ui, self.ui), {}))

    def test_on_clicked(self):
        """Test the on_clicked callback."""
        self.ui.on_clicked()

        self.assert_methods_called(self.ui.dialog, ['run', 'hide'])


class FoldersButtonTestCase(ListingButtonTestCase):
    """Test case for the FoldersButton widget."""

    label = 'Folders'
    stock_id = 'gtk-directory'
    ui_class = FoldersButton


class SharesToMeButtonTestCase(ListingButtonTestCase):
    """Test case for the SharesToMeButton widget."""

    label = 'Shares to Me'
    stock_id = 'gtk-network'
    ui_class = SharesToMeButton


class SharesToOthersButtonTestCase(ListingButtonTestCase):
    """Test case for the SharesToOthersButton widget."""

    label = 'Shares to Others'
    stock_id = 'gtk-network'
    ui_class = SharesToOthersButton


class PublicFilesButtonTestCase(ListingButtonTestCase):
    """Test case for the PublicFilesButton widget."""

    label = 'Public Files'
    stock_id = 'gtk-file'
    ui_class = PublicFilesButton
