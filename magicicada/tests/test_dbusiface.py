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

"""Tests for the DBus interce towards real syncdaemon."""

import logging

import dbus

from twisted.internet import defer
from twisted.trial.unittest import TestCase as TwistedTestCase
from ubuntuone.devtools.handlers import MementoHandler

from magicicada import dbusiface

# It's ok to access private data in the test suite
# pylint: disable=W0212


class FakeDBusClient(object):
    """Fake DBusClient, but with different behaviour at instantiation time."""

    def __init__(self, *args):
        self.init_args = None
        self.method_call_args = None

    def call_method(self, *args, **kwargs):
        """Record the arguments of the method call."""
        self.method_call_args = args, kwargs

    def __call__(self, *args):
        """Simulate instantiation."""
        self.init_args = args
        return self


class FakeSessionBus(object):
    """Fake Session Bus."""

    def __init__(self, **kwargs):
        self._callbacks = {}

    def add_signal_receiver(self, method, dbus_interface, signal_name):
        """Add a signal receiver."""
        self._callbacks[(dbus_interface, signal_name)] = method

    def remove_signal_receiver(self, match, dbus_interface, signal_name):
        """Remove the signal receiver."""
        del self._callbacks[(dbus_interface, signal_name)]

    def send_message_with_reply(self, *a, **k):
        """Fake."""


class CallLoguer(object):
    """Class that logs the methods called."""

    def __init__(self):
        self._called_method = None, ()
        self._fake_response = None

    def __getattribute__(self, name):
        """Return the value if there."""
        if name[0] == "_":
            return object.__getattribute__(self, name)
        else:

            def f(*args):
                """Fake function."""
                setattr(self, "_called_method", (name, args))
                if self._fake_response is None:
                    # no hurt in returning a deferred, it may be needed
                    return defer.Deferred()
                methname, response = self._fake_response
                assert methname == name
                if isinstance(response, Exception):
                    return defer.fail(response)
                else:
                    return defer.succeed(response)
            return f


class FakeSDTool(CallLoguer):
    """Fake real SyncDaemonTool."""

    def __init__(self, _):
        CallLoguer.__init__(self)


class FakeSyncDaemon(CallLoguer):
    """Fake Magicicada's SyncDaemon."""


class SafeTestCase(TwistedTestCase):
    """Safe tests not going outside the testing box."""

    @defer.inlineCallbacks
    def setUp(self):
        """Set up."""
        yield super(SafeTestCase, self).setUp()
        self.handler = MementoHandler()
        self.handler.setLevel(logging.DEBUG)
        logger = logging.getLogger('magicicada.dbusiface')
        logger.addHandler(self.handler)
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.removeHandler, self.handler)

        self.patch(dbusiface, 'SessionBus', FakeSessionBus)
        self.patch(dbusiface, 'SyncDaemonTool', FakeSDTool)

        self.fsd = FakeSyncDaemon()
        self.dbus = dbusiface.DBusInterface(self.fsd)

    def check_sdt_called(self, name):
        """Check that the SyncDaemonTool method was called."""
        self.assertEqual(self.dbus.sync_daemon_tool._called_method[0], name)

    def get_msd_called(self, name):
        """Get the args from the called Magicicada's SyncDaemon method."""
        called_method, called_args = self.fsd._called_method
        self.assertEqual(called_method, name)
        return called_args

    def fake_sdt_response(self, method_name, response):
        """Fake SDT answer in deferred mode."""
        self.dbus.sync_daemon_tool._fake_response = (method_name, response)


class SignalHookingTestCase(SafeTestCase):
    """Signal hooking tests.

    We can not check if the methods are really called, because DBus holds the
    method object itself, so no chance in monkeypatching.
    """

    def _get_hooked(self, iface, signal):
        """Return the hooked method if any."""
        if iface is None:
            interface = None
        else:
            interface = 'com.ubuntuone.SyncDaemon.' + iface
        return self.dbus._bus._callbacks.get((interface, signal))

    def test_hook_unhook(self):
        """Test the hooked signals are unhooked."""
        self.dbus.shutdown()
        self.assertEqual(self.dbus._bus._callbacks, {})

    def test_status_changed(self):
        """Test status changed callback."""
        self.assertEqual(self._get_hooked('Status', 'StatusChanged'),
                         self.dbus._on_status_changed)

    def test_queue_added(self):
        """Test queue added callback."""
        self.assertEqual(self._get_hooked('Status', 'RequestQueueAdded'),
                         self.dbus._on_queue_added)

    def test_queue_removed(self):
        """Test queue removed callback."""
        self.assertEqual(self._get_hooked('Status', 'RequestQueueRemoved'),
                         self.dbus._on_queue_removed)

    def test_on_upload_progress(self):
        """Test upload progress callback."""
        self.assertEqual(self._get_hooked('Status', 'UploadFileProgress'),
                         self.dbus._on_upload_progress)

    def test_on_download_progress(self):
        """Test download progress callback."""
        self.assertEqual(self._get_hooked('Status', 'DownloadFileProgress'),
                         self.dbus._on_download_progress)

    def test_folder_created_changed(self):
        """Test folder created changed callback."""
        self.assertEqual(self._get_hooked('Folders', 'FolderCreated'),
                         self.dbus._on_folder_created)

    def test_folder_deleted_changed(self):
        """Test folder deleted changed callback."""
        self.assertEqual(self._get_hooked('Folders', 'FolderDeleted'),
                         self.dbus._on_folder_deleted)

    def test_folder_subscribed_changed(self):
        """Test folder subscribed changed callback."""
        self.assertEqual(self._get_hooked('Folders', 'FolderSubscribed'),
                         self.dbus._on_folder_subscribed)

    def test_folder_unsubscribed_changed(self):
        """Test folder unsubscribed changed callback."""
        self.assertEqual(self._get_hooked('Folders', 'FolderUnSubscribed'),
                         self.dbus._on_folder_unsubscribed)

    def test_share_created(self):
        """Test share created callback."""
        self.assertEqual(self._get_hooked('Shares', 'ShareCreated'),
                         self.dbus._on_share_created)

    def test_share_deleted(self):
        """Test share deleted callback."""
        self.assertEqual(self._get_hooked('Shares', 'ShareDeleted'),
                         self.dbus._on_share_deleted)

    def test_share_changed(self):
        """Test share changed callback."""
        self.assertEqual(self._get_hooked('Shares', 'ShareChanged'),
                         self.dbus._on_share_changed)

    def test_public_files_changed(self):
        """Test public files changed callback."""
        self.assertEqual(self._get_hooked('PublicFiles',
                         'PublicAccessChanged'),
                         self.dbus._on_public_files_changed)


