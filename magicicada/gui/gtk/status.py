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

"""Magicicada Status widget."""

import logging
import os
import time

from twisted.internet import defer

# pylint: disable=E0611
from gi.repository import Gtk
# pylint: enable=E0611

from magicicada import syncdaemon
from magicicada.dbusiface import NOT_SYNCHED_PATH
from magicicada.helpers import log, humanize_bytes
from magicicada.gui.gtk.helpers import Buildable, build_icon_dict
from magicicada.gui.gtk.listings import (
    FoldersButton,
    PublicFilesButton,
    SharesToMeButton,
    SharesToOthersButton,
)

# pylint: disable=E0602

UBUNTU_ONE_ROOT = os.path.expanduser(u'~/Ubuntu One')

CONNECT = _(u'Connect')
CONNECTED = _(u'Connected')
CONNECTING = _(u'Connecting')
DISCONNECT = _(u'Disconnect')
DISCONNECTED = _(u'Disconnected')
DISCONNECTING = _(u'Disconnecting')
ERROR = _(u'Oops!')
IDLE = _(u'All done!')
START = _(u'Start')
STARTED = _(u'Started')
STARTING = _(u'Starting')
STOP = _(u'Stop')
STOPPED = _(u'Not running')
STOPPING = _(u'Stopping')
WORKING = _(u'Working')

logger = logging.getLogger('magicicada.gui.gtk.status')

ACTION_MAP = {
    syncdaemon.STATE_CONNECTING: (CONNECTING, DISCONNECT),
    syncdaemon.STATE_DISCONNECTED: (DISCONNECTED, CONNECT),
    syncdaemon.STATE_IDLE: (IDLE, DISCONNECT),
    syncdaemon.STATE_STARTING: (STARTING, STOP),
    syncdaemon.STATE_STOPPED: (STOPPED, START),
    syncdaemon.STATE_WORKING: (WORKING, DISCONNECT),
}


class MetadataDialog(Buildable):
    """The metadata dialog."""

    filename = 'metadata.ui'

    changed_message = {
        syncdaemon.CHANGED_NONE: (u'Synchronized', Gtk.STOCK_APPLY),
        syncdaemon.CHANGED_SERVER: (u'With server changes, downloading',
                                    Gtk.STOCK_GO_DOWN),
        syncdaemon.CHANGED_LOCAL: (u'With local changes, uploading',
                                   Gtk.STOCK_GO_UP),
    }

    def run(self):
        """Run the dialog."""
        self.dialog.show()

    def got_metadata(self, path, data):
        """Activate the information elements and hide the spinner."""
        # stop and hide the spinner
        self.spinner.stop()
        self.spinner.hide()

        # title with crude path
        self.dialog.set_title("Metadata for %s" % (path,))

        # the icon is taken from crude path, no matter if synched or not
        if os.path.isdir(path):
            icon = Gtk.STOCK_DIRECTORY
        else:
            icon = Gtk.STOCK_FILE
        self.filetype_image.set_from_stock(icon, Gtk.IconSize.MENU)

        # set the data in the elements
        if data == NOT_SYNCHED_PATH:
            # metadata path doesn't exist for syncdaemon, show crude path,
            # error message, and quit
            self.path_label.set_text(path)
            self.filepath_hbox.show()
            self.basic_info_label.set_text(NOT_SYNCHED_PATH)
            self.basic_info_label.show()
            return

        # show the nice path
        self.path_label.set_text(data['path'])
        self.filepath_hbox.show()

        # prepare simple text
        simple = []
        stat = data['stat']
        if stat is not None:
            size = stat['st_size']
            try:
                size = humanize_bytes(size)
            except (ValueError, TypeError):
                logger.exception('Error while humanizing bytes')
            simple.append("Size: %s" % (size,))
            tstamp = stat['st_mtime']
            simple.append("Modified on %s" % (time.ctime(tstamp),))

        # set state message and image
        state, stock = self.changed_message.get(data['changed'],
                                                ('Unknown state', None))
        simple.append(state)
        simple_text = "\n".join(simple)
        if stock is None:
            self.state_image.hide()
        else:
            self.state_image.set_from_stock(stock, Gtk.IconSize.LARGE_TOOLBAR)
        self.state_hbox.show()

        # prepare detailed text
        raw = data['raw_result']
        detailed_text = '\n'.join('%s: %s' % i for i in raw.iteritems())

        # fill and show
        self.basic_info_label.set_text(simple_text)
        self.basic_info_label.show()
        self.detailed_info_textview.get_buffer().set_text(detailed_text)
        self.details_expander.show()

    def on_dialog_close(self, widget, data=None):
        """Close the dialog."""
        self.dialog.hide()

    def destroy(self):
        """Destroy this widget's dialog."""
        self.dialog.destroy()


