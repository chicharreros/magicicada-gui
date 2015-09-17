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

"""The backend that communicates Magicicada with the SyncDaemon."""

import logging
import os
import re
import user

from twisted.internet import defer, reactor

from magicicada.dbusiface import (
    DBusInterface,
    FolderOperationError,
    NOT_SYNCHED_PATH,
    ShareOperationError,
)
from magicicada.helpers import NO_OP
from magicicada.queue_content import QueueContent, NODE_OP, INTERNAL_OP

# log!
logger = logging.getLogger('magicicada.syncdaemon')

# states for MQ and CQ handling bursts
ASKING_IDLE, ASKING_YES, ASKING_LATER = range(3)

# interval to poll for transfer progress
TRANSFER_POLL_INTERVAL = 5

# status of the node
CHANGED_LOCAL = u"UPLOADING"
CHANGED_NONE = u"SYNCHRONIZED"
CHANGED_SERVER = u"DOWNLOADING"

# state of SD
STATE_CONNECTING = u"CONNECTING"
STATE_DISCONNECTED = u"DISCONNECTED"
STATE_IDLE = u"IDLE"
STATE_STARTING = u"STARTING"
STATE_STOPPED = u"STOPPED"
STATE_WORKING = u"WORKING"


def mandatory_callback(function_name):
    """Log that the callback was not overwritten."""

    def f(*a, **k):
        """Fake callback."""
        logger.warning("Callback called but was not assigned! "
                       "%r called with %s %s", function_name, a, k)
    return f


class State(object):
    """Hold the state of SD."""

    _attrs = {'name', 'description', 'is_error', 'is_connected',
              'is_online', 'queues', 'connection', 'is_started', 'state'}
    _toshow = ['name', 'is_error', 'is_connected',
               'is_online', 'queues', 'connection', 'is_started', 'state']

    def __init__(self):
        # starting defaults
        self.name = ''
        self.description = ''
        self.is_error = False
        self.is_connected = False
        self.is_online = False
        self.queues = ''
        self.connection = ''
        self.is_started = False
        self.state = STATE_STOPPED

    def __getattribute__(self, name):
        """Return the value if there."""
        if name[0] == "_" or name == 'set':
            return object.__getattribute__(self, name)
        else:
            return self.__dict__[name]

    def set(self, **data):
        """Set the attributes from data, if allowed."""
        for name, value in data.iteritems():
            if name not in self._attrs:
                raise AttributeError("Name not in _attrs: %r" % name)
            self.__dict__[name] = value

    def __str__(self):
        """String representation."""
        result = []
        for attr in self._attrs:
            result.append("%s=%s" % (attr, getattr(self, attr)))
        return "<State %s>" % ", ".join(result)
    __repr__ = __str__


class Poller(object):
    """Object that executes a callback periodically."""

    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self._call = None
        self._inside_call = False
        self._should_run = False

    @defer.inlineCallbacks
    def _execute(self):
        """Execute the callback and go again."""
        self._inside_call = True
        yield self.callback()
        self._inside_call = False

        # if wasn't stopped in the middle, keep polling
        if self._should_run:
            self._call = reactor.callLater(self.interval, self._execute)

    def run(self, should_run):
        """Stop or start the poller."""
        self._should_run = should_run
        if should_run:
            # call later if don't have an active one and not in the middle
            # of being executing the callback
            if self._call is None or not self._call.active():
                if not self._inside_call:
                    self._call = reactor.callLater(self.interval,
                                                   self._execute)
        else:
            # cancel the polling call
            if self._call is not None and self._call.active():
                self._call.cancel()