class SimpleCallsTestCase(SafeTestCase):
    """Tests for some simple calls."""

    @defer.inlineCallbacks
    def test_is_sd_started_yes(self):
        """Test is SD started, yes."""
        self.patch(dbusiface, 'is_already_running',
                   lambda: defer.succeed(True))
        resp = yield self.dbus.is_sd_started()
        self.assertTrue(resp)

    @defer.inlineCallbacks
    def test_is_sd_started_no(self):
        """Test is SD started, no."""
        self.patch(dbusiface, 'is_already_running',
                   lambda: defer.succeed(False))
        resp = yield self.dbus.is_sd_started()
        self.assertFalse(resp)

    @defer.inlineCallbacks
    def test_get_shares_dir_real(self):
        """Get the real directory for the shares."""
        self.fake_sdt_response('get_shares_dir', "/some/shares/dir")
        result = yield self.dbus.get_real_shares_dir()
        self.assertEqual(result, "/some/shares/dir")
        self.assertTrue(self.handler.check_info("Real shares dir",
                                                "/some/shares/dir"))

    @defer.inlineCallbacks
    def test_get_shares_dir_link(self):
        """Get the link directory for the shares."""
        self.fake_sdt_response('get_shares_dir_link', "/some/shares/dir")
        result = yield self.dbus.get_link_shares_dir()
        self.assertEqual(result, "/some/shares/dir")
        self.assertTrue(self.handler.check_info("Link shares dir",
                                                "/some/shares/dir"))

    @defer.inlineCallbacks
    def test_get_current_downloads(self):
        """Get the current downloads."""
        downloads = [
            dict(deflated_size='123', n_bytes_read='45', node_id='node_id',
                 path='/path/to/file1', share_id=''),
            dict(n_bytes_read='0', node_id='node_id',
                 path='/path/to/file2', share_id=''),
            dict(deflated_size='678', n_bytes_read='90', node_id='node_id',
                 path='/path/to/file3', share_id=''),
        ]
        self.fake_sdt_response('get_current_downloads', downloads)
        result = yield self.dbus.get_current_downloads()
        self.assertEqual(result[0], ('/path/to/file1', 45, 123))
        self.assertEqual(result[1], ('/path/to/file3', 90, 678))
        self.assertTrue(self.handler.check_info("Get current downloads",
                                                "2 items"))

    @defer.inlineCallbacks
    def test_get_current_uploads(self):
        """Get the current uploads."""
        uploads = [
            dict(deflated_size='123', n_bytes_written='45', node_id='node_id',
                 path='/path/to/file', share_id=''),
        ]
        self.fake_sdt_response('get_current_uploads', uploads)
        result = yield self.dbus.get_current_uploads()
        self.assertEqual(result[0], ('/path/to/file', 45, 123))
        self.assertTrue(self.handler.check_info("Get current uploads",
                                                "1 items"))

    @defer.inlineCallbacks
    def test_get_free_space(self):
        """Get the free space."""
        self.fake_sdt_response('free_space', "3456")
        result = yield self.dbus.get_free_space("vol_id")
        self.assertEqual(result, "3456")
        self.assertTrue(self.handler.check_info("Free space for volume",
                                                "vol_id", "3456"))


class DataProcessingStatusTestCase(SafeTestCase):
    """Process Status before sending it to SyncDaemon."""

    @defer.inlineCallbacks
    def test_get_status(self):
        """Test getting status."""
        d = dict(name='n', description='d', is_error='', is_connected='True',
                 is_online='', queues='q', connection='c')
        self.fake_sdt_response('get_status', d)
        args = yield self.dbus.get_status()
        name, descrip, error, connected, online, queues, connection = args
        self.assertEqual(name, 'n')
        self.assertEqual(descrip, 'd')
        self.assertEqual(error, False)
        self.assertEqual(connected, True)
        self.assertEqual(online, False)
        self.assertEqual(queues, 'q')
        self.assertEqual(connection, 'c')

    def test_status_changed(self):
        """Test status changed callback."""
        d = dict(name='name', description='description', is_error='',
                 is_connected='True', is_online='', queues='queues',
                 connection='connection')
        self.dbus._on_status_changed(d)
        args = self.get_msd_called("on_sd_status_changed")
        name, descrip, error, connected, online, queues, connection = args
        self.assertEqual(name, 'name')
        self.assertEqual(descrip, 'description')
        self.assertEqual(error, False)
        self.assertEqual(connected, True)
        self.assertEqual(online, False)
        self.assertEqual(queues, 'queues')
        self.assertEqual(connection, 'connection')


class QueueChangedTestCase(SafeTestCase):
    """Process the signals for when the queue changes."""

    def test_queue_added(self):
        """Something added to the queue."""
        self.dbus._on_queue_added('name', 'id', {'some': 'data'})
        name, op_id, op_data = self.get_msd_called("on_sd_queue_added")
        self.assertEqual(name, 'name')
        self.assertEqual(op_id, 'id')
        self.assertEqual(op_data, {'some': 'data'})

    def test_queue_removed(self):
        """Something removed from the queue."""
        self.dbus._on_queue_removed('name', 'id', {'some': 'data'})
        name, op_id, op_data = self.get_msd_called("on_sd_queue_removed")
        self.assertEqual(name, 'name')
        self.assertEqual(op_id, 'id')
        self.assertEqual(op_data, {'some': 'data'})

    def test_upload_progress(self):
        """An upload is progressing."""
        data = dict(deflated_size='123', n_bytes_written='45')
        self.dbus._on_upload_progress('path', data)
        transfer, = self.get_msd_called("on_sd_upload_progress")
        self.assertEqual(transfer.path, 'path')
        self.assertEqual(transfer.transfered, 45)
        self.assertEqual(transfer.total, 123)

    def test_download_progress(self):
        """A download is progressing."""
        data = dict(deflated_size='123', n_bytes_read='45')
        self.dbus._on_download_progress('path', data)
        transfer, = self.get_msd_called("on_sd_download_progress")
        self.assertEqual(transfer.path, 'path')
        self.assertEqual(transfer.transfered, 45)
        self.assertEqual(transfer.total, 123)

    @defer.inlineCallbacks
    def test_get_queue_content_none(self):
        """Test with no data in the queue."""
        self.fake_sdt_response('waiting', [])
        rcv = yield self.dbus.get_queue_content()
        self.assertEqual(len(rcv), 0)

    @defer.inlineCallbacks
    def test_get_queue_content_somestuff(self):
        """Test with one item in the queue."""
        self.fake_sdt_response('waiting', [('Cmd1', '123', {'some': 'data'}),
                                           ('Other', '456', {'othr': 'data'})])
        rcv = yield self.dbus.get_queue_content()
        self.assertEqual(len(rcv), 2)
        self.assertEqual(rcv[0], ('Cmd1', '123', {'some': 'data'}))
        self.assertEqual(rcv[1], ('Other', '456', {'othr': 'data'}))


