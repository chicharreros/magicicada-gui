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

"""Tests for magicicada main UI."""

import os
import time

# pylint: disable=E0611
from gi.repository import Gtk, Pango
# pylint: enable=E0611

from twisted.internet import defer

from magicicada import syncdaemon
from magicicada.gui.gtk import status
from magicicada.gui.gtk.tests import BaseTestCase


TEST_FILE = os.path.join('/tmp', 'metadata-test.txt')
TEST_DIR = os.path.join('/tmp', 'metadata-test-dir')


# Access to a protected member of a client class
# pylint: disable=W0212


class BaseMetadataTestCase(BaseTestCase):
    """Base test case for metadata handling."""

    @defer.inlineCallbacks
    def setUp(self):
        yield super(BaseMetadataTestCase, self).setUp()

        # create temp file and dir
        open(TEST_FILE, 'w').close()
        self.addCleanup(os.remove, TEST_FILE)
        os.mkdir(TEST_DIR)
        self.addCleanup(os.rmdir, TEST_DIR)

        self.metadata = {
            'raw_result': dict(bla='ble', foo='bar'),
            'stat': dict(st_size=123, st_mtime=123),
            'path': 'path',
            'changed': 'changed',
        }


class MetadataDialogTestCase(BaseMetadataTestCase):
    """The test case for the MetadataDialog widget."""

    ui_class = status.MetadataDialog

    def test_metadata_close_hides_the_dialog(self):
        """Test metadata close button emits RESPONSE_CLOSE when clicked."""
        self.patch(self.ui.dialog, 'hide', self._set_called)

        self.ui.close_button.clicked()
        self.assertEqual(self._called, ((), {}),
                         "MetadataDialog.hide should be called.")

    def test_metadata_dialog_properties(self):
        """The metadata dialog has correct properties."""
        # title and modal
        title = 'Metadata for %s' % TEST_FILE
        self.ui.run()
        self.ui.got_metadata(TEST_FILE, self.metadata)
        self.assert_dialog_properties(dialog=self.ui.dialog,
                                      position=Gtk.WindowPosition.MOUSE,
                                      title=title, modal=False)
        # text should be wrapped
        actual = self.ui.detailed_info_textview.get_wrap_mode()
        msg = 'wrap mode for view must be Gtk.WrapMode.WORD (got %s instead).'
        self.assertEqual(Gtk.WrapMode.WORD, actual, msg % actual)

        # labels should be selectable
        self.assertTrue(self.ui.path_label.get_selectable())
        self.assertTrue(self.ui.basic_info_label.get_selectable())

    def test_filetype_icon_file(self):
        """Put the file image when it's a file."""
        self.ui.got_metadata(TEST_FILE, self.metadata)
        icon, size = self.ui.filetype_image.get_stock()
        self.assertEqual(icon, Gtk.STOCK_FILE)
        self.assertEqual(size, Gtk.IconSize.MENU)

    def test_filetype_icon_dir(self):
        """Put the dir image when it's a dir."""
        self.ui.got_metadata(TEST_DIR, self.metadata)
        icon, size = self.ui.filetype_image.get_stock()
        self.assertEqual(icon, Gtk.STOCK_DIRECTORY)
        self.assertEqual(size, Gtk.IconSize.MENU)

    def test_not_synched(self):
        """Special case: path not synched."""
        self.ui.got_metadata(TEST_FILE, status.NOT_SYNCHED_PATH)
        self.assertTrue(self.ui.path_label.get_visible())
        self.assertEqual(self.ui.path_label.get_text(), TEST_FILE)
        self.assertTrue(self.ui.basic_info_label.get_visible())
        self.assertEqual(self.ui.basic_info_label.get_text(),
                         status.NOT_SYNCHED_PATH)

    def test_path_label(self):
        """Check it puts the correct path in the label."""
        formatted_path = "specially formatted path"
        self.metadata['path'] = formatted_path
        assert TEST_FILE != formatted_path
        self.ui.got_metadata(TEST_FILE, self.metadata)
        self.assertEqual(self.ui.path_label.get_text(), formatted_path)

    def test_simple_text_no_stat(self):
        """The simple text should support not having stat."""
        self.metadata['stat'] = None
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertFalse("Size" in simple_text)
        self.assertFalse("Modified" in simple_text)

    def test_simple_text_size(self):
        """The simple text should have a size."""
        self.metadata['stat']['st_size'] = 678
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertTrue("Size: 678" in simple_text)

    def test_simple_text_size_broken_humanize(self):
        """Support a broken humanization."""
        broken_size = "will break humanize_bytes"
        self.metadata['stat']['st_size'] = broken_size
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertTrue(broken_size in simple_text)

    def test_simple_text_modified(self):
        """The simple text should have a tstamp."""
        mtime = time.time()
        self.metadata['stat']['st_mtime'] = mtime
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        should = "Modified on " + time.ctime(mtime)
        self.assertTrue(should in simple_text)

    def test_detailed_text(self):
        """The raw data is also shown."""
        self.ui.got_metadata(TEST_FILE, self.metadata)
        raw = self.metadata['raw_result']
        should = '\n'.join('%s: %s' % i for i in raw.iteritems())
        buf = self.ui.detailed_info_textview.get_buffer()
        detailed = buf.get_text(buf.get_start_iter(), buf.get_end_iter(),
                                include_hidden_chars=False)
        self.assertTrue(should in detailed)

    def test_state_none(self):
        """Text and icon for state NONE."""
        self.metadata['changed'] = syncdaemon.CHANGED_NONE
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertTrue("Synchronized" in simple_text)
        icon, size = self.ui.state_image.get_stock()
        self.assertEqual(icon, Gtk.STOCK_APPLY)
        self.assertEqual(size, Gtk.IconSize.LARGE_TOOLBAR)

    def test_state_local(self):
        """Text and icon for state LOCAL."""
        self.metadata['changed'] = syncdaemon.CHANGED_LOCAL
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertTrue("With local changes, uploading" in simple_text)
        icon, size = self.ui.state_image.get_stock()
        self.assertEqual(icon, Gtk.STOCK_GO_UP)
        self.assertEqual(size, Gtk.IconSize.LARGE_TOOLBAR)

    def test_state_server(self):
        """Text and icon for state SERVER."""
        self.metadata['changed'] = syncdaemon.CHANGED_SERVER
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertTrue("With server changes, downloading" in simple_text)
        icon, size = self.ui.state_image.get_stock()
        self.assertEqual(icon, Gtk.STOCK_GO_DOWN)
        self.assertEqual(size, Gtk.IconSize.LARGE_TOOLBAR)

    def test_state_unknown(self):
        """Text and icon for unknow state."""
        self.metadata['changed'] = 'broken'
        self.ui.got_metadata(TEST_FILE, self.metadata)
        simple_text = self.ui.basic_info_label.get_text()
        self.assertTrue("Unknown state" in simple_text)
        self.assertFalse(self.ui.state_image.get_visible())