class Status(Buildable, Gtk.Alignment):
    """The toolbar with info."""

    filename = 'status.ui'
    logger = logger
    _u1_root = UBUNTU_ONE_ROOT

    def __init__(self, syncdaemon_instance=None, **kwargs):
        """Init."""
        Buildable.__init__(self)
        Gtk.Alignment.__init__(self, **kwargs)

        if syncdaemon_instance is not None:
            self.sd = syncdaemon_instance
        else:
            self.sd = syncdaemon.SyncDaemon()
        self.sd.on_metadata_ready_callback = self.on_metadata_ready

        self._sd_actions = {
            CONNECT: (self.sd.connect, DISCONNECT),
            DISCONNECT: (self.sd.disconnect, CONNECT),
            START: (self.sd.start, STOP),
            STOP: (self.sd.quit, START),
        }
        self._metadata_dialogs = {}
        self._status_images = build_icon_dict(48)

        folders = FoldersButton(syncdaemon_instance=self.sd)
        shares_to_me = SharesToMeButton(syncdaemon_instance=self.sd)
        shares_to_others = SharesToOthersButton(syncdaemon_instance=self.sd)
        self.public_files = PublicFilesButton(syncdaemon_instance=self.sd)

        buttons = (folders, shares_to_me, shares_to_others, self.public_files)
        for button in buttons:
            self.toolbar.insert(button, -1)
        self.toolbar.set_sensitive(False)

        self.action_button.set_use_stock(True)

        self.update()

        self.add(self.info)
        self.show_all()

    # custom

    def _update_action_button(self, action):
        """Update the action button according to the SD state."""
        self.action_button.set_label(action)
        self.action_button.set_sensitive(True)

    # GTK callbacks

    @defer.inlineCallbacks
    def on_action_button_clicked(self, button):
        """An action was clicked by the user."""
        self.action_button.set_sensitive(False)

        sd_action, next_action = self._sd_actions[button.get_label()]
        yield sd_action()

        self._update_action_button(next_action)

    def on_metadata_clicked(self, widget, data=None):
        """Show metadata for a path choosen by the user."""
        res = self.file_chooser.run()
        self.file_chooser.hide()
        if res != Gtk.FileChooserAction.OPEN:
            return

        path = self.file_chooser.get_filename()
        assert path is not None

        dialog = MetadataDialog()
        self._metadata_dialogs[path] = dialog
        self.sd.get_metadata(path)
        dialog.run()

    def on_file_chooser_open_clicked(self, widget, data=None):
        """Close the file_chooser dialog."""
        self.file_chooser.response(Gtk.FileChooserAction.OPEN)

    def on_file_chooser_show(self, widget, data=None):
        """Close the file_chooser dialog."""
        self.file_chooser.set_current_folder(self._u1_root)

    # SyncDaemon callbacks

    @log(logger, level=logging.INFO)
    def on_initial_data_ready(self):
        """Initial data is now available in syncdaemon."""
        self.toolbar.set_sensitive(True)
        self.public_files.set_sensitive(False)

    @log(logger, level=logging.INFO)
    def on_initial_online_data_ready(self):
        """Online initial data is now available in syncdaemon."""
        self.public_files.set_sensitive(True)

    @log(logger)
    def on_metadata_ready(self, path, metadata):
        """Lower layer has the requested metadata for 'path'."""
        if path not in self._metadata_dialogs:
            logger.info("on_metadata_ready: path %r not in stored paths!",
                        path)
            return

        dialog = self._metadata_dialogs[path]
        dialog.got_metadata(path, metadata)

    def update(self, *args, **kwargs):
        """Update UI based on SD current state."""
        current_state = self.sd.current_state
        logger.debug('updating UI with state %r', current_state)

        state = current_state.state
        status, next_action = ACTION_MAP[state]
        if state == syncdaemon.STATE_IDLE:
            self.status_image.set_from_pixbuf(self._status_images['idle'])
        elif state in (syncdaemon.STATE_CONNECTING, syncdaemon.STATE_STARTING,
                       syncdaemon.STATE_WORKING):
            self.status_image.set_from_pixbuf(self._status_images['working'])
        else:
            self.status_image.set_from_pixbuf(self._status_images['alert'])

        self._update_action_button(next_action)
        self.status_label.set_text(status)