class DataProcessingFoldersTestCase(SafeTestCase):
    """Process Folders data before sending it to SyncDaemon."""

    @defer.inlineCallbacks
    def test_nodata(self):
        """Test get folders with no data."""
        self.fake_sdt_response('get_folders', [])
        rcv = yield self.dbus.get_folders()
        self.assertEqual(len(rcv), 0)

    @defer.inlineCallbacks
    def test_one(self):
        """Test get folders with one."""
        d = dict(node_id='nid', path=u'pth', subscribed='True',
                 suggested_path=u'sgp', type='UDF', volume_id='vid')
        self.fake_sdt_response('get_folders', [d])
        rcv = yield self.dbus.get_folders()
        self.assertEqual(len(rcv), 1)
        folder = rcv[0]
        self.assertEqual(folder.node, 'nid')
        self.assertEqual(folder.path, u'pth')
        self.assertEqual(folder.suggested_path, u'sgp')
        self.assertEqual(folder.subscribed, True)
        self.assertEqual(folder.volume, 'vid')

    @defer.inlineCallbacks
    def test_getting_info_two(self):
        """When changed, update info, got two."""
        d1 = dict(node_id='nid1', path=u'pth1', subscribed='True',
                  suggested_path=u'sgp1', type='UDF', volume_id='vid1')
        d2 = dict(node_id='nid2', path=u'pth2', subscribed='',
                  suggested_path=u'sgp2', type='UDF', volume_id='vid2')
        self.fake_sdt_response('get_folders', [d1, d2])
        rcv = yield self.dbus.get_folders()
        self.assertEqual(len(rcv), 2)
        folder = rcv[0]
        self.assertEqual(folder.node, 'nid1')
        self.assertEqual(folder.path, u'pth1')
        self.assertEqual(folder.suggested_path, u'sgp1')
        self.assertEqual(folder.subscribed, True)
        self.assertEqual(folder.volume, 'vid1')
        folder = rcv[1]
        self.assertEqual(folder.node, 'nid2')
        self.assertEqual(folder.path, u'pth2')
        self.assertEqual(folder.suggested_path, u'sgp2')
        self.assertEqual(folder.subscribed, False)
        self.assertEqual(folder.volume, 'vid2')

    def test_folders_changed_from_created(self):
        """Test folders changed callback from created."""
        self.dbus._on_folder_created(None)
        self.get_msd_called("on_sd_folders_changed")

    def test_folders_changed_from_deleted(self):
        """Test folders changed callback from deleted."""
        self.dbus._on_folder_deleted(None)
        self.get_msd_called("on_sd_folders_changed")

    def test_folders_changed_from_subscribed(self):
        """Test folders changed callback from subscribed."""
        self.dbus._on_folder_subscribed(None)
        self.get_msd_called("on_sd_folders_changed")

    def test_folders_changed_from_unsubscribed(self):
        """Test folders changed callback from unsubscribed."""
        self.dbus._on_folder_unsubscribed(None)
        self.get_msd_called("on_sd_folders_changed")


class DataProcessingMetadataTestCase(SafeTestCase):
    """Process Metadata data before sending it to SyncDaemon."""

    @defer.inlineCallbacks
    def test_info_ok(self):
        """Test get metadata and see response."""
        md = dbus.Dictionary({'a': 3, 'c': 4}, signature=dbus.Signature('ss'))
        self.fake_sdt_response('get_metadata', md)
        rcv = yield self.dbus.get_metadata('path')
        self.assertEqual(rcv, dict(a=3, c=4))

    @defer.inlineCallbacks
    def test_info_bad(self):
        """Test get metadata and get the error."""
        exc = dbus.exceptions.DBusException(
            name='org.freedesktop.DBus.Python.KeyError')
        self.fake_sdt_response('get_metadata', exc)
        rcv = yield self.dbus.get_metadata('not a real path')
        self.assertEqual(rcv, dbusiface.NOT_SYNCHED_PATH)


class DataProcessingSharesTestCase(SafeTestCase):
    """Process Shares data before sending it to SyncDaemon."""

    @defer.inlineCallbacks
    def test_sharestome_nodata(self):
        """Test get shares to me with no data."""
        self.fake_sdt_response('get_shares', [])
        rcv = yield self.dbus.get_shares_to_me()
        self.assertEqual(len(rcv), 0)

    @defer.inlineCallbacks
    def test_sharestoothers_nodata(self):
        """Test get shares to others with no data."""
        self.fake_sdt_response('list_shared', [])
        rcv = yield self.dbus.get_shares_to_others()
        self.assertEqual(len(rcv), 0)

    @defer.inlineCallbacks
    def test_sharestome_one(self):
        """Test get shares to me with one."""
        d = dict(accepted=u'True', access_level=u'View', free_bytes=u'123456',
                 name=u'foobar', node_id=u'node', other_username=u'johndoe',
                 other_visible_name=u'John Doe', path=u'path',
                 volume_id=u'vol', type=u'Share', subscribed='')
        self.fake_sdt_response('get_shares', [d])
        rcv = yield self.dbus.get_shares_to_me()
        self.assertEqual(len(rcv), 1)
        share = rcv[0]
        self.assertEqual(share.accepted, True)
        self.assertEqual(share.access_level, 'View')
        self.assertEqual(share.free_bytes, 123456)
        self.assertEqual(share.name, 'foobar')
        self.assertEqual(share.node_id, 'node')
        self.assertEqual(share.other_username, 'johndoe')
        self.assertEqual(share.other_visible_name, 'John Doe')
        self.assertEqual(share.path, 'path')
        self.assertEqual(share.subscribed, False)

    @defer.inlineCallbacks
    def test_sharestoother_one(self):
        """Test get shares to other with one."""
        d = dict(accepted=u'True', access_level=u'View', free_bytes=u'123456',
                 name=u'foobar', node_id=u'node', other_username=u'johndoe',
                 other_visible_name=u'John Doe', path=u'path',
                 volume_id=u'vol', type=u'Shared', subscribed='True')
        self.fake_sdt_response('list_shared', [d])
        rcv = yield self.dbus.get_shares_to_others()
        self.assertEqual(len(rcv), 1)
        share = rcv[0]
        self.assertEqual(share.accepted, True)
        self.assertEqual(share.access_level, 'View')
        self.assertEqual(share.free_bytes, 123456)
        self.assertEqual(share.name, 'foobar')
        self.assertEqual(share.node_id, 'node')
        self.assertEqual(share.other_username, 'johndoe')
        self.assertEqual(share.other_visible_name, 'John Doe')
        self.assertEqual(share.path, 'path')
        self.assertEqual(share.volume_id, 'vol')
        self.assertEqual(share.subscribed, True)

    @defer.inlineCallbacks
    def test_sharestoother_two(self):
        """Test get shares to other with two."""
        d1 = dict(accepted=u'True', access_level=u'View', free_bytes=u'123456',
                  name=u'foobar', node_id=u'node', other_username=u'johndoe',
                  other_visible_name=u'John Doe', path=u'path',
                  volume_id=u'vol', type=u'Shared', subscribed='')
        d2 = dict(accepted=u'', access_level=u'Modify', free_bytes=u'789',
                  name=u'rulo', node_id=u'node', other_username=u'nn',
                  other_visible_name=u'Ene Ene', path=u'path',
                  volume_id=u'vol', type=u'Shared', subscribed='True')
        self.fake_sdt_response('list_shared', [d1, d2])
        rcv = yield self.dbus.get_shares_to_others()
        self.assertEqual(len(rcv), 2)
        share = rcv[0]
        self.assertEqual(share.accepted, True)
        self.assertEqual(share.access_level, 'View')
        self.assertEqual(share.free_bytes, 123456)
        self.assertEqual(share.name, 'foobar')
        self.assertEqual(share.node_id, 'node')
        self.assertEqual(share.other_username, 'johndoe')
        self.assertEqual(share.other_visible_name, 'John Doe')
        self.assertEqual(share.path, 'path')
        self.assertEqual(share.volume_id, 'vol')
        self.assertEqual(share.subscribed, False)
        share = rcv[1]
        self.assertEqual(share.accepted, False)
        self.assertEqual(share.access_level, 'Modify')
        self.assertEqual(share.free_bytes, 789)
        self.assertEqual(share.name, 'rulo')
        self.assertEqual(share.node_id, 'node')
        self.assertEqual(share.other_username, 'nn')
        self.assertEqual(share.other_visible_name, 'Ene Ene')
        self.assertEqual(share.path, 'path')
        self.assertEqual(share.volume_id, 'vol')
        self.assertEqual(share.subscribed, True)

    def test_shares_changed_from_created(self):
        """Test shares changed callback from created."""
        self.dbus._on_share_created(None)
        self.get_msd_called("on_sd_shares_changed")

    def test_shares_changed_from_deleted(self):
        """Test shares changed callback from deleted."""
        self.dbus._on_share_deleted(None)
        self.get_msd_called("on_sd_shares_changed")

    def test_shares_changed_from_changed(self):
        """Test shares changed callback from changed."""
        self.dbus._on_share_changed(None)
        self.get_msd_called("on_sd_shares_changed")

    @defer.inlineCallbacks
    def test_with_no_free_bytes(self):
        """Test get shares to me with no free bytes."""
        d = dict(accepted=u'True', access_level=u'View', free_bytes=u'',
                 name=u'foobar', node_id=u'node', other_username=u'johndoe',
                 other_visible_name=u'John Doe', path=u'path',
                 volume_id=u'vol', type=u'Share', subscribed='True')
        self.fake_sdt_response('get_shares', [d])
        rcv = yield self.dbus.get_shares_to_me()
        self.assertEqual(len(rcv), 1)
        share = rcv[0]
        self.assertEqual(share.accepted, True)
        self.assertEqual(share.access_level, 'View')
        self.assertEqual(share.free_bytes, None)
        self.assertEqual(share.name, 'foobar')
        self.assertEqual(share.node_id, 'node')
        self.assertEqual(share.other_username, 'johndoe')
        self.assertEqual(share.other_visible_name, 'John Doe')
        self.assertEqual(share.path, 'path')
        self.assertEqual(share.volume_id, 'vol')
        self.assertEqual(share.subscribed, True)