class StatusTestCase(BaseTestCase):
    """UI test cases for the Status widget."""

    ui_class = status.Status

    def assert_status_correct(self, ):
        """Test that the status label and button is correct."""
        current_state = self.ui.sd.current_state

        state = current_state.state
        if state == syncdaemon.STATE_IDLE:
            expected_image = self.ui._status_images['idle']
            expected_status = status.IDLE
        elif state == syncdaemon.STATE_WORKING:
            expected_image = self.ui._status_images['working']
            expected_status = status.WORKING
        else:
            expected_image = self.ui._status_images['alert']
            if state == syncdaemon.STATE_STARTING:
                expected_status = status.STARTING
            elif state == syncdaemon.STATE_STOPPED:
                expected_status = status.STOPPED
            else:
                expected_status = status.ERROR

        if current_state.is_started:
            if current_state.is_online:
                next_action = status.DISCONNECT
            else:
                next_action = status.CONNECT
        else:
            next_action = status.START

        actual = self.ui.status_label.get_text()
        msg = 'status label test must be "%s" (got "%s" instead).'
        self.assertEqual(expected_status, actual,
                         msg % (expected_status, actual))

        self.assertTrue(self.ui.action_button.get_sensitive())
        self.assertEqual(self.ui.action_button.get_label(), next_action)
        self.assertEqual(self.ui.status_image.get_pixbuf(), expected_image)

    def assert_widget_availability(self, enabled=True,
                                   public_files_enabled=True):
        """Check button availability according to 'enabled'."""
        widget = self.ui.toolbar
        self.assertTrue(widget.get_visible(), 'Should be visible.')
        # all children should be visible

        for n_button in xrange(self.ui.toolbar.get_n_items()):
            button = self.ui.toolbar.get_nth_item(n_button)
            self.assertTrue(button.get_visible(),
                            'Children should be visible.')

        sensitive = widget.is_sensitive()
        msg = 'Should %sbe sensitive.' % ('' if enabled else 'not ')
        self.assertTrue(sensitive if enabled else not sensitive, msg)

        for n_button in xrange(self.ui.toolbar.get_n_items()):
            button = self.ui.toolbar.get_nth_item(n_button)
            sensitive = button.is_sensitive()

            if button is self.ui.public_files:
                expected = public_files_enabled
            else:
                expected = enabled

            msg = 'Button %i should %sbe sensitive.'
            self.assertTrue(sensitive if expected else not sensitive,
                            msg % (n_button, '' if expected else 'not '))

    def test_metadata_callback_is_connected(self):
        """Metadata ready callback is connected."""
        self.assertEqual(self.ui.sd.on_metadata_ready_callback,
                         self.ui.on_metadata_ready,
                         'on_metadata_ready_callback callback must be set.')

    def test_update_is_called_at_startup(self):
        """Update is called at startup."""
        self.patch(self.ui_class, 'update', self._set_called)
        self.ui = self.ui_class()
        self.assertTrue(self._called,
                        'update was called at startup.')

    def test_status_label_ellipsizes(self):
        """The status label ellipsizes."""
        expected = Pango.EllipsizeMode.END
        actual = self.ui.status_label.get_ellipsize()
        self.assertEqual(expected, actual,
                         'label ellipsizes is ELLIPSIZE_END.')

    def test_update_is_correct_for_status_label(self):
        """Correctly updates the status label."""
        self.ui.sd.current_state.set()
        self.ui.update()
        self.assert_status_correct()

    def test_status_label_default_if_not_started(self):
        """Status label is the default if not started."""
        self.assert_status_correct()

    def test_disabled_until_initial_data_ready(self):
        """Folders and shares are disabled until data ready."""
        # disabled at startup
        self.assert_widget_availability(enabled=False,
                                        public_files_enabled=False)

        # enabled when initial data ready
        self.ui.on_initial_data_ready()
        self.assert_widget_availability(public_files_enabled=False)

    def test_public_files_disabled_until_initial_online_data_ready(self):
        """Widget is disabled until initial online data ready."""
        # disabled at startup
        self.assert_widget_availability(enabled=False,
                                        public_files_enabled=False)

        # all enabled but public_files when initial data ready
        self.ui.on_initial_data_ready()
        self.assert_widget_availability(public_files_enabled=False)

        # all enabled when initial online data ready
        self.ui.on_initial_online_data_ready()
        self.assert_widget_availability()

    def test_enabled_until_stopped(self):
        """Folders and shares are enabled until offline."""
        self.assert_widget_availability(enabled=False,
                                        public_files_enabled=False)

        self.ui.on_initial_data_ready()
        self.assert_widget_availability(public_files_enabled=False)

        self.ui.on_initial_online_data_ready()
        self.assert_widget_availability()


