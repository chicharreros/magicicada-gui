#
# Author: Facundo Batista <facundo@taniquetil.com.ar>
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

"""The DBus Interface."""

import collections
import logging

import dbus
from dbus import SessionBus
from dbus.mainloop.glib import DBusGMainLoop
from twisted.internet import defer

# yes, they can be imported! pylint: disable=F0401,E0611
from ubuntuone.platform.tools import SyncDaemonTool, is_already_running

# log!
logger = logging.getLogger('magicicada.dbusiface')

# we use here camel case names, because this variables are used later as
# classes, so pylint: disable=C0103
FolderData = collections.namedtuple(
    'FolderData', 'node path suggested_path subscribed volume')
ShareData = collections.namedtuple(
    'ShareData', 'accepted access_level free_bytes name node_id '
                 'other_username other_visible_name path volume_id subscribed')
PublicFilesData = collections.namedtuple(
    'PublicFilesData', 'volume node path public_url')
Transfer = collections.namedtuple('Transfer', 'path transfered total')


# DBus exceptions store the type inside, as a string :|
DBUSERR_NOREPLY = 'org.freedesktop.DBus.Error.NoReply'
DBUSERR_PYKEYERROR = 'org.freedesktop.DBus.Python.KeyError'

# some constants
NOT_SYNCHED_PATH = "Not a valid path!"


class ShareOperationError(Exception):
    """Error on an operation on a share."""
    def __init__(self, share_id=None, error=None):
        self.share_id = share_id
        self.error = error
        super(ShareOperationError, self).__init__(error)


class FolderOperationError(Exception):
    """Error on an operation on a folder.

    The 'path' will be present on a CreateFolder error, in the rest of
    operations the volume_id will be the identificator.
    """
    def __init__(self, path=None, volume_id=None, error=None):
        self.path = path
        self.volume_id = volume_id
        self.error = error
        super(FolderOperationError, self).__init__(error)


def _is_retry_exception(err):
    """Check if the exception is a retry one."""
    if isinstance(err, dbus.exceptions.DBusException):
        if err.get_dbus_name() == DBUSERR_NOREPLY:
            return True
    return False


def retryable(func):
    """Call the function until its deferred succeed (max 5 times)."""

    @defer.inlineCallbacks
    def f(*a, **k):
        """Built func."""
        opportunities = 10
        while opportunities:
            try:
                res = yield func(*a, **k)
            except Exception, err:  # pylint: disable=W0703
                opportunities -= 1
                if opportunities == 0 or not _is_retry_exception(err):
                    raise
            else:
                break
        defer.returnValue(res)

    return f