class PublicFilesTestCase(SafeTestCase):
    """PublicFiles data handling and related services."""

    def test_public_files_changed_yes(self):
        """Call the changed callback."""
        d = dict(share_id='share', node_id='node', is_public='True',
                 public_url='url', path='path')
        self.dbus._on_public_files_changed(d)
        pf, is_public = self.get_msd_called("on_sd_public_files_changed")
        self.assertEqual(pf.volume, 'share')
        self.assertEqual(pf.node, 'node')
        self.assertEqual(pf.public_url, 'url')
        self.assertEqual(pf.path, 'path')
        self.assertEqual(is_public, True)

    def test_public_files_changed_no(self):
        """Call the changed callback."""
        d = dict(share_id='share', node_id='node', is_public='',
                 public_url='url', path='path')
        self.dbus._on_public_files_changed(d)
        pf, is_public = self.get_msd_called("on_sd_public_files_changed")
        self.assertEqual(pf.volume, 'share')
        self.assertEqual(pf.node, 'node')
        self.assertEqual(pf.public_url, 'url')
        self.assertEqual(pf.path, 'path')
        self.assertEqual(is_public, False)

    def test_public_files_empty(self):
        """Call the callback without info."""
        res = self.dbus._on_public_files_list([])
        self.assertEqual(res, [])

    def test_public_files_one(self):
        """Call the callback with a public file."""
        d = dict(volume_id='volume', node_id='node',
                 public_url='url', path='path')
        res = self.dbus._on_public_files_list([d])
        self.assertEqual(len(res), 1)
        pf = res[0]
        self.assertEqual(pf.volume, 'volume')
        self.assertEqual(pf.node, 'node')
        self.assertEqual(pf.public_url, 'url')
        self.assertEqual(pf.path, 'path')

    def test_public_files_more(self):
        """Call the callback with a mixed content."""
        d1 = dict(volume_id='volume1', node_id='node1',
                  public_url='url1', path='path1')
        d2 = dict(volume_id='volume2', node_id='node2',
                  public_url='url2', path='path2')
        d3 = dict(volume_id='volume3', node_id='node3',
                  public_url='url3', path='path3')
        res = self.dbus._on_public_files_list([d1, d2, d3])
        self.assertEqual(len(res), 3)
        pf = res[0]
        self.assertEqual(pf.volume, 'volume1')
        self.assertEqual(pf.node, 'node1')
        self.assertEqual(pf.public_url, 'url1')
        self.assertEqual(pf.path, 'path1')
        pf = res[1]
        self.assertEqual(pf.volume, 'volume2')
        self.assertEqual(pf.node, 'node2')
        self.assertEqual(pf.public_url, 'url2')
        self.assertEqual(pf.path, 'path2')
        pf = res[2]
        self.assertEqual(pf.volume, 'volume3')
        self.assertEqual(pf.node, 'node3')
        self.assertEqual(pf.public_url, 'url3')
        self.assertEqual(pf.path, 'path3')

    @defer.inlineCallbacks
    def test_getpublicfiles_asktoclient_ok(self):
        """The info was requested to the SyncDaemonTool, and was ok."""
        expected = [object(), object()]
        self.fake_sdt_response('get_public_files', expected)

        self.patch(self.dbus, '_on_public_files_list', lambda _: _)
        result = yield self.dbus.get_public_files()
        self.assertEqual(result, expected)

        self.check_sdt_called('get_public_files')
        self.assertTrue(self.handler.check_debug("Public files asked ok."))

    @defer.inlineCallbacks
    def test_getpublicfiles_asktoclient_error(self):
        """The info was requested to the SyncDaemonTool, and was not ok."""
        exc = ValueError('foo')
        self.fake_sdt_response('get_public_files', exc)

        result = yield self.dbus.get_public_files()
        self.assertEqual(result, [])

        self.assertTrue(self.handler.check_exception(exc.__class__))
        self.assertTrue(self.handler.check_error(
                        "Public files finished with error:"))

    @defer.inlineCallbacks
    def test_getpublicfiles_asktoclient_attribute_error(self):
        """The info was requested to the SyncDaemonTool, and was not ok."""
        exc = AttributeError()
        self.fake_sdt_response('get_public_files', exc)

        expected = [object(), object()]
        self.patch(self.dbus, 'get_public_files_old',
                   lambda: defer.succeed(expected))
        self.patch(self.dbus, '_on_public_files_list', lambda _: _)
        result = yield self.dbus.get_public_files()
        self.assertEqual(result, expected)

        msg = 'Method sdtool.get_public_files is not available, ' \
              'trying old one directly from dbus.'
        self.assertTrue(self.handler.check_warning(msg))

    @defer.inlineCallbacks
    def test_public_file_changeaccess_yes_success(self):
        """Make a path public, all ok."""
        result = dict(path='path', public_url='http://something',
                      node_id='node_id', share_id='share_id', is_public='True')
        self.fake_sdt_response('change_public_access', result)
        pf = yield self.dbus.change_public_access('path', True)
        self.assertEqual(pf.path, 'path')
        self.assertEqual(pf.volume, 'share_id')
        self.assertEqual(pf.node, 'node_id')
        self.assertEqual(pf.public_url, 'http://something')
        self.assertTrue(self.handler.check_debug(
                        "Change public access started", "path", "True"))
        self.assertTrue(self.handler.check_debug(
                        "Change public access finished ok", str(result)))

    @defer.inlineCallbacks
    def test_public_file_changeaccess_yes_error(self):
        """Make a path public, error."""
        self.fake_sdt_response('change_public_access', KeyError('wrong path'))
        d = self.dbus.change_public_access('path', True)
        err = yield self.assertFailure(d, KeyError)
        self.assertEqual(err.message, 'wrong path')
        self.assertTrue(self.handler.check_debug(
                        "Change public access started", "path"))
        self.assertTrue(self.handler.check_debug(
                        "Change public access finished with error",
                        "KeyError", "wrong path"))