class StatusMetadataTestCase(BaseMetadataTestCase):
    """UI test cases for metadata display."""

    ui_class = status.Status

    @defer.inlineCallbacks
    def setUp(self):
        yield super(StatusMetadataTestCase, self).setUp()

        # no need for the file_chooser to actually run, it works.
        self.patch(self.ui.file_chooser, 'run', lambda: Gtk.ResponseType.CLOSE)

        self._file_chooser_path = None

        # no need for the file_chooser to actually run, it works.
        self.patch(self.ui.file_chooser, 'run',
                   lambda: Gtk.FileChooserAction.OPEN)

        # store whatever file was set
        self.patch(self.ui.file_chooser, 'set_filename',
                   lambda path: setattr(self, '_file_chooser_path', path))

        # return the stored path
        self.patch(self.ui.file_chooser, 'get_filename',
                   lambda: getattr(self, '_file_chooser_path'))

    def assert_visibility(self, md_dialog, dialog, info, spinner):
        """Check the visibility for dialog, text_view and spinner."""
        msg = '%s visibility should be %s (got %s instead).'
        visible = md_dialog.dialog.get_visible()
        self.assertEqual(dialog, visible,
                         msg % ('dialog', dialog, visible))

        visible = md_dialog.filepath_hbox.get_visible()
        self.assertEqual(info, visible,
                         msg % ('filepath_hbox', info, visible))

        visible = md_dialog.state_hbox.get_visible()
        self.assertEqual(info, visible,
                         msg % ('state_hbox', info, visible))

        visible = md_dialog.details_expander.get_visible()
        self.assertEqual(info, visible,
                         msg % ('details_expander', info, visible))

        visible = md_dialog.spinner.get_visible()
        self.assertEqual(spinner, visible,
                         msg % ('spinner', spinner, visible))

    def test_file_chooser_is_hidden_at_startup(self):
        """File chooser exists but is not visible."""
        self.assertFalse(self.ui.file_chooser.get_visible(),
                         'file_chooser must be hidden by default.')

    def test_filename_is_used_only_if_open_clicked(self):
        """Filename is used only if user clicked open."""
        # no need for the file_chooser to actually run, it works.
        self.patch(self.ui.file_chooser, 'run', lambda: Gtk.ResponseType.CLOSE)
        self.patch(self.ui.sd, 'get_metadata', self._set_called)

        self.ui.on_metadata_clicked(self.ui.metadata)

        msg = 'get_metadata should not be called if no file chosen.'
        self.assertFalse(self._called, msg)

    def test_filename_is_stored_if_open_was_clicked(self):
        """Filename is stored in the metadata dicts if user clicked open."""
        self.assertEqual(self.ui._metadata_dialogs, {},
                         'no dialogs in the ui.')

        self.ui._u1_root = os.path.dirname(TEST_FILE)
        self.ui.file_chooser.set_filename(TEST_FILE)
        self.ui.on_metadata_clicked(self.ui.metadata)

        self.assertEqual([TEST_FILE], self.ui._metadata_dialogs.keys(),
                         'metadata dict keys should be what the user choose.')

    def test_on_metadata_ready_doesnt_update_if_last_path_doesnt_match(self):
        """Callback on_metadata_ready updates the metadata_view."""
        path = 'bla'
        assert path not in self.ui._metadata_dialogs
        self.ui.on_metadata_ready(path, self.metadata)
        self.assertTrue(self.memento.check_info("on_metadata_ready", path,
                                                "not in stored paths"))

    def test_file_chooser_open_emits_response_ok(self):
        """Test volume close button emits RESPONSE_CLOSE when clicked."""
        self.patch(self.ui.file_chooser, 'response', self._set_called)

        self.ui.file_chooser_open.clicked()

        msg = 'file_chooser_open should emit %s (got %s instead).'
        expected = Gtk.FileChooserAction.OPEN
        self.assertEqual(self._called, ((expected,), {}),
                         msg % (expected, self._called))

    def test_on_metadata_ready(self):
        """Callback on_metadata_ready executes the dialog method."""
        path = 'bla'
        md = status.MetadataDialog()
        called = []
        md.got_metadata = lambda *a: called.extend(a)
        self.ui._metadata_dialogs[path] = md
        self.ui.on_metadata_ready(path, self.metadata)
        self.assertEqual(called, [path, self.metadata])

    def test_on_metadata_clicked(self):
        """Test on_metadata_clicked."""
        self.ui._u1_root = os.path.dirname(TEST_FILE)
        self.ui.file_chooser.set_filename(TEST_FILE)

        self.ui.on_metadata_clicked(self.ui.metadata)

        # file_chooser must be visible on metadata clicked.
        self.assertEqual(TEST_FILE, self.ui.file_chooser.get_filename(),
                         'filename returned by file chooser must be correct.')

        # dialog must exist now
        dialog = self.ui._metadata_dialogs[TEST_FILE]

        # metadata_dialog is enabled and shows the loading animation
        self.assert_visibility(dialog, dialog=True, info=False, spinner=True)
        self.assertIsInstance(dialog.spinner, Gtk.Spinner)
        self.assertTrue(dialog.spinner.get_property('active'),
                        'metadata_spinner is active.')

        # check that the metadata was asked to the SD
        self.assertEqual(1, len(self.ui.sd._meta_paths))
        self.assertEqual(self.ui.sd._meta_paths[0], TEST_FILE)
        # SD will eventually callback us with the metadata
        self.ui.on_metadata_ready(TEST_FILE, self.metadata)

        # metadata_dialog is enabled and shows the metadata
        self.assert_visibility(dialog, dialog=True, info=True, spinner=False)

        # user closes the dialog
        dialog.close_button.clicked()

        # dialog was closed already
        visible = dialog.dialog.get_visible()
        self.assertFalse(visible, 'metadata_dialog should not be visible.')

    def test_two_metadata_windows(self):
        """More than one metadata window is allowed."""
        self.patch(self.ui.file_chooser, 'run',
                   lambda: Gtk.FileChooserAction.OPEN)

        path1 = os.path.abspath(self.mktemp())
        open(path1, 'w').close()
        assert os.path.exists(path1)
        meta1 = dict(raw_result={'value': 'Lorem ipsum dolor sit amet.'})

        path2 = os.path.abspath(self.mktemp())
        open(path2, 'w').close()
        assert os.path.exists(path2)
        meta2 = dict(raw_result={'value': 'Etiam iaculis congue nisl.'})

        #import pdb; pdb.set_trace()
        assert len(self.ui._metadata_dialogs) == 0

        self.ui.file_chooser.get_filename = lambda: path1
        self.ui.on_metadata_clicked(self.ui.metadata)

        self.ui.file_chooser.get_filename = lambda: path2
        self.ui.on_metadata_clicked(self.ui.metadata)

        # Check that the UI has 2 metadata dialogs
        self.assertEqual(2, len(self.ui._metadata_dialogs))
        called1 = []
        md1 = self.ui._metadata_dialogs[path1]
        md1.got_metadata = lambda *a: called1.extend(a)
        called2 = []
        md2 = self.ui._metadata_dialogs[path2]
        md2.got_metadata = lambda *a: called2.extend(a)

        # Check that the metadata was asked to the SD
        self.assertEqual(2, len(self.ui.sd._meta_paths))
        self.assertEqual(self.ui.sd._meta_paths[0], path1)
        self.assertEqual(self.ui.sd._meta_paths[1], path2)

        # SD will eventually callback us with the metadata
        self.ui.on_metadata_ready(path1, meta1)
        # SD will eventually callback us with the metadata
        self.ui.on_metadata_ready(path2, meta2)

        self.assertEqual(called1, [path1, meta1])
        self.assertEqual(called2, [path2, meta2])

        # user closes the dialog
        self.ui._metadata_dialogs[path1].close_button.clicked()
        self.ui._metadata_dialogs[path2].close_button.clicked()