class SyncDaemon(object):
    """Interface to Ubuntu One's SyncDaemon."""

    def __init__(self, dbus_class=DBusInterface):
        logger.info("SyncDaemon interface started!")

        # set up dbus and related stuff
        self.dbus = dbus_class(self)

        # attributes for GUI, definition and filling
        self.current_state = State()
        self.folders = None
        self.shares_to_me = None
        self.shares_to_others = None
        self.public_files = None
        self.queue_content = QueueContent(home=user.home)

        # callbacks for GUI to hook in
        self.status_changed_callback = NO_OP
        self.on_started_callback = NO_OP
        self.on_stopped_callback = NO_OP
        self.on_connected_callback = NO_OP
        self.on_disconnected_callback = NO_OP
        self.on_online_callback = NO_OP
        self.on_offline_callback = NO_OP
        self.on_folders_changed_callback = NO_OP
        self.on_shares_to_me_changed_callback = NO_OP
        self.on_shares_to_others_changed_callback = NO_OP
        self.on_public_files_changed_callback = NO_OP
        self.on_metadata_ready_callback = mandatory_callback(
            'on_metadata_ready_callback')
        self.on_initial_data_ready_callback = NO_OP
        self.on_initial_online_data_ready_callback = NO_OP
        self.on_share_op_error_callback = mandatory_callback(
            'on_share_op_error_callback')
        self.on_folder_op_error_callback = mandatory_callback(
            'on_folder_op_error_callback')
        self.on_public_op_error_callback = mandatory_callback(
            'on_public_op_error_callback')
        self.on_node_ops_changed_callback = NO_OP
        self.on_internal_ops_changed_callback = NO_OP
        self.on_transfers_callback = NO_OP

        # poller
        self.transfers_poller = Poller(TRANSFER_POLL_INTERVAL,
                                       self.get_current_transfers)
        self._check_started()

    @defer.inlineCallbacks
    def _check_started(self):
        """Check if started and load initial data if yes."""
        # load initial data if ubuntuone-client already started
        started = yield self.dbus.is_sd_started()
        if started:
            self.current_state.set(is_started=True)
            self._get_initial_data()
        else:
            self.current_state.set(is_started=False)

    def shutdown(self):
        """Shut down the SyncDaemon."""
        logger.info("SyncDaemon interface going down")
        self.transfers_poller.run(False)
        self.dbus.shutdown()

    @defer.inlineCallbacks
    def get_current_transfers(self):
        """Get downloads and uploads."""
        uploads = yield self.dbus.get_current_uploads()
        downloads = yield self.dbus.get_current_downloads()
        self.on_transfers_callback(uploads + downloads)

    @defer.inlineCallbacks
    def _get_initial_data(self):
        """Get the initial SD data."""
        logger.info("Getting offline initial data")

        status_data = yield self.dbus.get_status()
        self._send_status_changed(*status_data)

        # queue content stuff
        shares_real_dir = yield self.dbus.get_real_shares_dir()
        shares_link_dir = yield self.dbus.get_link_shares_dir()
        self.queue_content.set_shares_dirs(shares_link_dir, shares_real_dir)
        content = yield self.dbus.get_queue_content()
        self.queue_content.set_content(content)
        self.transfers_poller.run(self.queue_content.transferring)

        self.folders = yield self.dbus.get_folders()

        self.shares_to_me = yield self.dbus.get_shares_to_me()
        self.shares_to_others = yield self.dbus.get_shares_to_others()

        # let frontend know that we have all the initial offline data
        logger.info("All initial offline data is ready")
        self.on_initial_data_ready_callback()

        logger.info("Getting online initial data")
        self.public_files = yield self.dbus.get_public_files()

        # let frontend know that we have all the initial online data
        logger.info("All initial online data is ready")
        self.on_initial_online_data_ready_callback()

    @defer.inlineCallbacks
    def on_sd_public_files_changed(self, pf=None, is_public=False):
        """Update the Public Files list."""
        data = yield self.dbus.get_public_files()
        logger.info("Got new Public Files list (%d items)", len(data))
        self.public_files = data
        self.on_public_files_changed_callback(self.public_files)

    @defer.inlineCallbacks
    def on_sd_shares_changed(self):
        """Shares changed, ask for new information."""
        logger.info("SD Shares changed")

        # to me
        new_to_me = yield self.dbus.get_shares_to_me()
        if new_to_me != self.shares_to_me:
            self.shares_to_me = new_to_me
            self.on_shares_to_me_changed_callback(new_to_me)

        # to others
        new_to_others = yield self.dbus.get_shares_to_others()
        if new_to_others != self.shares_to_others:
            self.shares_to_others = new_to_others
            self.on_shares_to_others_changed_callback(new_to_others)

    @defer.inlineCallbacks
    def on_sd_folders_changed(self):
        """Folders changed, ask for new information."""
        logger.info("SD Folders changed")
        self.folders = yield self.dbus.get_folders()
        self.on_folders_changed_callback(self.folders)

    def on_sd_status_changed(self, *status_data):
        """The Status of SD changed.."""
        logger.info("SD Status changed")
        self._send_status_changed(*status_data)

    def _send_status_changed(self, name, description, is_error, is_connected,
                             is_online, queues, connection):
        """Send status changed signal."""
        kwargs = dict(name=name, description=description,
                      is_error=is_error, is_connected=is_connected,
                      is_online=is_online, queues=queues,
                      connection=connection)

        # check status changes to call other callbacks
        if is_connected and not self.current_state.is_connected:
            self.on_connected_callback()
        if not is_connected and self.current_state.is_connected:
            self.on_disconnected_callback()
        if is_online and not self.current_state.is_online:
            self.on_online_callback()
        if not is_online and self.current_state.is_online:
            self.on_offline_callback()

        # state of SD
        if name == "SHUTDOWN":
            state = STATE_STOPPED
            self.current_state.set(is_started=False)
            self.on_stopped_callback()
        elif name in ('READY', 'WAITING'):
            if connection == 'With User With Network':
                state = STATE_CONNECTING
            else:
                state = STATE_DISCONNECTED
        elif name == 'STANDOFF':
            state = STATE_DISCONNECTED
        else:
            if is_connected:
                if name == "QUEUE_MANAGER":
                    if queues == "IDLE":
                        state = STATE_IDLE
                    else:
                        state = STATE_WORKING
                else:
                    state = STATE_CONNECTING
            else:
                state = STATE_STARTING
                # check if it's the first time we flag starting
                if self.current_state.state != STATE_STARTING:
                    self.current_state.set(is_started=True)
                    self.on_started_callback()
                    self._get_initial_data()
        kwargs['state'] = state
        xs = sorted(kwargs.iteritems())
        logger.debug("    new status: %s", ', '.join('%s=%r' % i for i in xs))

        # set current state to new values and call status changed cb
        self.current_state.set(**kwargs)
        self.status_changed_callback(**kwargs)

    def on_sd_queue_added(self, op_name, op_id, op_data):
        """A command was added to the Request Queue."""
        logger.info("Queue content: added %r [%s] %s", op_name, op_id, op_data)
        r = self.queue_content.add(op_name, op_id, op_data)
        if r == NODE_OP:
            self.on_node_ops_changed_callback(self.queue_content.node_ops)
        elif r == INTERNAL_OP:
            self.on_internal_ops_changed_callback(
                self.queue_content.internal_ops)
        self.transfers_poller.run(self.queue_content.transferring)

    def on_sd_queue_removed(self, op_name, op_id, op_data):
        """A command was removed from the Request Queue."""
        logger.info("Queue content: removed %r [%s] %s",
                    op_name, op_id, op_data)
        r = self.queue_content.remove(op_name, op_id, op_data)
        if r == NODE_OP:
            self.on_node_ops_changed_callback(self.queue_content.node_ops)
        elif r == INTERNAL_OP:
            self.on_internal_ops_changed_callback(
                self.queue_content.internal_ops)
        self.transfers_poller.run(self.queue_content.transferring)

    def start(self):
        """Start the SyncDaemon."""
        logger.info("Starting u1.SD")
        d = self.dbus.start()
        self._get_initial_data()
        return d

    def quit(self):
        """Stop the SyncDaemon and makes it quit."""
        logger.info("Stopping u1.SD")
        return self.dbus.quit()

    def connect(self):
        """Tell the SyncDaemon that the user wants it to connect."""
        logger.info("Telling u1.SD to connect")
        return self.dbus.connect()

    def disconnect(self):
        """Tell the SyncDaemon that the user wants it to disconnect."""
        logger.info("Telling u1.SD to disconnect")
        return self.dbus.disconnect()

    @defer.inlineCallbacks
    def get_metadata(self, path):
        """Get the metadata for given path."""
        resp = yield self.dbus.get_metadata(os.path.realpath(path))
        if resp == NOT_SYNCHED_PATH:
            self.on_metadata_ready_callback(path, resp)
            return

        # have data! store it in raw, and process some
        result = dict(raw_result=resp)

        # stat
        if resp['stat'] == u'None':
            stat = None
        else:
            items = re.match(".*\((.*)\)", resp['stat']).groups()[0]
            items = [x.split("=") for x in items.split(", ")]
            stat = dict((a, int(b[:-1] if b[-1] == 'L' else b))
                        for a, b in items)
        result['stat'] = stat

        # changed
        is_partial = resp['info_is_partial'] != u'False'
        if resp['local_hash'] == resp['server_hash']:
            if is_partial:
                logger.warning("Bad 'changed' values: %r", resp)
                changed = None
            else:
                changed = CHANGED_NONE
        else:
            if is_partial:
                changed = CHANGED_SERVER
            else:
                changed = CHANGED_LOCAL
        result['changed'] = changed

        # path
        processed_path = resp['path']
        if processed_path.startswith(user.home):
            processed_path = "~" + processed_path[len(user.home):]
        result['path'] = processed_path

        self.on_metadata_ready_callback(path, result)

    @defer.inlineCallbacks
    def get_free_space(self, volume_id):
        """Get the free space for a volume."""
        free_space = yield self.dbus.get_free_space(volume_id)
        defer.returnValue(int(free_space))

    def _answer_share(self, share_id, method, action_name):
        """Effectively accept or reject a share."""
        def error(failure):
            """Operation failed."""
            if failure.check(ShareOperationError):
                error = failure.value.error
                logger.info("%s share %s finished with error: %s",
                            action_name, share_id, error)
                self.on_share_op_error_callback(share_id, error)
            else:
                logger.error("Unexpected error when %s share %s: %s %s",
                             action_name.lower(), share_id,
                             failure.type, failure.value)

        def success(_):
            """Operation finished ok."""
            logger.info("%s share %s finished successfully",
                        action_name, share_id)

        logger.info("%s share %s started", action_name, share_id)
        d = method(share_id)
        d.addCallbacks(success, error)

    def accept_share(self, share_id):
        """Accept a share."""
        self._answer_share(share_id, self.dbus.accept_share, "Accepting")

    def reject_share(self, share_id):
        """Reject a share."""
        self._answer_share(share_id, self.dbus.reject_share, "Rejecting")

    def subscribe_share(self, share_id):
        """Subscribe a share."""
        self._answer_share(share_id, self.dbus.subscribe_share, "Subscribing")

    def unsubscribe_share(self, share_id):
        """Unsubscribe a share."""
        self._answer_share(share_id, self.dbus.unsubscribe_share,
                           "Unsubscribing")

    def send_share_invitation(self, path, mail_address, sh_name, access_level):
        """Send a share invitation."""
        def error(failure):
            """Operation failed."""
            if failure.check(ShareOperationError):
                error = failure.value.error
                logger.info("Sending share invitation finished with error %s "
                            "(path=%r mail_address=%s share_name=%r "
                            "access_level=%s)", error, path, mail_address,
                            sh_name, access_level)
            else:
                logger.error("Unexpected error when sending share invitation "
                             "%s %s (path=%r mail_address=%s share_name=%r "
                             "access_level=%s)", failure.type, failure.value,
                             path, mail_address, sh_name, access_level)

        def success(_):
            """Operation finished ok."""
            logger.info("Sending share invitation finished successfully "
                        "(path=%r mail_address=%s share_name=%r "
                        "access_level=%s", path, mail_address,
                        sh_name, access_level)

        logger.info("Sending share invitation: path=%r mail_address=%s "
                    "share_name=%r access_level=%s", path, mail_address,
                    sh_name, access_level)
        d = self.dbus.send_share_invitation(path, mail_address,
                                            sh_name, access_level)
        d.addCallbacks(success, error)

    @defer.inlineCallbacks
    def _folder_operation(self, operation, value, op_name):
        """Generic folder operation."""
        try:
            result = yield operation(value)
        except FolderOperationError, e:
            logger.info("%s folder (on %r) finished with error: %s",
                        op_name, value, e)
            self.on_folder_op_error_callback(e)
        else:
            vol = result.volume
            path = result.path
            logger.info("%s folder ok: volume=%s path=%r", op_name, vol, path)
            self.folders = yield self.dbus.get_folders()

    def create_folder(self, path):
        """Create a folder."""
        return self._folder_operation(self.dbus.create_folder, path, "Create")

    def delete_folder(self, volume_id):
        """Delete a folder."""
        return self._folder_operation(self.dbus.delete_folder,
                                      volume_id, "Delete")

    def subscribe_folder(self, volume_id):
        """Subscribe a folder."""
        return self._folder_operation(self.dbus.subscribe_folder,
                                      volume_id, "Subscribe")

    def unsubscribe_folder(self, volume_id):
        """Unsubscribe a folder."""
        return self._folder_operation(self.dbus.unsubscribe_folder,
                                      volume_id, "Unsubscribe")

    @defer.inlineCallbacks
    def change_public_access(self, path, is_public):
        """Set a file public or not."""
        try:
            result = yield self.dbus.change_public_access(path, is_public)
        except StandardError, e:
            logger.info("Change public access (on %r) finished with error: "
                        "%s (%s)", path, e.__class__.__name__, e)
            self.on_public_op_error_callback(e)
        else:
            url = result['public_url']
            logger.info("Change public access ok: path=%r is_public=%s url=%r",
                        path, is_public, url)

    def on_sd_upload_progress(self, transfer):
        """Tell the GUI that an upload is progressing."""
        self.on_transfers_callback([transfer])

    def on_sd_download_progress(self, transfer):
        """Tell the GUI that a download is progressing."""
        self.on_transfers_callback([transfer])