class ToolActionsTestCase(SafeTestCase):
    """Actions against SD.tools.

    Here we test only the actions, not callbacks, as they're tested before
    in what they return.
    """

    def test_start(self):
        """Test call to start."""
        res = self.dbus.start()
        self.check_sdt_called("start")
        self.assertIsInstance(res, defer.Deferred)

    def test_quit(self):
        """Test call to quit."""
        res = self.dbus.quit()
        self.check_sdt_called("quit")
        self.assertIsInstance(res, defer.Deferred)

    def test_connect(self):
        """Test call to connect."""
        res = self.dbus.connect()
        self.check_sdt_called("connect")
        self.assertIsInstance(res, defer.Deferred)

    def test_disconnect(self):
        """Test call to disconnect."""
        res = self.dbus.disconnect()
        self.check_sdt_called("disconnect")
        self.assertIsInstance(res, defer.Deferred)


class LogsTestCase(SafeTestCase):
    """Test logging."""

    def test_instancing(self):
        """Just logged SD instancing."""
        self.assertTrue(self.handler.check_info("DBus interface starting"))

    def test_shutdown(self):
        """Log when SD shutdowns."""
        self.dbus.shutdown()
        self.assertTrue(self.handler.check_info("DBus interface going down"))

    def test_waiting(self):
        """Test call to queue content."""
        self.dbus.get_queue_content()
        self.assertTrue(self.handler.check_info("Getting queue content"))

    def test_get_status(self):
        """Test call to status."""
        self.dbus.get_status()
        self.assertTrue(self.handler.check_info("Getting status"))

    def test_get_folders(self):
        """Test call to folders."""
        self.dbus.get_folders()
        self.assertTrue(self.handler.check_info("Getting folders"))

    def test_get_metadata(self):
        """Test call to metadata."""
        self.dbus.get_metadata('path')
        msg = "Getting metadata for 'path'"
        self.assertTrue(self.handler.check_info(msg))

    def test_get_shares_to_me(self):
        """Test call to shares to me."""
        self.dbus.get_shares_to_me()
        self.assertTrue(self.handler.check_info("Getting shares to me"))

    def test_get_shares_to_other(self):
        """Test call to shares to others."""
        self.dbus.get_shares_to_others()
        self.assertTrue(self.handler.check_info("Getting shares to others"))

    def test_is_sd_started(self):
        """Test call to is_sd_started."""
        self.patch(dbusiface, 'is_already_running',
                   lambda: defer.succeed(True))
        self.dbus.is_sd_started()
        self.assertTrue(self.handler.check_info(
                        "Checking if SD is started: True"))

    def test_start(self):
        """Test call to start."""
        self.dbus.start()
        self.assertTrue(self.handler.check_info("Calling start"))

    def test_quit(self):
        """Test call to quit."""
        self.dbus.quit()
        self.assertTrue(self.handler.check_info("Calling quit"))

    def test_connect(self):
        """Test call to connect."""
        self.dbus.connect()
        self.assertTrue(self.handler.check_info("Calling connect"))

    def test_disconnect(self):
        """Test call to disconnect."""
        self.dbus.disconnect()
        self.assertTrue(self.handler.check_info("Calling disconnect"))

    def test_status_changed(self):
        """Test status changed callback."""
        d = dict(name='name', description='description', is_error='',
                 is_connected='True', is_online='', queues='queues',
                 connection='connection')
        self.dbus._on_status_changed(d)
        self.assertTrue(self.handler.check_info("Received Status changed"))
        msg = "Status changed data: %r" % d
        self.assertTrue(self.handler.check_debug(msg))

    def test_queue_added(self):
        """Test queue added callback."""
        self.dbus._on_queue_added("name", "1234", {'some': 'data'})
        m = "Received Queue added: 'name' [1234] {'some': 'data'}"
        self.assertTrue(self.handler.check_debug(m))

    def test_queue_removed(self):
        """Test queue removed callback."""
        self.dbus._on_queue_removed("name", "1234", {'some': 'data'})
        m = "Received Queue removed: 'name' [1234] {'some': 'data'}"
        self.assertTrue(self.handler.check_debug(m))

    def test_upload_progress(self):
        """Test upload progress  callback."""
        data = dict(deflated_size='123', n_bytes_written='45')
        self.dbus._on_upload_progress('path', data)
        args = 'Received Upload progress', 'path', '45', '123'
        self.assertTrue(self.handler.check_debug(*args))

    def test_download_progress(self):
        """Test download progress  callback."""
        data = dict(deflated_size='123', n_bytes_read='45')
        self.dbus._on_download_progress('path', data)
        args = 'Received Download progress', 'path', '45', '123'
        self.assertTrue(self.handler.check_debug(*args))

    def test_folder_created_changed(self):
        """Test folder created changed callback."""
        self.dbus._on_folder_created("foo")
        self.assertTrue(self.handler.check_info("Received Folder created"))

    def test_folder_deleted_changed(self):
        """Test folder deleted changed callback."""
        self.dbus._on_folder_deleted("foo")
        self.assertTrue(self.handler.check_info("Received Folder deleted"))

    def test_folder_subscribed_changed(self):
        """Test folder subscribed changed callback."""
        self.dbus._on_folder_subscribed("foo")
        self.assertTrue(self.handler.check_info("Received Folder subscribed"))

    def test_folder_unsubscribed_changed(self):
        """Test folder unsubscribed changed callback."""
        self.dbus._on_folder_unsubscribed("foo")
        self.assertTrue(
            self.handler.check_info("Received Folder unsubscribed"))

    def test_share_created(self):
        """Test share created callback."""
        self.dbus._on_share_created("foo")
        self.assertTrue(self.handler.check_info("Received Share created"))

    def test_share_deleted(self):
        """Test share deleted callback."""
        self.dbus._on_share_deleted("foo")
        self.assertTrue(self.handler.check_info("Received Share deleted"))

    def test_share_changed(self):
        """Test share changed callback."""
        self.dbus._on_share_changed("foo")
        self.assertTrue(self.handler.check_info("Received Share changed"))

    @defer.inlineCallbacks
    def test_public_files_list(self):
        """Test public files list callback."""
        d = dict(volume_id='volume', node_id='node',
                 public_url='url', path='path')
        yield self.dbus._on_public_files_list([d])
        self.assertTrue(self.handler.check_info(
                        "Received Public Files list (1)"))
        self.assertTrue(self.handler.check_debug(
                        "    Public Files data: %s" % d))

    @defer.inlineCallbacks
    def test_public_files_changed(self):
        """Test public files changed callback."""
        d = dict(share_id='volume', node_id='node', is_public='',
                 public_url='url', path='path')
        yield self.dbus._on_public_files_changed(d)
        self.assertTrue(self.handler.check_debug(
                        "Received Public Files changed: %s" % d))

    @defer.inlineCallbacks
    def test_folders_processing(self):
        """Test get folders with one."""
        d = dict(node_id='nid', path=u'pth', subscribed='True',
                 suggested_path=u'sgp', type='UDF', volume_id='vid')
        self.fake_sdt_response('get_folders', [d])
        yield self.dbus.get_folders()
        msg = "Processing Folders items (1)"
        self.assertTrue(self.handler.check_info(msg))
        self.assertTrue(self.handler.check_debug("    Folders data: %r" % d))

    @defer.inlineCallbacks
    def test_metadata_processing(self):
        """Test get metadata."""
        d = dict(lot_of_data="I don't care")
        self.fake_sdt_response('get_metadata', d)
        yield self.dbus.get_metadata('path')
        self.assertTrue(self.handler.check_debug(
                        "Got metadata for path 'path': %r" % d))

    @defer.inlineCallbacks
    def test_sharestome_processing(self):
        """Test get shares to me with one."""
        d = dict(accepted=u'True', access_level=u'View', free_bytes=u'123456',
                 name=u'foobar', node_id=u'node', other_username=u'johndoe',
                 other_visible_name=u'John Doe', path=u'path',
                 volume_id=u'vol', type=u'Share', subscribed='')
        self.fake_sdt_response('get_shares', [d])
        yield self.dbus.get_shares_to_me()
        self.assertTrue(self.handler.check_info(
                        "Processing Shares To Me items (1)"))
        self.assertTrue(self.handler.check_debug("    Share data: %r" % d))

    @defer.inlineCallbacks
    def test_sharestoothers_processing(self):
        """Test get shares to others with one."""
        d = dict(accepted=u'True', access_level=u'View', free_bytes=u'123456',
                 name=u'foobar', node_id=u'node', other_username=u'johndoe',
                 other_visible_name=u'John Doe', path=u'path',
                 volume_id=u'vol', type=u'Shared', subscribed='True')
        self.fake_sdt_response('list_shared', [d])
        yield self.dbus.get_shares_to_others()
        self.assertTrue(self.handler.check_info(
                        "Processing Shares To Others items (1)"))
        self.assertTrue(self.handler.check_debug("    Share data: %r" % d))


