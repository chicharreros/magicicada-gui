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

"""Magicicada GTK UI."""

import gettext
import logging
import os
import sys

# pylint: disable=E0611
from gi.repository import GdkPixbuf, AppIndicator3, Gtk
# pylint: enable=E0611

# optional Launchpad integration, pylint: disable=F0401
# this shouldn't crash if not found as it is simply used for bug reporting
try:
    import LaunchpadIntegration
    LAUNCHPAD_AVAILABLE = True
except ImportError:
    LAUNCHPAD_AVAILABLE = False
# pylint: enable=F0401

INSTALL_KWARGS = {}
if sys.version_info < (3,):
    INSTALL_KWARGS["unicode"] = True

gettext.install('ubuntu-sso-client', **INSTALL_KWARGS)

from magicicada import syncdaemon
from magicicada.helpers import log, NO_OP
from magicicada.gui.gtk.helpers import (
    Buildable,
    build_icon_dict,
    get_data_file,
)
from magicicada.gui.gtk.operations import Operations
from magicicada.gui.gtk.status import Status


logger = logging.getLogger('magicicada.gui.gtk')


# Instance of 'A' has no 'y' member
# pylint: disable=E1101

# Unused argument, we need them for GTK callbacks
# pylint: disable=W0613


class Indicator(object):
    """The indicator."""
    def __init__(self, main_ui):
        self.main_ui = main_ui

        category = AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        icon_name = "icon-idle-16"
        logos_path = os.path.join(get_data_file(), 'media')
        ind = AppIndicator3.Indicator.new("magicicada", icon_name, category)
        ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        ind.set_title("Magicicada")
        ind.set_icon_theme_path(logos_path)
        ind.set_icon(icon_name)
        self.indicator = ind
        self.menu = None
        self.set_menu()

    def set_icon(self, name):
        """Put a proper icon in the systray."""
        full_name = "icon-%s-16" % (name,)
        self.indicator.set_icon(full_name)

    def set_menu(self):
        """Set the menu in the indicator."""
        menu = self._build_menu()
        self.indicator.set_menu(menu)

    def _build_menu(self):
        """Build the menu according to the config."""
        menu = Gtk.Menu()
        accgroup = Gtk.AccelGroup()

        # show / hide
        item = Gtk.ImageMenuItem.new_from_stock("Show / Hide", accgroup)
        menu.append(item)
        item.connect("activate", self._show_hide)
        item.show()

        # about
        item = Gtk.ImageMenuItem.new_from_stock("gtk-about", accgroup)
        menu.append(item)
        item.connect("activate", self._run_about_dialog)
        item.show()

        # quit!
        item = Gtk.ImageMenuItem.new_from_stock("gtk-quit", accgroup)
        menu.append(item)
        item.connect("activate", self.main_ui.on_destroy)
        item.show()

        return menu

    def _run_about_dialog(self, _):
        """Run the About dialog."""
        self.main_ui.on_about_activate(None)

    def _show_hide(self, _):
        """Show or hide the main window.."""
        self.main_ui.show_hide()


class MagicicadaUI(Buildable):
    """Magicicada GUI main class."""

    CURRENT_ROW = '<b><span foreground="#000099">%s</span></b>'
    filename = 'main.ui'
    logger = logger

    def __init__(self, on_destroy=NO_OP):
        """Init."""
        super(MagicicadaUI, self).__init__()
        self.sd = syncdaemon.SyncDaemon()

        if LAUNCHPAD_AVAILABLE:
            # for more information about LaunchpadIntegration:
            # wiki.ubuntu.com/UbuntuDevelopment/Internationalisation/Coding
            helpmenu = self.builder.get_object('helpMenu')
            if helpmenu:
                LaunchpadIntegration.set_sourcepackagename('magicicada')
                LaunchpadIntegration.add_items(helpmenu, 0, False, True)

        self._on_destroy = on_destroy

        active_filename = get_data_file('media', 'active-016.png')
        self.active_indicator = GdkPixbuf.Pixbuf.new_from_file(active_filename)

        self.status = Status(syncdaemon_instance=self.sd, xscale=1, yscale=1)
        self.main_box.pack_start(self.status, expand=False, fill=True,
                                 padding=6)

        self._icons = {}
        for size in (16, 32, 48, 64, 128):
            icon_filename = get_data_file('media', 'logo-%.3i.png' % size)
            self._icons[size] = GdkPixbuf.Pixbuf.new_from_file(icon_filename)
        self.main_window.set_default_icon_list(self._icons.values())
        self.main_window.set_icon_list(self._icons.values())

        self.indicator = Indicator(self)

        about_fname = get_data_file('media', 'logo-128.png')
        self.about_dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file(about_fname))

        self.operations = Operations(syncdaemon_instance=self.sd)
        self.main_box.pack_start(self.operations, expand=True,
                                 fill=True, padding=0)

        self.sd.status_changed_callback = self.on_status_changed
        self.sd.on_initial_data_ready_callback = self.on_initial_data_ready
        self.sd.on_initial_online_data_ready_callback = \
            self.on_initial_online_data_ready

    def destroy(self, *a, **kw):
        """Destroy all widgets."""
        self.main_window.destroy()

    def on_destroy(self, widget=None, data=None):
        """Called when this widget is destroyed."""
        self.sd.shutdown()
        self._on_destroy()

    on_main_window_destroy = on_destroy

    def on_quit_activate(self, widget, data=None):
        """Signal handler for closing the program."""
        self.on_main_window_destroy(self.main_window)

    def on_about_activate(self, widget, data=None):
        """Display the about box."""
        self.about_dialog.run()
        self.about_dialog.hide()

    def show_hide(self):
        """Show or hide the main window.."""
        if self.main_window.get_visible():
            self.main_window.hide()
        else:
            self.main_window.show()

    @log(logger)
    def on_status_changed(self, *args, **kwargs):
        """Callback'ed when the SD status changed."""
        self.status.update(*args, **kwargs)

        # change status icon
        state = kwargs.get('state')
        if state == syncdaemon.STATE_IDLE:
            self.indicator.set_icon('idle')
        elif state == syncdaemon.STATE_WORKING:
            self.indicator.set_icon('working')
        else:
            self.indicator.set_icon('alert')

    @log(logger, level=logging.INFO)
    def on_initial_data_ready(self):
        """Initial data is now available in syncdaemon."""
        self.status.on_initial_data_ready()
        self.operations.load()

    @log(logger, level=logging.INFO)
    def on_initial_online_data_ready(self):
        """Online initial data is now available in syncdaemon."""
        self.status.on_initial_online_data_ready()
