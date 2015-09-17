# -*- coding: utf-8 -*-
#
# Copyright 2010-2014 Chicharreros
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

import logging

from functools import wraps

from magicicada import syncdaemon
from magicicada.gui.gtk import main
from magicicada.gui.gtk.tests import BaseTestCase, FakedSyncdaemon


def override_input_output(input_args, output_args):
    """Call 'f' but receive fixed input and return fixed output."""

    def decorator(f):
        """The decorator per se."""

        @wraps(f)
        def inner(*args, **kwargs):
            """Feed 'f' with 'input_args' and return 'output_args'."""
            f(input_args)
            return output_args

        return inner

    return decorator


# Access to a protected member of a client class
# pylint: disable=W0212


class MagicicadaUITestCase(BaseTestCase):
    """UI test cases for basic state."""

    ui_class = main.MagicicadaUI
    kwargs = {}

    def test_init_creates_sd_instance(self):
        """SyncDaemon instance is created at creation time."""
        self.assertTrue(self.ui.sd is not None)
        self.assertTrue(isinstance(self.ui.sd, FakedSyncdaemon))

    def test_destroy_shutdowns_sd_instance(self):
        """SyncDaemon instance is shutdown at destroy time."""
        self.patch(self.ui.sd, 'shutdown', self._set_called)
        self.ui.on_main_window_destroy(self.ui.main_window)
        self.assertTrue(self._called,
                        'syncdaemon.shutdown must be called at destroy time.')

    def test_main_window_get_visible(self):
        """UI can be created and main_window is visible."""
        self.assertTrue(self.ui.main_window.get_visible())

    def test_main_window_have_correct_icon_list(self):
        """Every window has the icon set."""
        self.assertEqual(len(self.ui.main_window.get_icon_list()),
                         len(self.ui._icons.values()))

    def test_every_window_has_correct_list(self):
        """The default icon list is set."""
        icons = self.ui.main_window.get_default_icon_list()
        self.assertEqual(len(icons), len(self.ui._icons.values()))

    def test_status_changed_callback_is_connected(self):
        """Status callback is connected."""
        self.assertEqual(self.ui.sd.status_changed_callback,
                         self.ui.on_status_changed,
                         'status_changed callback must be set.')

    def test_initial_data_ready_callback_connected(self):
        """The callback 'on_initial_data_ready' is connected to SD."""
        self.assertEqual(self.ui.sd.on_initial_data_ready_callback,
                         self.ui.on_initial_data_ready,
                         "on_initial_data_ready should be connected.")

    def test_initial_online_data_ready_callback_connected(self):
        """The callback 'on_initial_online_data_ready' is connected to SD."""
        self.assertEqual(self.ui.sd.on_initial_online_data_ready_callback,
                         self.ui.on_initial_online_data_ready,
                         "on_initial_online_data_ready should be connected.")

    def test_on_status_changed_updates_status_widget(self):
        """On status changed, the status widget is updated."""
        self.patch(self.ui.status, 'update', self._set_called)

        self.ui.on_status_changed()

        self.assertEqual(self._called, ((), {}))

    def test_on_initial_data_ready_updates_status_widget(self):
        """On initial data ready, the status widget is updated."""
        self.patch(self.ui.status, 'on_initial_data_ready', self._set_called)

        self.ui.on_initial_data_ready()

        self.assertEqual(self._called, ((), {}))

    def test_on_initial_data_ready_updates_operations_widget(self):
        """On initial data ready, the status widget is updated."""
        self.patch(self.ui.operations, 'load', self._set_called)

        self.ui.on_initial_data_ready()

        self.assertEqual(self._called, ((), {}))

    def test_on_initial_online_data_ready_updates_status_widget(self):
        """On initial online data ready, the status widget is updated."""
        self.patch(self.ui.status, 'on_initial_online_data_ready',
                   self._set_called)

        self.ui.on_initial_online_data_ready()

        self.assertEqual(self._called, ((), {}))

    def test_update_statusicon_idle(self):
        """Status icon is updated to idle."""
        self.ui.on_status_changed(state=syncdaemon.STATE_IDLE)
        icon_name = self.ui.indicator.indicator.get_icon()
        self.assertEqual(icon_name, "icon-idle-16")

    def test_update_statusicon_working(self):
        """Status icon is updated to working."""
        self.ui.on_status_changed(state=syncdaemon.STATE_WORKING)
        icon_name = self.ui.indicator.indicator.get_icon()
        self.assertEqual(icon_name, "icon-working-16")

    def test_update_statusicon_alert(self):
        """Status icon is updated to alert."""
        self.ui.on_status_changed(state=syncdaemon.STATE_STOPPED)
        icon_name = self.ui.indicator.indicator.get_icon()
        self.assertEqual(icon_name, "icon-alert-16")

    def test_main_window_is_hid_when_icon_clicked(self):
        """Main window is hid when the systray icon is clicked."""
        self.ui.show_hide()
        self.assertFalse(self.ui.main_window.get_visible(),
                         'main_window should be invisible when icon clicked.')

    def test_main_window_is_shown_when_clicked_after_hidden(self):
        """Main window is shown when the icon is clicked after hidden."""
        self.ui.show_hide()  # hide
        self.ui.show_hide()  # show
        msg = 'main_window should be visible when icon clicked after hidden.'
        self.assertTrue(self.ui.main_window.get_visible(), msg)

    def test_on_status_changed_logs(self):
        """Check _on_status_changed logs properly."""
        args = ('test status', 'status description', True, False, True)
        kwargs = dict(queues='bla', connection=None)
        self.assert_function_logs(logging.getLevelName(logging.DEBUG),
                                  self.ui.on_status_changed, *args, **kwargs)

    def test_on_metadata_ready_logs(self):
        """Check on_metadata_ready logs properly."""
        args = ()
        kwargs = dict(path='test', metadata=True)
        self.assert_function_logs(logging.getLevelName(logging.DEBUG),
                                  self.ui.status.on_metadata_ready,
                                  *args, **kwargs)

    def test_on_initial_data_ready_logs(self):
        """Check on_initial_data_ready logs properly."""
        args = ()
        kwargs = dict(path='test', metadata=True)
        self.assert_function_logs(logging.getLevelName(logging.INFO),
                                  self.ui.on_initial_data_ready,
                                  *args, **kwargs)