class RetryDecoratorTestCase(TwistedTestCase):
    """Test the retry decorator."""

    class Helper(object):
        """Fail some times, finally succeed."""

        def __init__(self, limit, excep=None):
            self.cant = 0
            self.limit = limit
            if excep is None:
                self.excep = dbus.exceptions.DBusException(
                    name='org.freedesktop.DBus.Error.NoReply')
            else:
                self.excep = excep

        def __call__(self):
            """Called."""
            self.cant += 1
            if self.cant < self.limit:
                return defer.fail(self.excep)
            else:
                return defer.succeed(True)

    def test_retryexcep_noexcep(self):
        """Test _is_retry_exception with no error."""
        self.assertFalse(dbusiface._is_retry_exception("foo"))

    def test_retryexcep_stdexcep(self):
        """Test _is_retry_exception with a standard exception."""
        self.assertFalse(dbusiface._is_retry_exception(NameError("foo")))

    def test_retryexcep_dbusnoretry(self):
        """Test _is_retry_exception with DBus exception, but not retry."""
        err = dbus.exceptions.DBusException(name='org.freedesktop.DBus.Other')
        self.assertFalse(dbusiface._is_retry_exception(err))

    def test_retryexcep_dbusretry(self):
        """Test _is_retry_exception with DBus exception, retry."""
        err = dbus.exceptions.DBusException(
            name='org.freedesktop.DBus.Error.NoReply')
        self.assertTrue(dbusiface._is_retry_exception(err))

    def get_decorated_func(self, func):
        """Execute the test calling the received function."""

        @dbusiface.retryable
        def f():
            """Test func."""
            d = func()
            return d

        return f

    def test_all_ok(self):
        """All ok."""
        f = self.get_decorated_func(lambda: defer.succeed(True))
        d = f()
        return d

    def test_one_fail(self):
        """One fail."""
        deferred = defer.Deferred()
        helper = self.Helper(2)
        d = self.get_decorated_func(helper)()

        def check(_):
            """Check called quantity."""
            self.assertEqual(helper.cant, 2)
            deferred.callback(True)
        d.addCallbacks(check,
                       lambda _: deferred.errback(Exception()))
        return deferred

    def test_two_fails(self):
        """Two fails."""
        deferred = defer.Deferred()
        helper = self.Helper(3)
        d = self.get_decorated_func(helper)()

        def check(_):
            """Check called quantity."""
            self.assertEqual(helper.cant, 3)
            deferred.callback(True)
        d.addCallbacks(check,
                       lambda _: deferred.errback(Exception()))
        return deferred

    def test_too_many_fails(self):
        """Check that retryal is not forever."""
        deferred = defer.Deferred()
        helper = self.Helper(12)
        d = self.get_decorated_func(helper)()

        d.addCallbacks(lambda _: deferred.errback(Exception()),
                       lambda _: deferred.callback(True))
        return deferred

    def test_other_exception(self):
        """Less fails than limit, but not retrying exception."""
        deferred = defer.Deferred()
        helper = self.Helper(2, excep=NameError("foo"))
        d = self.get_decorated_func(helper)()

        d.addCallbacks(lambda _: deferred.errback(Exception()),
                       lambda _: deferred.callback(True))
        return deferred