class DBusInterface(object):
    """The DBus Interface to Ubuntu One's SyncDaemon."""

    def __init__(self, msd):
        # magicicada's syncdaemon
        self.msd = msd
        logger.info("DBus interface starting")
        self._public_files_deferred = None

        # set up dbus and related stuff
        loop = DBusGMainLoop(set_as_default=True)
        self._bus = bus = SessionBus(mainloop=loop)
        self.sync_daemon_tool = SyncDaemonTool(bus)

        # hook up for signals and store info for the shutdown
        _signals = [
            (self._on_status_changed, 'Status', 'StatusChanged'),
            (self._on_queue_added, 'Status', 'RequestQueueAdded'),
            (self._on_queue_removed, 'Status', 'RequestQueueRemoved'),
            (self._on_upload_progress, 'Status', 'UploadFileProgress'),
            (self._on_download_progress, 'Status', 'DownloadFileProgress'),
            (self._on_folder_created, 'Folders', 'FolderCreated'),
            (self._on_folder_deleted, 'Folders', 'FolderDeleted'),
            (self._on_folder_subscribed, 'Folders', 'FolderSubscribed'),
            (self._on_folder_unsubscribed, 'Folders', 'FolderUnSubscribed'),
            (self._on_share_created, 'Shares', 'ShareCreated'),
            (self._on_share_deleted, 'Shares', 'ShareDeleted'),
            (self._on_share_changed, 'Shares', 'ShareChanged'),
            (self._on_public_files_changed, 'PublicFiles',
                                            'PublicAccessChanged'),
        ]
        self._dbus_matches = []
        for method, dbus_lastname, signal_name in _signals:
            if dbus_lastname is None:
                dbus_interface = None
            else:
                dbus_interface = 'com.ubuntuone.SyncDaemon.' + dbus_lastname
            match = bus.add_signal_receiver(method,
                                            dbus_interface=dbus_interface,
                                            signal_name=signal_name)
            self._dbus_matches.append((match, dbus_interface, signal_name))

    def shutdown(self):
        """Shut down the SyncDaemon."""
        logger.info("DBus interface going down")

        # remove the signals from DBus
        remove = self._bus.remove_signal_receiver
        for match, dbus_interface, signal in self._dbus_matches:
            remove(match, dbus_interface=dbus_interface, signal_name=signal)

    def _process_status(self, state):
        """Transform status information."""
        name = state['name']
        description = state['description']
        is_error = bool(state['is_error'])
        is_connected = bool(state['is_connected'])
        is_online = bool(state['is_online'])
        queues = state['queues']
        connection = state['connection']
        return (name, description, is_error, is_connected,
                is_online, queues, connection)

    @retryable
    def get_status(self):
        """Get SD status."""
        logger.info("Getting status")
        d = self.sync_daemon_tool.get_status()
        d.addCallback(self._process_status)
        return d

    @retryable
    @defer.inlineCallbacks
    def get_free_space(self, volume_id):
        """Get the free space for a volume."""
        result = yield self.sync_daemon_tool.free_space(volume_id)
        logger.info("Free space for volume %r is %r", volume_id, result)
        defer.returnValue(result)

    @retryable
    @defer.inlineCallbacks
    def get_real_shares_dir(self):
        """Get the real directory for the shares."""
        result = yield self.sync_daemon_tool.get_shares_dir()
        logger.info("Real shares dir: %r", result)
        defer.returnValue(result)

    @retryable
    @defer.inlineCallbacks
    def get_link_shares_dir(self):
        """Get the link directory for the shares."""
        result = yield self.sync_daemon_tool.get_shares_dir_link()
        logger.info("Link shares dir: %r", result)
        defer.returnValue(result)

    def _process_transfers(self, transfers, progress):
        """Process downloads or uploads to keep useful info only."""
        r = [Transfer(t['path'], int(t[progress]), int(t['deflated_size']))
             for t in transfers if 'deflated_size' in t]
        return r

    @retryable
    @defer.inlineCallbacks
    def get_current_downloads(self):
        """Get the current_downloads."""
        result = yield self.sync_daemon_tool.get_current_downloads()
        processed = self._process_transfers(result, 'n_bytes_read')
        logger.info("Get current downloads: %d items", len(processed))
        defer.returnValue(processed)

    @retryable
    @defer.inlineCallbacks
    def get_current_uploads(self):
        """Get the current_uploads."""
        result = yield self.sync_daemon_tool.get_current_uploads()
        processed = self._process_transfers(result, 'n_bytes_written')
        logger.info("Get current uploads: %d items", len(processed))
        defer.returnValue(processed)

    def _on_status_changed(self, state):
        """Call the SD callback."""
        logger.info("Received Status changed")
        logger.debug("Status changed data: %r", state)
        data = self._process_status(state)
        self.msd.on_sd_status_changed(*data)

    def _on_queue_added(self, op_name, op_id, op_data):
        """Call the SD callback."""
        logger.debug("Received Queue added: %r [%s] %s",
                     op_name, op_id, op_data)
        self.msd.on_sd_queue_added(op_name, op_id, op_data)

    def _on_queue_removed(self, op_name, op_id, op_data):
        """Call the SD callback."""
        logger.debug("Received Queue removed: %r [%s] %s",
                     op_name, op_id, op_data)
        self.msd.on_sd_queue_removed(op_name, op_id, op_data)

    def _on_upload_progress(self, path, op_data):
        """Call the SD callback."""
        logger.debug("Received Upload progress: %r %s", path, op_data)
        transf = Transfer(path, int(op_data['n_bytes_written']),
                          int(op_data['deflated_size']))
        self.msd.on_sd_upload_progress(transf)

    def _on_download_progress(self, path, op_data):
        """Call the SD callback."""
        logger.debug("Received Download progress: %r %s", path, op_data)
        transf = Transfer(path, int(op_data['n_bytes_read']),
                          int(op_data['deflated_size']))
        self.msd.on_sd_download_progress(transf)

    def _on_folder_created(self, _):
        """Call the SD callback."""
        logger.info("Received Folder created")
        self.msd.on_sd_folders_changed()

    def _on_folder_deleted(self, _):
        """Call the SD callback."""
        logger.info("Received Folder deleted")
        self.msd.on_sd_folders_changed()

    def _on_folder_subscribed(self, _):
        """Call the SD callback."""
        logger.info("Received Folder subscribed")
        self.msd.on_sd_folders_changed()

    def _on_folder_unsubscribed(self, _):
        """Call the SD callback."""
        logger.info("Received Folder unsubscribed")
        self.msd.on_sd_folders_changed()

    def _on_share_created(self, _):
        """Call the SD callback."""
        logger.info("Received Share created")
        self.msd.on_sd_shares_changed()

    def _on_share_deleted(self, _):
        """Call the SD callback."""
        logger.info("Received Share deleted")
        self.msd.on_sd_shares_changed()

    def _on_share_changed(self, _):
        """Call the SD callback."""
        logger.info("Received Share changed")
        self.msd.on_sd_shares_changed()

    def _on_public_files_changed(self, data):
        """Call the SD callback."""
        logger.debug("Received Public Files changed: %s", data)
        pf = PublicFilesData(volume=data['share_id'], node=data['node_id'],
                             path=data['path'], public_url=data['public_url'])
        is_public = bool(data['is_public'])
        self.msd.on_sd_public_files_changed(pf, is_public)

    def _on_public_files_list(self, data):
        """Call the SD callback."""
        logger.info("Received Public Files list (%d)", len(data))
        processed = []
        for d in data:
            logger.debug("    Public Files data: %s", d)
            p = PublicFilesData(volume=d['volume_id'], node=d['node_id'],
                                path=d['path'], public_url=d['public_url'])
            processed.append(p)

        return processed

    @defer.inlineCallbacks
    def get_public_files(self):
        """Ask the Public Files info to syncdaemon."""
        try:
            result = yield self.sync_daemon_tool.get_public_files()
            logger.debug("Public files asked ok.")
        except AttributeError:
            logger.warning('Method sdtool.get_public_files is not available, '
                           'trying old one directly from dbus.')
            result = yield self.get_public_files_old()
        except:
            logger.exception("Public files finished with error:")
            result = []

        defer.returnValue(self._on_public_files_list(result))

    def get_public_files_old(self):
        """Ask the Public Files info to syncdaemon (old approach)."""
        # yes, they can be imported! pylint: disable=F0401,E0611,W0404
        from ubuntuone.platform.tools import DBusClient, ErrorSignal
        from ubuntuone.platform.dbus_interface import \
            DBUS_IFACE_PUBLIC_FILES_NAME
        client = DBusClient(self._bus, '/publicfiles',
                            DBUS_IFACE_PUBLIC_FILES_NAME)

        # note that these callbacks do not come with the requested info, the
        # method just will return None, and the real info will come later
        # in a signal

        def call_done(result):
            """Call was succesful."""
            logger.debug("Public files asked ok.")

        def call_error(error):
            """Call was not succesful."""
            logger.error("Public files asked with error: %s", error)

        d = self.sync_daemon_tool.wait_for_signal('PublicFilesList',
                                                  filter=lambda _: True)

        client.call_method('get_public_files',
                           reply_handler=call_done,
                           error_handler=call_error)
        return d

    @retryable
    def get_queue_content(self):
        """Get the queue content from SDT."""
        logger.info("Getting queue content")
        return self.sync_daemon_tool.waiting()

    @retryable
    def get_folders(self):
        """Get the folders info from SDT."""

        def process(data):
            """Enhance data format."""
            logger.info("Processing Folders items (%d)", len(data))
            all_items = []
            for d in data:
                logger.debug("    Folders data: %r", d)
                f = self._get_folder_data(d)
                all_items.append(f)
            return all_items

        logger.info("Getting folders")
        d = self.sync_daemon_tool.get_folders()
        d.addCallback(process)
        return d

    def start(self):
        """Start SDT."""
        logger.info("Calling start")
        return self.sync_daemon_tool.start()

    def quit(self):
        """Stop SDT."""
        logger.info("Calling quit")
        return self.sync_daemon_tool.quit()

    def connect(self):
        """Connect SDT."""
        logger.info("Calling connect")
        return self.sync_daemon_tool.connect()

    def disconnect(self):
        """Disconnect SDT."""
        logger.info("Calling disconnect")
        return self.sync_daemon_tool.disconnect()

    @defer.inlineCallbacks
    def is_sd_started(self):
        """Find out if SD is active in the system."""
        started = yield is_already_running()
        logger.info("Checking if SD is started: %s", started)
        defer.returnValue(started)

    def _process_share_info(self, data):
        """Process share data."""
        all_items = []
        for d in data:
            logger.debug("    Share data: %r", d)

            # some processing
            dfb = d['free_bytes']
            free_bytes = None if dfb == '' else int(dfb)

            s = ShareData(
                accepted=bool(d['accepted']),
                access_level=d['access_level'],
                free_bytes=free_bytes,
                name=d['name'],
                node_id=d['node_id'],
                other_username=d['other_username'],
                other_visible_name=d['other_visible_name'],
                path=d['path'],
                volume_id=d['volume_id'],
                subscribed=bool(d['subscribed']),
            )
            all_items.append(s)
        return all_items

    @retryable
    def get_shares_to_me(self):
        """Get the shares to me ('shares') info from SDT."""

        def process(data):
            """Enhance data format."""
            logger.info("Processing Shares To Me items (%d)", len(data))
            return self._process_share_info(data)

        logger.info("Getting shares to me")
        d = self.sync_daemon_tool.get_shares()
        d.addCallback(process)
        return d

    @retryable
    def get_shares_to_others(self):
        """Get the shares to others ('shared') info from SDT."""

        def process(data):
            """Enhance data format."""
            logger.info("Processing Shares To Others items (%d)", len(data))
            return self._process_share_info(data)

        logger.info("Getting shares to others")
        d = self.sync_daemon_tool.list_shared()
        d.addCallback(process)
        return d

    @retryable
    def get_metadata(self, path):
        """Return the raw metadata."""
        logger.info("Getting metadata for %r", path)

        def fix_failure(failure):
            """Get the failure and return a nice message."""
            if failure.check(dbus.exceptions.DBusException):
                if failure.value.get_dbus_name() == DBUSERR_PYKEYERROR:
                    return NOT_SYNCHED_PATH
            return failure

        def process(metadata):
            """Process the metadata."""
            logger.debug("Got metadata for path %r: %r", path, metadata)
            return dict(metadata)

        d = self.sync_daemon_tool.get_metadata(path)
        d.addCallbacks(process, fix_failure)
        return d

    @retryable
    @defer.inlineCallbacks
    def _answer_share(self, share_id, method, action_name):
        """Effectively accept or reject a share."""
        logger.debug("%s share %s started", action_name, share_id)
        try:
            result = yield method(share_id)
        except Exception, e:
            if len(e.args) == 2 and len(e.args[1]) > 1:
                error = "%s (%s)" % (e.args[0], e.args[1][1])
            else:
                error = str(e.args[0])
            logger.debug("%s share %s crashed: %s",
                         action_name, share_id, error)
            raise ShareOperationError(share_id=share_id, error=error)

        logger.debug("%s share %s finished: %s", action_name, share_id, result)
        if 'error' in result:
            raise ShareOperationError(share_id=share_id, error=result['error'])

    def accept_share(self, share_id):
        """Accept a share."""
        return self._answer_share(share_id,
                                  self.sync_daemon_tool.accept_share, "Accept")

    def reject_share(self, share_id):
        """Reject a share."""
        return self._answer_share(share_id,
                                  self.sync_daemon_tool.reject_share, "Reject")

    def subscribe_share(self, share_id):
        """Subscribe a share."""
        args = share_id, self.sync_daemon_tool.subscribe_share, "Subscribe"
        return self._answer_share(*args)

    def unsubscribe_share(self, share_id):
        """Unsubscribe a share."""
        args = share_id, self.sync_daemon_tool.unsubscribe_share, "Unsubscribe"
        return self._answer_share(*args)

    @retryable
    @defer.inlineCallbacks
    def send_share_invitation(self, path, mail_address,
                              share_name, access_level):
        """Send a share invitation."""
        logger.debug("Send share invitation started: path=%r mail_address=%s "
                     "share_name=%r access_level=%s", path, mail_address,
                     share_name, access_level)
        try:
            yield self.sync_daemon_tool.send_share_invitation(
                path, mail_address, share_name, access_level)
        except dbus.exceptions.DBusException, e:
            error = str(e.args[0])
            logger.debug("Send share invitation crashed: %s (path=%r "
                         "mail_address=%s share_name=%r access_level=%s)",
                         error, path, mail_address, share_name, access_level)
            raise ShareOperationError(error=error)
        else:
            logger.debug("Send share invitation finished ok (path=%r "
                         "mail_address=%s share_name=%r access_level=%s)",
                         path, mail_address, share_name, access_level)

    def _get_folder_data(self, data):
        """Transform a syncdaemontool folder response in an internal object."""
        f = FolderData(path=data['path'], subscribed=bool(data['subscribed']),
                       node=data['node_id'], volume=data['volume_id'],
                       suggested_path=data['suggested_path'])
        return f

    @retryable
    @defer.inlineCallbacks
    def _folder_operation(self, act_name, action, val_name, value):
        """Generic folder operation."""
        logger.debug("%s folder started on %s %r", act_name, val_name, value)
        try:
            result = yield action(value)
        except Exception, e:
            logger.debug("%s folder finished with error %s on %s %r",
                         act_name, e, val_name, value)
            if len(e.args) == 2 and len(e.args[1]) > 1:
                error = "%s (%s)" % (e.args[0], e.args[1][1])
            else:
                error = str(e.args[0])
            kwargs = {'error': error, val_name: value}
            raise FolderOperationError(**kwargs)
        else:
            logger.debug("%s folder finished ok: %s", act_name, result)
            folder = self._get_folder_data(result)
            defer.returnValue(folder)

    def create_folder(self, path):
        """Create a folder."""
        args = 'Create', self.sync_daemon_tool.create_folder, 'path', path
        return self._folder_operation(*args)

    def delete_folder(self, volume_id):
        """Delete a folder."""
        args = ('Delete', self.sync_daemon_tool.delete_folder,
                'volume_id', volume_id)
        return self._folder_operation(*args)

    def subscribe_folder(self, volume_id):
        """Subscribe a folder."""
        args = ('Subscribe', self.sync_daemon_tool.subscribe_folder,
                'volume_id', volume_id)
        return self._folder_operation(*args)

    def unsubscribe_folder(self, volume_id):
        """Unsubscribe a folder."""
        args = ('Unsubscribe', self.sync_daemon_tool.unsubscribe_folder,
                'volume_id', volume_id)
        return self._folder_operation(*args)

    @retryable
    @defer.inlineCallbacks
    def change_public_access(self, path, is_public):
        """Make a file public or not."""
        logger.debug("Change public access started: path=%r, is_public=%s",
                     path, is_public)
        try:
            res = yield self.sync_daemon_tool.change_public_access(path,
                                                                   is_public)
        except Exception, e:
            logger.debug("Change public access finished with error %r on %r",
                         e, path)
            raise

        logger.debug("Change public access finished ok: %s", res)
        pf = PublicFilesData(volume=res['share_id'], node=res['node_id'],
                             path=res['path'], public_url=res['public_url'])
        defer.returnValue(pf)