class HandlingSharesTestCase(SafeTestCase):
    """Handle shares."""

    @defer.inlineCallbacks
    def test_accept_share_ok(self):
        """Accepting share finishes ok."""
        d = dict(volume_id='foo', answer='bar')
        self.fake_sdt_response('accept_share', d)
        yield self.dbus.accept_share('foo')
        self.assertTrue(self.handler.check_debug(
                        "Accept share foo started", "foo"))
        self.assertTrue(self.handler.check_debug(
                        "Accept share foo finished", str(d)))

    @defer.inlineCallbacks
    def test_accept_share_bad(self):
        """Accepting share finishes bad."""
        d = dict(volume_id='foo', answer='bar', error='baz')
        self.fake_sdt_response('accept_share', d)
        try:
            yield self.dbus.accept_share('foo')
        except dbusiface.ShareOperationError, e:
            self.assertEqual(e.share_id, 'foo')
            self.assertEqual(e.error, 'baz')
        else:
            raise Exception("Test should have raised an exception")
        self.assertTrue(self.handler.check_debug(
                        "Accept share foo started", "foo"))
        self.assertTrue(self.handler.check_debug(
                        "Accept share foo finished", str(d)))

    @defer.inlineCallbacks
    def test_accept_share_ugly_error(self):
        """Accepting share went really bad."""
        e = dbus.exceptions.DBusException('ugly!')
        self.fake_sdt_response('accept_share', e)
        try:
            yield self.dbus.accept_share('foo')
        except dbusiface.ShareOperationError, e:
            self.assertEqual(e.share_id, 'foo')
            self.assertEqual(e.error, "ugly!")
        else:
            raise Exception("Test should have raised an exception")
        self.assertTrue(self.handler.check_debug(
                        "Accept share foo started", "foo"))
        self.assertTrue(self.handler.check_debug(
                        "Accept share foo crashed", "ugly!"))

    @defer.inlineCallbacks
    def test_reject_share_ok(self):
        """Rejecting share finishes ok."""
        d = dict(volume_id='foo', answer='bar')
        self.fake_sdt_response('reject_share', d)
        yield self.dbus.reject_share('foo')
        self.assertTrue(self.handler.check_debug(
                        "Reject share foo started", "foo"))
        self.assertTrue(self.handler.check_debug(
                        "Reject share foo finished", str(d)))

    @defer.inlineCallbacks
    def test_reject_share_bad(self):
        """Rejecting share finishes bad."""
        d = dict(volume_id='foo', answer='bar', error='baz')
        self.fake_sdt_response('reject_share', d)
        try:
            yield self.dbus.reject_share('foo')
        except dbusiface.ShareOperationError, e:
            self.assertEqual(e.share_id, 'foo')
            self.assertEqual(e.error, 'baz')
        else:
            raise Exception("Test should have raised an exception")
        self.assertTrue(self.handler.check_debug(
                        "Reject share foo started", "foo"))
        self.assertTrue(self.handler.check_debug(
                        "Reject share foo finished", str(d)))

    @defer.inlineCallbacks
    def test_reject_share_ugly_error(self):
        """Rejecting share went really bad."""
        e = dbus.exceptions.DBusException('ugly!')
        self.fake_sdt_response('reject_share', e)
        try:
            yield self.dbus.reject_share('foo')
        except dbusiface.ShareOperationError, e:
            self.assertEqual(e.share_id, 'foo')
            self.assertEqual(e.error, "ugly!")
        else:
            raise Exception("Test should have raised an exception")
        self.assertTrue(self.handler.check_debug(
                        "Reject share foo started", "foo"))
        self.assertTrue(self.handler.check_debug(
                        "Reject share foo crashed", "ugly!"))

    @defer.inlineCallbacks
    def test_send_share_invitation_ok(self):
        """Sending a share invitation finishes ok."""
        self.fake_sdt_response('send_share_invitation', None)
        self.handler.debug = True
        yield self.dbus.send_share_invitation('path', 'mail_address',
                                              'sh_name', 'access_level')
        self.assertTrue(self.handler.check_debug(
                        "Send share invitation started", "path",
                        "mail_address", "sh_name", "access_level"))
        self.assertTrue(self.handler.check_debug(
                        "Send share invitation finished ok", "path",
                        "mail_address", "sh_name", "access_level"))

    @defer.inlineCallbacks
    def test_send_share_invitation_error(self):
        """Sending a share invitation went bad."""
        e = dbus.exceptions.DBusException('ugly!')
        self.fake_sdt_response('send_share_invitation', e)
        try:
            yield self.dbus.send_share_invitation('path', 'mail_address',
                                                  'sh_name', 'access_level')
        except dbusiface.ShareOperationError, e:
            self.assertEqual(e.error, "ugly!")
        else:
            raise Exception("Test should have raised an exception")
        self.assertTrue(self.handler.check_debug(
                        "Send share invitation started", "path",
                        "mail_address", "sh_name", "access_level"))
        self.assertTrue(self.handler.check_debug(
                        "Send share invitation crashed", "ugly", "path",
                        "mail_address", "sh_name", "access_level"))

    @defer.inlineCallbacks
    def test_subscribe_ok(self):
        """Subscribing a share finishes ok."""
        self.fake_sdt_response('subscribe_share', (None,))
        result = yield self.dbus.subscribe_share('share_id')
        self.assertEqual(result, None)
        self.assertTrue(self.handler.check_debug(
                        "Subscribe share share_id started"))
        self.assertTrue(self.handler.check_debug(
                        "Subscribe share share_id finished"))

    @defer.inlineCallbacks
    def test_subscribe_error(self):
        """Subscribing a share finishes bad."""
        exc = ValueError('ShareSubscribeError',
                         (dict(id='share_id'), 'DOES_NOT_EXIST'))
        self.fake_sdt_response('subscribe_share', exc)
        res = self.dbus.subscribe_share('share_id')
        raised = yield self.assertFailure(res, dbusiface.ShareOperationError)
        self.assertEqual(raised.share_id, 'share_id')
        self.assertEqual(raised.error, "ShareSubscribeError (DOES_NOT_EXIST)")
        self.handler.debug = True
        self.assertTrue(self.handler.check_debug(
                        "Subscribe share share_id started"))
        self.assertTrue(self.handler.check_debug(
                        "Subscribe share share_id crashed",
                        "ShareSubscribeError", "DOES_NOT_EXIST"))

    @defer.inlineCallbacks
    def test_unsubscribe_ok(self):
        """Subscribing a share finishes ok."""
        self.fake_sdt_response('unsubscribe_share', (None,))
        result = yield self.dbus.unsubscribe_share('share_id')
        self.assertEqual(result, None)
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe share share_id started"))
        self.handler.debug = True
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe share share_id finished"))

    @defer.inlineCallbacks
    def test_unsubscribe_error(self):
        """Subscribing a share finishes bad."""
        exc = ValueError('ShareUnsubscribeError',
                         (dict(id='share_id'), 'DOES_NOT_EXIST'))
        self.fake_sdt_response('unsubscribe_share', exc)
        res = self.dbus.unsubscribe_share('share_id')
        raised = yield self.assertFailure(res, dbusiface.ShareOperationError)
        self.assertEqual(raised.share_id, 'share_id')
        self.assertEqual(raised.error,
                         "ShareUnsubscribeError (DOES_NOT_EXIST)")
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe share share_id started"))
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe share share_id crashed",
                        "ShareUnsubscribeError", "DOES_NOT_EXIST"))


class HandlingFoldersTestCase(SafeTestCase):
    """Handle folders (UDFs)."""

    @defer.inlineCallbacks
    def test_create_ok(self):
        """Creating a folder finishes ok."""
        d = dict(node_id='nid', path=u'pth', subscribed='True', generation='5',
                 suggested_path=u'sgp', type='UDF', volume_id='vid')
        self.fake_sdt_response('create_folder', d)
        result = yield self.dbus.create_folder('pth')
        self.assertEqual(result.path, 'pth')
        self.assertEqual(result.suggested_path, 'sgp')
        self.assertEqual(result.node, 'nid')
        self.assertEqual(result.volume, 'vid')
        self.assertEqual(result.subscribed, True)
        self.assertTrue(self.handler.check_debug(
                        "Create folder started", "pth"))
        self.assertTrue(self.handler.check_debug(
                        "Create folder finished ok", str(d)))

    @defer.inlineCallbacks
    def test_create_error(self):
        """Creating a folder finishes bad."""
        exc = ValueError('FolderCreateError',
                         (dict(path='pth'), 'Invalid path'))
        self.fake_sdt_response('create_folder', exc)
        res = self.dbus.create_folder('pth')
        raised = yield self.assertFailure(res, dbusiface.FolderOperationError)
        self.assertEqual(raised.path, 'pth')
        self.assertEqual(raised.volume_id, None)
        self.assertEqual(raised.error, "FolderCreateError (Invalid path)")
        self.assertTrue(self.handler.check_debug(
                        "Create folder started", "pth"))
        self.assertTrue(self.handler.check_debug(
                        "Create folder finished with error",
                        "FolderCreateError", "Invalid path"))

    @defer.inlineCallbacks
    def test_delete_ok(self):
        """Deleting a folder finishes ok."""
        d = dict(node_id='nid', path=u'pth', subscribed='', generation='5',
                 suggested_path=u'sgp', type='UDF', volume_id='vid')
        self.fake_sdt_response('delete_folder', d)
        result = yield self.dbus.delete_folder('vid')
        self.assertEqual(result.path, 'pth')
        self.assertEqual(result.suggested_path, 'sgp')
        self.assertEqual(result.node, 'nid')
        self.assertEqual(result.volume, 'vid')
        self.assertEqual(result.subscribed, False)
        self.assertTrue(self.handler.check_debug(
                        "Delete folder started", "vid"))
        self.assertTrue(self.handler.check_debug(
                        "Delete folder finished ok", str(d)))

    @defer.inlineCallbacks
    def test_delete_error(self):
        """Deleting a folder finishes bad."""
        exc = ValueError('FolderDeleteError',
                         (dict(path='pth'), 'Invalid id'))
        self.fake_sdt_response('delete_folder', exc)
        res = self.dbus.delete_folder('vid')
        raised = yield self.assertFailure(res, dbusiface.FolderOperationError)
        self.assertEqual(raised.path, None)
        self.assertEqual(raised.volume_id, 'vid')
        self.assertEqual(raised.error, "FolderDeleteError (Invalid id)")
        self.assertTrue(self.handler.check_debug(
                        "Delete folder started", "vid"))
        self.assertTrue(self.handler.check_debug(
                        "Delete folder finished with error",
                        "FolderDeleteError", "Invalid id"))

    @defer.inlineCallbacks
    def test_subscribe_ok(self):
        """Subscribing a folder finishes ok."""
        d = dict(node_id='nid', path=u'pth', subscribed='', generation='5',
                 suggested_path=u'sgp', type='UDF', volume_id='vid')
        self.fake_sdt_response('subscribe_folder', d)
        result = yield self.dbus.subscribe_folder('vid')
        self.assertEqual(result.path, 'pth')
        self.assertEqual(result.suggested_path, 'sgp')
        self.assertEqual(result.node, 'nid')
        self.assertEqual(result.volume, 'vid')
        self.assertEqual(result.subscribed, False)
        self.assertTrue(self.handler.check_debug(
                        "Subscribe folder started", "vid"))
        self.assertTrue(self.handler.check_debug(
                        "Subscribe folder finished ok", str(d)))

    @defer.inlineCallbacks
    def test_subscribe_error(self):
        """Subscribing a folder finishes bad."""
        exc = ValueError('FolderSubscribeError',
                         (dict(path='pth'), 'Invalid id'))
        self.fake_sdt_response('subscribe_folder', exc)
        res = self.dbus.subscribe_folder('vid')
        raised = yield self.assertFailure(res, dbusiface.FolderOperationError)
        self.assertEqual(raised.path, None)
        self.assertEqual(raised.volume_id, 'vid')
        self.assertEqual(raised.error, "FolderSubscribeError (Invalid id)")
        self.assertTrue(self.handler.check_debug(
                        "Subscribe folder started", "vid"))
        self.assertTrue(self.handler.check_debug(
                        "Subscribe folder finished with error",
                        "FolderSubscribeError", "Invalid id"))

    @defer.inlineCallbacks
    def test_unsubscribe_ok(self):
        """Subscribing a folder finishes ok."""
        d = dict(node_id='nid', path=u'pth', subscribed='', generation='5',
                 suggested_path=u'sgp', type='UDF', volume_id='vid')
        self.fake_sdt_response('unsubscribe_folder', d)
        result = yield self.dbus.unsubscribe_folder('vid')
        self.assertEqual(result.path, 'pth')
        self.assertEqual(result.suggested_path, 'sgp')
        self.assertEqual(result.node, 'nid')
        self.assertEqual(result.volume, 'vid')
        self.assertEqual(result.subscribed, False)
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe folder started", "vid"))
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe folder finished ok", str(d)))

    @defer.inlineCallbacks
    def test_unsubscribe_error(self):
        """Subscribing a folder finishes bad."""
        exc = ValueError('FolderUnsubscribeError',
                         (dict(path='pth'), 'Invalid id'))
        self.fake_sdt_response('unsubscribe_folder', exc)
        res = self.dbus.unsubscribe_folder('vid')
        raised = yield self.assertFailure(res, dbusiface.FolderOperationError)
        self.assertEqual(raised.path, None)
        self.assertEqual(raised.volume_id, 'vid')
        self.assertEqual(raised.error, "FolderUnsubscribeError (Invalid id)")
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe folder started", "vid"))
        self.assertTrue(self.handler.check_debug(
                        "Unsubscribe folder finished with error",
                        "FolderUnsubscribeError", "Invalid id"))
