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

"""Tests for the SyncDaemon communication backend."""

import logging
import os
import unittest
import user

from twisted.internet import defer, reactor
from twisted.trial.unittest import TestCase as TwistedTestCase
from ubuntuone.devtools.handlers import MementoHandler

from magicicada.dbusiface import (
    FolderData,
    FolderOperationError,
    NOT_SYNCHED_PATH,
    PublicFilesData,
    ShareOperationError,
)
from magicicada.syncdaemon import (
    CHANGED_LOCAL,
    CHANGED_NONE,
    CHANGED_SERVER,
    INTERNAL_OP,
    NODE_OP,
    Poller,
    STATE_CONNECTING,
    STATE_DISCONNECTED,
    STATE_IDLE,
    STATE_STARTING,
    STATE_STOPPED,
    STATE_WORKING,
    State,
    SyncDaemon,
    TRANSFER_POLL_INTERVAL,
    mandatory_callback,
)


# It's ok to access private data in the test suite
# pylint: disable=W0212

# Lambda may not be necessary
# pylint: disable=W0108


class FakeQueueContent(object):
    """Fake queue content."""
    transferring = False
    set_content = set_shares_dirs = add = remove = lambda *a: None


class FakeDBusInterface(object):
    """Fake DBus Interface, for SD to not use dbus at all during tests."""

    fake_sd_started = False
    fake_pf_data = PublicFilesData(volume='v', node='n',
                                   path='p', public_url='u')
    fake_share_response = None
    fake_folder_response = None
    fake_change_public_access = None

    def __init__(self, sd):
        pass

    def shutdown(self):
        """Fake shutdown."""

    def get_status(self):
        """Fake status."""
        return defer.succeed(('fakename', 'fakedescrip', False, True,
                              False, 'fakequeues', 'fakeconnection'))

    def get_folders(self):
        """Fake folders."""
        return defer.succeed('fakedata')

    start = quit = connect = disconnect = get_folders
    get_shares_to_me = get_shares_to_others = get_folders

    def get_queue_content(self):
        """Fake queue content."""
        return defer.succeed([])

    def get_public_files(self):
        """Fake public files."""
        return defer.succeed([self.fake_pf_data])

    def is_sd_started(self):
        """Fake response."""
        return self.fake_sd_started

    def accept_share(self, *a):
        """Fake share handling."""
        return self.fake_share_response

    send_share_invitation = reject_share = accept_share
    subscribe_share = unsubscribe_share = accept_share

    def create_folder(self, *a):
        """Fake folder handling."""
        return self.fake_folder_response

    delete_folder = subscribe_folder = unsubscribe_folder = create_folder

    def get_link_shares_dir(self):
        """Fake shares dir."""
        return defer.succeed(user.home)

    get_real_shares_dir = get_link_shares_dir

    def change_public_access(self, *a):
        """Fake change public access."""
        return self.fake_change_public_access


class BaseTestCase(TwistedTestCase):
    """Base test with a SD."""

    timeout = 1

    def setUp(self):
        """Set up."""
        self.hdlr = MementoHandler()
        self.hdlr.setLevel(logging.DEBUG)
        logger = logging.getLogger('magicicada.syncdaemon')
        logger.addHandler(self.hdlr)
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.removeHandler, self.hdlr)

        self.sd = SyncDaemon(FakeDBusInterface)
        self.addCleanup(self.sd.shutdown)


class MandatoryCallbackTestCase(BaseTestCase):
    """Tests for the mandatory callback generic function."""

    def test_log_function_name(self):
        """Log the function name."""
        some_function = mandatory_callback('bar')
        some_function()
        self.assertTrue(self.hdlr.check_warning(
                        "Callback called but was not assigned", "bar"))

    def test_log_args(self):
        """Log the arguments."""
        some_function = mandatory_callback('bar')
        some_function(1, 2, b=45)
        self.assertTrue(self.hdlr.check_warning(
                        "Callback called but was not assigned",
                        "1", "2", "'b': 45"))


class InitialDataTestCase(unittest.TestCase):
    """Tests for initial data gathering."""

    def setUp(self):
        """Set up the test."""
        self.sd = SyncDaemon(FakeDBusInterface)

        self.offline_called = False
        self.sd.on_initial_data_ready_callback = \
            lambda: setattr(self, 'offline_called', True)
        self.online_called = False
        self.sd.on_initial_online_data_ready_callback = \
            lambda: setattr(self, 'online_called', True)

    def tearDown(self):
        """Tear down the test."""
        self.sd.shutdown()

    def test_called_by_start(self):
        """Check that start calls get initial data."""
        sd = SyncDaemon(FakeDBusInterface)
        called = []
        sd._get_initial_data = lambda: called.append(True)
        sd.start()
        self.assertTrue(called)

    def test_called_beggining_no(self):
        """Check that it should not be called if no SD."""
        called = []
        orig_met = SyncDaemon._get_initial_data
        SyncDaemon._get_initial_data = lambda s: called.append(True)
        SyncDaemon(FakeDBusInterface)
        SyncDaemon._get_initial_data = orig_met
        self.assertFalse(called)

    def test_called_beggining_yes(self):
        """Check that it should be called if SD already started."""
        called = []
        orig_met = SyncDaemon._get_initial_data
        SyncDaemon._get_initial_data = lambda s: called.append(True)
        FakeDBusInterface.fake_sd_started = True
        SyncDaemon(FakeDBusInterface)
        SyncDaemon._get_initial_data = orig_met
        self.assertTrue(called)

    def test_calls_callbacks(self):
        """Check that initial data calls the callbacks for new data."""
        called = []
        sd = SyncDaemon(FakeDBusInterface)
        sd.status_changed_callback = lambda *a, **kw: called.append(True)
        sd._get_initial_data()
        self.assertTrue(called)

    def test_public_files_info(self):
        """Check we get the public files info at start."""
        sd = SyncDaemon(FakeDBusInterface)
        fake_data = FakeDBusInterface.fake_pf_data
        sd._get_initial_data()
        self.assertEqual(sd.public_files, [fake_data])

    def test_all_ready(self):
        """All data is ready."""
        self.sd._get_initial_data()
        self.assertTrue(self.offline_called)
        self.assertTrue(self.online_called)

    def test_no_public_files(self):
        """Initial gathering is stuck in public files."""
        self.sd.dbus.get_public_files = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertTrue(self.offline_called)
        self.assertFalse(self.online_called)

    def test_no_shares_to_others(self):
        """Initial gathering is stuck in shares to others."""
        self.sd.dbus.get_shares_to_others = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)

    def test_no_shares_to_me(self):
        """Initial gathering is stuck in shares to me."""
        self.sd.dbus.get_shares_to_me = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)

    def test_no_folders(self):
        """Initial gathering is stuck in folders."""
        self.sd.dbus.get_folders = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)

    def test_no_queue_content(self):
        """Initial gathering is stuck in queue content."""
        self.sd.dbus.get_queue_content = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)

    def test_queue_content_processed(self):
        """Initial gathering is stuck in queue content."""
        called = []
        self.sd.dbus.get_queue_content = lambda: defer.succeed((1, 2, 3))
        self.sd.queue_content.set_content = lambda a: called.append(a)
        self.sd._get_initial_data()
        self.assertEqual(called[0], (1, 2, 3))

    def test_no_status(self):
        """Initial gathering is stuck in status."""
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)

    def test_real_shares_dir_for_queue_content(self):
        """Initial dirs are called for queue content."""
        self.sd.dbus.get_real_shares_dir = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)

    def test_link_shares_dir_for_queue_content(self):
        """Initial dirs are called for queue content."""
        self.sd.dbus.get_link_shares_dir = lambda: defer.Deferred()
        self.sd._get_initial_data()
        self.assertFalse(self.offline_called)
        self.assertFalse(self.online_called)


class StatusChangedTestCase(BaseTestCase):
    """Simple signals checking."""

    @defer.inlineCallbacks
    def test_initial_value(self):
        """Fill the status info initially."""
        called = []

        def fake():
            """Fake method."""
            called.append(True)
            return defer.succeed(('fakename', 'fakedescrip', False, True,
                                  False, 'fakequeues', 'fakeconnection'))

        self.sd.dbus.get_status = fake
        yield self.sd._get_initial_data()
        self.assertTrue(called)

    def test_statuschanged_stopped(self):
        """Test StatusChanged signal with status STOPPED."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'SHUTDOWN')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, True)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'connection')
            self.assertEqual(state, STATE_STOPPED)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.on_sd_status_changed('SHUTDOWN', 'description', False,
                                     True, False, 'IDLE', 'connection')
        return deferred

    def test_statuschanged_idle(self):
        """Test StatusChanged signal with status IDLE."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'QUEUE_MANAGER')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, True)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'connection')
            self.assertEqual(state, STATE_IDLE)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.on_sd_status_changed('QUEUE_MANAGER', 'description', False,
                                     True, False, 'IDLE', 'connection')
        return deferred

    def test_statuschanged_working(self):
        """Test StatusChanged signal with status WORKING."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'QUEUE_MANAGER')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, True)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'WORKING')
            self.assertEqual(connection, 'connection')
            self.assertEqual(state, STATE_WORKING)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.on_sd_status_changed('QUEUE_MANAGER', 'description', False,
                                     True, False, 'WORKING', 'connection')
        return deferred

    def test_statuschanged_connecting_after_ready(self):
        """Test StatusChanged signal with status CONNECTION."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'SERVER_RESCAN')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, True)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'connection')
            self.assertEqual(state, STATE_CONNECTING)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.on_sd_status_changed('SERVER_RESCAN', 'description', False,
                                     True, False, 'IDLE', 'connection')
        return deferred

    def test_statuschanged_starting(self):
        """Test StatusChanged signal with status STARTING."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'LOCAL_RESCAN')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, False)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'connectn')
            self.assertEqual(state, STATE_STARTING)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd.on_sd_status_changed('LOCAL_RESCAN', 'description', False,
                                     False, False, 'IDLE', 'connectn')
        return deferred

    def test_statuschanged_connecting_ready(self):
        """Test StatusChanged signal when READY to connect."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'READY')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, False)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'With User With Network')
            self.assertEqual(state, STATE_CONNECTING)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd.on_sd_status_changed('READY', 'description', False, False,
                                     False, 'IDLE', 'With User With Network')
        return deferred

    def test_statuschanged_disconnected_ready(self):
        """Test StatusChanged signal when READY but not to connect."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'READY')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, False)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'not with both in with')
            self.assertEqual(state, STATE_DISCONNECTED)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd.on_sd_status_changed('READY', 'description', False, False,
                                     False, 'IDLE', 'not with both in with')
        return deferred

    def test_statuschanged_connecting_waiting(self):
        """Test StatusChanged signal when WAITING to connect."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'WAITING')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, False)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'With User With Network')
            self.assertEqual(state, STATE_CONNECTING)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd.on_sd_status_changed('WAITING', 'description', False, False,
                                     False, 'IDLE', 'With User With Network')
        return deferred

    def test_statuschanged_disconnected_waiting(self):
        """Test StatusChanged signal when WAITING but not to connect."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'WAITING')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, False)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'not with both in with')
            self.assertEqual(state, STATE_DISCONNECTED)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd.on_sd_status_changed('WAITING', 'description', False, False,
                                     False, 'IDLE', 'not with both in with')
        return deferred

    def test_statuschanged_standoff(self):
        """Test StatusChanged signal when STANDOFF."""
        deferred = defer.Deferred()

        def callback(name, description, is_error, is_connected, is_online,
                     queues, connection, state):
            """Check received data."""
            self.assertEqual(name, 'STANDOFF')
            self.assertEqual(description, 'description')
            self.assertEqual(is_error, False)
            self.assertEqual(is_connected, False)
            self.assertEqual(is_online, False)
            self.assertEqual(queues, 'IDLE')
            self.assertEqual(connection, 'With User With Network')
            self.assertEqual(state, STATE_DISCONNECTED)
            deferred.callback(True)

        self.sd.status_changed_callback = callback
        self.sd.dbus.get_status = lambda: defer.Deferred()
        self.sd.on_sd_status_changed('STANDOFF', 'description', False, False,
                                     False, 'IDLE', 'With User With Network')
        return deferred

    def test_status_changed_affects_current_status(self):
        """Make changes to see how status are reflected."""
        # one set of values
        self.sd.on_sd_status_changed('name1', 'description1', False, True,
                                     False, 'queues1', 'connection1')
        self.assertEqual(self.sd.current_state.name, 'name1')
        self.assertEqual(self.sd.current_state.description, 'description1')
        self.assertEqual(self.sd.current_state.is_error, False)
        self.assertEqual(self.sd.current_state.is_connected, True)
        self.assertEqual(self.sd.current_state.is_online, False)
        self.assertEqual(self.sd.current_state.queues, 'queues1')
        self.assertEqual(self.sd.current_state.connection, 'connection1')

        # again, to be sure they actually are updated
        self.sd.on_sd_status_changed('name2', 'description2', True, False,
                                     True, 'queues2', 'connection2')
        self.assertEqual(self.sd.current_state.name, 'name2')
        self.assertEqual(self.sd.current_state.description, 'description2')
        self.assertEqual(self.sd.current_state.is_error, True)
        self.assertEqual(self.sd.current_state.is_connected, False)
        self.assertEqual(self.sd.current_state.is_online, True)
        self.assertEqual(self.sd.current_state.queues, 'queues2')
        self.assertEqual(self.sd.current_state.connection, 'connection2')

    def test_is_started_fixed_at_init_no(self):
        """Status.is_started is set at init time, to no."""
        FakeDBusInterface.fake_sd_started = False
        sd = SyncDaemon(FakeDBusInterface)
        self.assertFalse(sd.current_state.is_started)

    def test_is_started_fixed_at_init_yes(self):
        """Status.is_started is set at init time, to yes."""
        FakeDBusInterface.fake_sd_started = True
        sd = SyncDaemon(FakeDBusInterface)
        self.assertTrue(sd.current_state.is_started)

    def test_on_stopped(self):
        """Stopped affects the status."""
        called = []
        self.sd.on_stopped_callback = lambda: called.append(True)
        self.sd.on_sd_status_changed('SHUTDOWN', 'description', False,
                                     False, False, '', '')
        self.assertEqual(self.sd.current_state.name, 'SHUTDOWN')
        self.assertEqual(self.sd.current_state.description, 'description')
        self.assertEqual(self.sd.current_state.is_error, False)
        self.assertEqual(self.sd.current_state.is_connected, False)
        self.assertEqual(self.sd.current_state.is_online, False)
        self.assertEqual(self.sd.current_state.queues, '')
        self.assertEqual(self.sd.current_state.connection, '')
        self.assertEqual(self.sd.current_state.state, STATE_STOPPED)
        self.assertEqual(self.sd.current_state.is_started, False)
        self.assertTrue(called)

    def test_logging(self):
        """Test how the info is logged."""
        self.sd.on_sd_status_changed('QUEUE_MANAGER', 'description', False,
                                     True, False, 'IDLE', 'connection')
        should = (
            "new status:",
            "name='QUEUE_MANAGER'",
            "description='description'",
            "is_error=False",
            "is_connected=True",
            "is_online=False",
            "queues='IDLE'",
            "connection='connection'",
            "state=u'IDLE'",
        )
        self.assertTrue(self.hdlr.check_debug(*should))


class QueueChangedTestCase(BaseTestCase):
    """Check the RequestQueueAdded and RequestQueueRemoved handling."""

    def test_queueadded_without_setting_callback(self):
        """It should work even if not hooking into the callback."""
        self.sd.on_sd_queue_added('name', 'id', {})

    def test_queueremoved_without_setting_callback(self):
        """It should work even if not hooking into the callback."""
        self.sd.on_sd_queue_removed('name', 'id', {})

    def test_node_ops_callback_call_on_queueadded(self):
        """Call the node callback when queue added."""
        node_cback = []
        internal_cback = []
        self.sd.on_node_ops_changed_callback = lambda a: node_cback.append(a)
        self.sd.on_internal_ops_changed_callback = \
            lambda a: internal_cback.append(a)
        self.sd.queue_content.add = lambda *a: NODE_OP
        self.sd.on_sd_queue_added('node', 'id', {})
        self.assertEqual(node_cback, [self.sd.queue_content.node_ops])
        self.assertFalse(internal_cback)

    def test_internal_ops_callback_call_on_queueadded(self):
        """Call the internal callback when queue added."""
        node_cback = []
        internal_cback = []
        self.sd.on_node_ops_changed_callback = lambda a: node_cback.append(a)
        self.sd.on_internal_ops_changed_callback = \
            lambda a: internal_cback.append(a)
        self.sd.queue_content.add = lambda *a: INTERNAL_OP
        self.sd.on_sd_queue_added('internal', 'id', {})
        self.assertEqual(internal_cback, [self.sd.queue_content.internal_ops])
        self.assertFalse(node_cback)

    def test_no_callback_call_on_queueadded(self):
        """Don't call the internal callback when nothing added."""
        node_cback = []
        internal_cback = []
        self.sd.on_node_ops_changed_callback = lambda a: node_cback.append(a)
        self.sd.on_internal_ops_changed_callback = \
            lambda a: internal_cback.append(a)
        self.sd.queue_content.add = lambda *a: None
        self.sd.on_sd_queue_added('dont care', 'id', {})
        self.assertFalse(node_cback)
        self.assertFalse(internal_cback)

    def test_node_ops_callback_call_on_queueremoved(self):
        """Call the node callback when queue removed."""
        node_cback = []
        internal_cback = []
        self.sd.on_node_ops_changed_callback = lambda a: node_cback.append(a)
        self.sd.on_internal_ops_changed_callback = \
            lambda a: internal_cback.append(a)
        self.sd.queue_content.remove = lambda *a: NODE_OP
        self.sd.on_sd_queue_removed('node', 'id', {})
        self.assertEqual(node_cback, [self.sd.queue_content.node_ops])
        self.assertFalse(internal_cback)

    def test_internal_ops_callback_call_on_queueremoved(self):
        """Call the internal callback when queue removed."""
        node_cback = []
        internal_cback = []
        self.sd.on_node_ops_changed_callback = lambda a: node_cback.append(a)
        self.sd.on_internal_ops_changed_callback = \
            lambda a: internal_cback.append(a)
        self.sd.queue_content.remove = lambda *a: INTERNAL_OP
        self.sd.on_sd_queue_removed('internal', 'id', {})
        self.assertEqual(internal_cback, [self.sd.queue_content.internal_ops])
        self.assertFalse(node_cback)

    def test_no_callback_call_on_queueremoved(self):
        """Don't call the internal callback when nothing removed."""
        node_cback = []
        internal_cback = []
        self.sd.on_node_ops_changed_callback = lambda a: node_cback.append(a)
        self.sd.on_internal_ops_changed_callback = \
            lambda a: internal_cback.append(a)
        self.sd.queue_content.remove = lambda *a: None
        self.sd.on_sd_queue_removed('dont care', 'id', {})
        self.assertFalse(node_cback)
        self.assertFalse(internal_cback)

    def test_queueadded_add_to_queuecontent(self):
        """Call the queue_content's add when queue added."""
        called = []
        self.sd.queue_content.add = lambda *a: called.append(a)
        self.sd.on_sd_queue_added('name', 'id', {})
        self.assertEqual(called, [('name', 'id', {})])

    def test_queueremoved_remove_to_queuecontent(self):
        """Call the queue_content's remove when queue removed."""
        called = []
        self.sd.queue_content.remove = lambda *a: called.append(a)
        self.sd.on_sd_queue_removed('name', 'id', {})
        self.assertEqual(called, [('name', 'id', {})])


class StateTestCase(unittest.TestCase):
    """Test State class."""

    def test_initial(self):
        """Initial state for vals."""
        st = State()
        self.assertEqual(st.name, '')

    def test_set_one_value(self):
        """Set one value."""
        st = State()
        st.set(name=55)

        # check the one is set, the rest not
        self.assertEqual(st.name, 55)
        self.assertEqual(st.description, '')

    def test_set_two_values(self):
        """Set two values."""
        st = State()
        st.set(name=55, description=77)

        # check those two are set, the rest not
        self.assertEqual(st.name, 55)
        self.assertEqual(st.description, 77)
        self.assertFalse(st.is_error)

    def test_bad_value(self):
        """Set a value that should not."""
        st = State()
        self.assertRaises(AttributeError, st.set, not_really_allowed=44)


class APITestCase(TwistedTestCase):
    """Check exposed methods and attributes."""

    def setUp(self):
        """Set up the test."""
        self.sd = SyncDaemon(FakeDBusInterface)

        self._replaced = None
        self.called = False

    def tearDown(self):
        """Tear down the test."""
        if self._replaced is not None:
            setattr(*self._replaced)
        self.sd.shutdown()

    def flag_called(self, obj, method_name):
        """Replace callback to flag called."""
        f = lambda *a, **k: setattr(self, 'called', True)
        setattr(obj, method_name, f)

    def test_start(self):
        """Test start calls SD."""
        deferred = object()
        self.patch(self.sd.dbus, 'start', lambda: deferred)
        res = self.sd.start()
        self.assertIdentical(res, deferred)

    def test_quit(self):
        """Test quit calls SD."""
        deferred = object()
        self.patch(self.sd.dbus, 'quit', lambda: deferred)
        res = self.sd.quit()
        self.assertIdentical(res, deferred)

    def test_connect(self):
        """Test connect calls SD."""
        deferred = object()
        self.patch(self.sd.dbus, 'connect', lambda: deferred)
        res = self.sd.connect()
        self.assertIdentical(res, deferred)

    def test_disconnect(self):
        """Test disconnect calls SD."""
        deferred = object()
        self.patch(self.sd.dbus, 'disconnect', lambda: deferred)
        res = self.sd.disconnect()
        self.assertIdentical(res, deferred)

    def test_on_connected(self):
        """Called when SD connected."""
        self.flag_called(self.sd, 'on_connected_callback')

        # first signal with connected in True
        self.sd.on_sd_status_changed('name', 'description', False, True,
                                     False, 'queues', 'connection')
        self.assertTrue(self.called)

    def test_on_disconnected(self):
        """Called when SD disconnected."""
        self.flag_called(self.sd, 'on_disconnected_callback')

        # connect and disconnect
        self.sd.on_sd_status_changed('name', 'description', False, True,
                                     False, 'queues', 'connection')
        self.sd.on_sd_status_changed('name', 'description', False, False,
                                     False, 'queues', 'connection')
        self.assertTrue(self.called)

    def test_on_online(self):
        """Called when SD goes online."""
        self.flag_called(self.sd, 'on_online_callback')

        # first signal with online in True
        self.sd.on_sd_status_changed('name', 'description', False, True,
                                     True, 'queues', 'connection')
        self.assertTrue(self.called)

    def test_on_offline(self):
        """Called when SD goes offline."""
        self.flag_called(self.sd, 'on_offline_callback')

        # go online and then offline
        self.sd.on_sd_status_changed('name', 'description', False, True,
                                     True, 'queues', 'connection')
        self.sd.on_sd_status_changed('name', 'description', False, True,
                                     False, 'queues', 'connection')
        self.assertTrue(self.called)


class LogsTestCase(unittest.TestCase):
    """Test logging."""

    def setUp(self):
        """Set up."""
        self.hdlr = MementoHandler()
        self.hdlr.setLevel(logging.DEBUG)
        logger = logging.getLogger('magicicada.syncdaemon')
        logger.addHandler(self.hdlr)
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.removeHandler, self.hdlr)
        self.sd = SyncDaemon(FakeDBusInterface)

    def tearDown(self):
        """Shut down!"""
        self.sd.shutdown()

    def test_instancing(self):
        """Just logged SD instancing."""
        self.assertTrue(self.hdlr.check_info("SyncDaemon interface started!"))

    def test_shutdown(self):
        """Log when SD shutdowns."""
        self.sd.shutdown()
        msg = "SyncDaemon interface going down"
        self.assertTrue(self.hdlr.check_info(msg))

    @defer.inlineCallbacks
    def test_initial_value(self):
        """Log the initial filling."""
        yield self.sd._get_initial_data()
        self.assertTrue(self.hdlr.check_info("Getting offline initial data"))
        self.assertTrue(self.hdlr.check_info(
                        "All initial offline data is ready"))
        self.assertTrue(self.hdlr.check_info("Getting online initial data"))
        self.assertTrue(self.hdlr.check_info(
                        "All initial online data is ready"))

    def test_start(self):
        """Log the call to start."""
        self.sd.start()
        self.assertTrue(self.hdlr.check_info("Starting u1.SD"))

    def test_quit(self):
        """Log the call to quit."""
        self.sd.quit()
        self.assertTrue(self.hdlr.check_info("Stopping u1.SD"))

    def test_connect(self):
        """Log the call to connect."""
        self.sd.connect()
        self.assertTrue(self.hdlr.check_info("Telling u1.SD to connect"))

    def test_disconnect(self):
        """Log the call to disconnect."""
        self.sd.disconnect()
        self.assertTrue(self.hdlr.check_info("Telling u1.SD to disconnect"))

    def test_on_status_changed(self):
        """Log status changed."""
        self.sd.on_sd_status_changed('name', 'description', False, True,
                                     False, 'queues', 'connection')
        self.assertTrue(self.hdlr.check_info("SD Status changed"))
        expected = (u"    new status: connection='connection', "
                    u"description='description', is_connected=True, "
                    u"is_error=False, is_online=False, name='name', "
                    u"queues='queues'")
        self.assertTrue(self.hdlr.check_debug(expected))

    def test_queue_added(self):
        """Log when something is added to the queue."""
        d = dict(somedata='foo')
        self.sd.on_sd_queue_added('Operation', 'op_id', d)
        self.assertTrue(self.hdlr.check_info("Queue content", "added",
                                             "Operation", "op_id", str(d)))

    def test_queue_removed(self):
        """Log when something is removed from the queue."""
        d = dict(somedata='foo')
        self.sd.on_sd_queue_removed('Operation', 'op_id', d)
        self.assertTrue(self.hdlr.check_info("Queue content", "removed",
                                             "Operation", "op_id", str(d)))

    def test_folders_changed(self):
        """Log when folders changed."""
        self.sd.on_sd_folders_changed()
        self.assertTrue(self.hdlr.check_info("SD Folders changed"))

    def test_shares_changed(self):
        """Log when shares changed."""
        self.sd.on_sd_shares_changed()
        self.assertTrue(self.hdlr.check_info("SD Shares changed"))

    def test_on_public_files_changed(self):
        """Log we got a new public files list."""
        pf1 = PublicFilesData(volume='v', node='n1', path='p', public_url='u')
        pf2 = PublicFilesData(volume='v', node='n2', path='p', public_url='u')
        self.sd.dbus.get_public_files = lambda: defer.succeed([pf1, pf2])
        self.sd.on_sd_public_files_changed()
        self.assertTrue(self.hdlr.check_info(
                        "Got new Public Files list (2 items)"))


class MetadataTestCase(BaseTestCase):
    """Get Metadata info."""

    def test_get_metadata_no_callback_set(self):
        """It's mandatory to set the callback for this response."""
        self.sd.on_metadata_ready_callback()
        self.assertTrue(self.hdlr.check_warning('on_metadata_ready_callback'))

    def test_get_metadata_double(self):
        """Get the metadata twice."""
        d1 = dict(stat=u'None', info_is_partial=u'False', path='path1',
                  local_hash=u'', server_hash=u'')
        d2 = dict(stat=u'None', info_is_partial=u'False', path='path2',
                  local_hash=u'', server_hash=u'')
        self.patch(os.path, 'realpath', lambda p: p)
        called = []
        fake_md = {'path1': d1, 'path2': d2}
        self.sd.dbus.get_metadata = lambda p: defer.succeed(fake_md[p])
        self.sd.on_metadata_ready_callback = lambda *a: called.append(a)
        self.sd.get_metadata('path1')
        self.sd.get_metadata('path2')
        self.assertEqual(called[0][0], 'path1')
        self.assertEqual(called[0][1]['path'], 'path1')
        self.assertEqual(called[1][0], 'path2')
        self.assertEqual(called[1][1]['path'], 'path2')

    def test_get_metadata_uses_realpath(self):
        """Ask for metadata using the realpath (LP: #612191)."""
        d = dict(stat=u'None', info_is_partial=u'False', path='path',
                 local_hash=u'', server_hash=u'')
        self.patch(os.path, 'realpath', lambda p: '/a/realpath')
        called = []
        f = lambda p: called.append(p) or defer.succeed(d)
        self.sd.dbus.get_metadata = f
        self.sd.get_metadata('/a/symlink/path')
        self.assertEqual(called, ['/a/realpath'])

    def test_processing_nodata(self):
        """No stat in the info received."""
        self.sd.dbus.get_metadata = lambda p: defer.succeed(NOT_SYNCHED_PATH)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result, NOT_SYNCHED_PATH)

    def test_processing_nostat(self):
        """No stat in the info received."""
        d = dict(stat=u'None', info_is_partial=u'False', path='path',
                 local_hash=u'', server_hash=u'')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['stat'], None)

    def test_processing_realstat(self):
        """Have stat in the result."""
        d = dict(stat='posix.stat_result(st_mode=33188, st_ino=787516L, '
                      'st_dev=2051L, st_nlink=1, st_uid=1000, st_gid=100, '
                      'st_size=48641L, st_atime=131377712, '
                      'st_mtime=131377711, st_ctime=131381137)', path='path',
                 info_is_partial=u'False', local_hash=u'', server_hash=u'')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        should = dict(st_mode=33188, st_ino=787516, st_dev=2051, st_size=48641,
                      st_uid=1000, st_gid=100, st_nlink=1, st_atime=131377712,
                      st_mtime=131377711, st_ctime=131381137)
        self.assertEqual(result['stat'], should)

    def test_processing_raw_info(self):
        """The raw result is included."""
        d = dict(stat=u'None', info_is_partial=u'False', path='path',
                 local_hash=u'', server_hash=u'')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['raw_result'], d)

    def test_processing_state_synchronized(self):
        """The node is synchronized."""
        d = dict(stat=u'None', info_is_partial=u'False', path='path',
                 local_hash=u'same', server_hash=u'same')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['changed'], CHANGED_NONE)

    def test_processing_state_downloading(self):
        """The node is downloading."""
        d = dict(stat=u'None', info_is_partial=u'True', path='path',
                 local_hash=u'one', server_hash=u'other')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['changed'], CHANGED_SERVER)

    def test_processing_state_uploading(self):
        """The node is uploading."""
        d = dict(stat=u'None', info_is_partial=u'False', path='path',
                 local_hash=u'one', server_hash=u'other')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['changed'], CHANGED_LOCAL)

    def test_processing_state_broken(self):
        """The node state is not recognized."""
        d = dict(stat=u'None', info_is_partial=u'True', path='path',
                 local_hash=u'same', server_hash=u'same')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['changed'], None)
        self.assertTrue(self.hdlr.check_warning(
                        "Bad 'changed' values", str(d)))

    def test_processing_path_in_home(self):
        """Transform the path to relative to home."""
        path = os.path.join(user.home, 'foo', 'bar')
        d = dict(stat=u'None', info_is_partial=u'True', path=path,
                 local_hash=u'same', server_hash=u'same')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['path'], os.path.join('~', 'foo', 'bar'))

    def test_processing_path_not_in_home(self):
        """Not possible to transform the path to relative to home."""
        d = dict(stat=u'None', info_is_partial=u'True', path="/not/in/home",
                 local_hash=u'same', server_hash=u'same')
        self.sd.dbus.get_metadata = lambda p: defer.succeed(d)
        called = []
        self.sd.on_metadata_ready_callback = lambda *a: called.extend(a)

        self.sd.get_metadata('dontcare')
        result = called[1]
        self.assertEqual(result['path'], "/not/in/home")


class FoldersTestCase(BaseTestCase):
    """Folders checking."""

    def test_foldercreated_callback(self):
        """Get the new data after the folders changed."""
        # set the callback
        called = []
        self.sd.dbus.get_folders = lambda: called.append(True)

        # they changed!
        self.sd.on_sd_folders_changed()

        # test
        self.assertTrue(called)

    @defer.inlineCallbacks
    def test_initial_value(self):
        """Fill the folder info initially."""
        called = []
        self.sd.dbus.get_folders = lambda: called.append(True)
        yield self.sd._get_initial_data()
        self.assertTrue(called)

    def test_folder_changed_callback(self):
        """Test that the GUI callback is called."""
        # set the callback
        called = []
        self.sd.on_folders_changed_callback = lambda *a: called.append(True)

        # they changed!
        self.sd.on_sd_folders_changed()

        # test
        self.assertTrue(called)

    def test_on_folder_op_error_callback_set(self):
        """It's mandatory to set the callback for this response."""
        self.sd.on_folder_op_error_callback()
        self.assertTrue(self.hdlr.check_warning('on_folder_op_error_callback'))

    @defer.inlineCallbacks
    def test_create_folder_ok(self):
        """Creating a folder finishes ok."""
        folder_data = FolderData(path='path', subscribed=True,
                                 node='node_id', volume='vol_id',
                                 suggested_path='sug_path')
        self.sd.dbus.fake_folder_response = defer.succeed(folder_data)
        self.sd.on_folder_op_error_callback = lambda *a: None
        self.sd.dbus.get_folders = lambda: defer.succeed([folder_data])
        assert not self.sd.folders

        # execute and test
        yield self.sd.create_folder('path')
        self.assertTrue(self.hdlr.check_info("Create folder ok", "path='path'",
                                             "volume=vol_id"))
        self.assertEqual(self.sd.folders, [folder_data])

    @defer.inlineCallbacks
    def test_create_folder_failure(self):
        """Creating a folder finishes bad."""
        called = []
        exc = FolderOperationError(error="uglyerror", path="path")
        self.sd.dbus.fake_folder_response = defer.fail(exc)
        self.sd.on_folder_op_error_callback = lambda e: called.append(e)

        # execute and test
        yield self.sd.create_folder('path')
        self.assertEqual(called, [exc])
        self.assertTrue(self.hdlr.check_info("Create folder", "uglyerror",
                                             "finished with error", "path"))

    @defer.inlineCallbacks
    def test_delete_folder_ok(self):
        """Deleting a folder finishes ok."""
        folder_data = FolderData(path='path', subscribed=True,
                                 node='node_id', volume='vol_id',
                                 suggested_path='sug_path')
        self.sd.dbus.fake_folder_response = defer.succeed(folder_data)
        self.sd.on_folder_op_error_callback = lambda *a: None
        self.sd.dbus.get_folders = lambda: defer.succeed([])
        self.sd.folders = 'stuff'

        # execute and test
        yield self.sd.delete_folder('vol_id')
        self.assertTrue(self.hdlr.check_info("Delete folder ok", "path='path'",
                                             "volume=vol_id"))
        self.assertEqual(self.sd.folders, [])

    @defer.inlineCallbacks
    def test_delete_folder_failure(self):
        """Deleting a folder finishes bad."""
        called = []
        exc = FolderOperationError(error="uglyerror", path="path")
        self.sd.dbus.fake_folder_response = defer.fail(exc)
        self.sd.on_folder_op_error_callback = lambda e: called.append(e)

        # execute and test
        yield self.sd.delete_folder('vol_id')
        self.assertEqual(called, [exc])
        self.assertTrue(self.hdlr.check_info("Delete folder", "uglyerror",
                                             "finished with error", "vol_id"))

    @defer.inlineCallbacks
    def test_subscribe_folder_ok(self):
        """Subscribing a folder finishes ok."""
        folder_data = FolderData(path='path', subscribed=True,
                                 node='node_id', volume='vol_id',
                                 suggested_path='sug_path')
        self.sd.dbus.fake_folder_response = defer.succeed(folder_data)
        self.sd.on_folder_op_error_callback = lambda *a: None
        self.sd.dbus.get_folders = lambda: defer.succeed([folder_data])
        self.sd.folders = 'stuff'

        # execute and test
        yield self.sd.subscribe_folder('vol_id')
        self.assertTrue(self.hdlr.check_info("Subscribe folder ok",
                                             "path='path'", "volume=vol_id"))
        self.assertEqual(self.sd.folders, [folder_data])

    @defer.inlineCallbacks
    def test_subscribe_folder_failure(self):
        """Subscribing a folder finishes bad."""
        called = []
        exc = FolderOperationError(error="uglyerror", path="path")
        self.sd.dbus.fake_folder_response = defer.fail(exc)
        self.sd.on_folder_op_error_callback = lambda e: called.append(e)

        # execute and test
        yield self.sd.subscribe_folder('vol_id')
        self.assertEqual(called, [exc])
        self.assertTrue(self.hdlr.check_info("Subscribe folder", "uglyerror",
                                             "finished with error", "vol_id"))

    @defer.inlineCallbacks
    def test_unsubscribe_folder_ok(self):
        """Unsubscribing a folder finishes ok."""
        folder_data = FolderData(path='path', subscribed=True,
                                 node='node_id', volume='vol_id',
                                 suggested_path='sug_path')
        self.sd.dbus.fake_folder_response = defer.succeed(folder_data)
        self.sd.on_folder_op_error_callback = lambda *a: None
        self.sd.dbus.get_folders = lambda: defer.succeed([folder_data])
        self.sd.folders = 'stuff'

        # execute and test
        yield self.sd.unsubscribe_folder('vol_id')
        self.assertTrue(self.hdlr.check_info("Unsubscribe folder ok",
                                             "path='path'", "volume=vol_id"))
        self.assertEqual(self.sd.folders, [folder_data])

    @defer.inlineCallbacks
    def test_unsubscribe_folder_failure(self):
        """Unsubscribing a folder finishes bad."""
        called = []
        exc = FolderOperationError(error="uglyerror", path="path")
        self.sd.dbus.fake_folder_response = defer.fail(exc)
        self.sd.on_folder_op_error_callback = lambda e: called.append(e)

        # execute and test
        yield self.sd.unsubscribe_folder('vol_id')
        self.assertEqual(called, [exc])
        self.assertTrue(self.hdlr.check_info("Unsubscribe folder", "uglyerror",
                                             "finished with error", "vol_id"))


class SharesTestCase(BaseTestCase):
    """Shares checking."""

    def test_shares_changed_callback(self):
        """Get the new data after the shares changed."""
        # set the callback
        called = []
        self.sd.dbus.get_shares_to_me = lambda: called.append(True)
        self.sd.dbus.get_shares_to_others = lambda: called.append(True)

        # they changed!
        self.sd.on_sd_shares_changed()

        # test
        self.assertEqual(len(called), 2)

    @defer.inlineCallbacks
    def test_initial_value(self):
        """Fill the folder info initially."""
        called = []
        self.sd.dbus.get_shares_to_me = lambda: called.append(True)
        self.sd.dbus.get_shares_to_others = lambda: called.append(True)
        yield self.sd._get_initial_data()
        self.assertEqual(len(called), 2)

    def test_shares_to_me_changed_callback(self):
        """Test that the GUI callback is called."""
        # set the callback
        cal = []
        self.sd.on_shares_to_me_changed_callback = lambda *a: cal.append(1)
        self.sd.on_shares_to_others_changed_callback = lambda *a: cal.append(2)

        # they changed!
        self.sd.shares_to_me = 'foo'
        self.sd.shares_to_others = 'fakedata'  # what fake dbus will return
        self.sd.on_sd_shares_changed()

        # test
        self.assertEqual(cal, [1])

    def test_shares_to_others_changed_callback(self):
        """Test that the GUI callback is called."""
        # set the callback
        cal = []
        self.sd.on_shares_to_me_changed_callback = lambda *a: cal.append(1)
        self.sd.on_shares_to_others_changed_callback = lambda *a: cal.append(2)

        # they changed!
        self.sd.shares_to_others = 'foo'
        self.sd.shares_to_me = 'fakedata'  # what fake dbus will return
        self.sd.on_sd_shares_changed()

        # test
        self.assertEqual(cal, [2])


class PublicFilesTestCase(BaseTestCase):
    """PublicFiles checking."""

    @defer.inlineCallbacks
    def test_initial_value(self):
        """Fill the public_files info initially."""
        called = []
        self.sd.dbus.get_public_files = lambda: called.append(True)
        yield self.sd._get_initial_data()
        self.assertTrue(called)

    @defer.inlineCallbacks
    def test_initial_value_is_stored(self):
        """Fill the public_files info initially."""
        data = object()
        self.sd.dbus.get_public_files = lambda: defer.succeed(data)
        yield self.sd._get_initial_data()
        self.assertEqual(self.sd.public_files, data)

    @defer.inlineCallbacks
    def test_on_sd_public_files_changed(self):
        """Test the on_sd_public_files_changed method."""
        self.sd.public_files = None
        pf1 = PublicFilesData(volume='volume1', node='node1',
                              path='path1', public_url='url1')
        pf2 = PublicFilesData(volume='volume2', node='node2',
                              path='path2', public_url='url2')
        self.sd.dbus.get_public_files = lambda: defer.succeed([pf1, pf2])

        yield self.sd.on_sd_public_files_changed()

        self.assertEqual(len(self.sd.public_files), 2)
        self.assertEqual(self.sd.public_files[0], pf1)
        self.assertEqual(self.sd.public_files[1], pf2)

    @defer.inlineCallbacks
    def test_on_sd_public_files_changed_calls_callback(self):
        """When public files changed, the UI callback is called ."""
        called = []
        pf = object()
        self.sd.dbus.get_public_files = lambda: defer.succeed([pf])
        self.sd.on_public_files_changed_callback = lambda _: called.append(_)

        yield self.sd.on_sd_public_files_changed()

        self.assertEqual(called, [[pf]])

    @defer.inlineCallbacks
    def test_change_public_access_ok(self):
        """Change public access ok."""
        # monkeypatch
        result = dict(public_url='public')
        self.sd.dbus.fake_change_public_access = defer.succeed(result)
        self.sd.on_public_op_error_callback = lambda *a: None

        # execute and test
        yield self.sd.change_public_access('testpath', True)
        self.assertTrue(self.hdlr.check_info("Change public access ok",
                                             "path='testpath'",
                                             "is_public=True", "url='public'"))

    @defer.inlineCallbacks
    def test_change_public_access_error(self):
        """Change public access with problems."""
        # monkeypatch
        called = []
        e = ValueError('test failure')
        self.sd.dbus.fake_change_public_access = defer.fail(e)
        self.sd.on_public_op_error_callback = lambda *a: called.extend(a)

        # execute and test
        yield self.sd.change_public_access('testpath', True)
        self.assertEqual(called, [e])
        self.hdlr.debug = True
        self.assertTrue(self.hdlr.check_info("Change public access",
                                             "testpath", "finished with error",
                                             "ValueError", "test failure"))


class HandlingSharesTestCase(BaseTestCase):
    """Handling shares checking."""

    def test_on_share_op_error_callback_set(self):
        """It's mandatory to set the callback for this response."""
        self.sd.on_share_op_error_callback()
        self.assertTrue(self.hdlr.check_warning('on_share_op_error_callback'))

    def test_accept_share_ok(self):
        """Accepting a share finishes ok."""
        # monkeypatch
        self.sd.dbus.fake_share_response = defer.succeed(None)
        self.sd.on_share_op_error_callback = lambda *a: None

        # execute and test
        self.sd.accept_share('share_id')
        self.assertTrue(self.hdlr.check_info("Accepting share", "share_id",
                                             "started"))
        self.assertTrue(self.hdlr.check_info("Accepting share", "share_id",
                                             "finished successfully"))

    def test_accept_share_failure(self):
        """Accepting a share finishes bad."""
        # monkeypatch
        called = []
        e = ShareOperationError(share_id='foo', error='bar')
        self.sd.dbus.fake_share_response = defer.fail(e)
        self.sd.on_share_op_error_callback = \
            lambda sid, e: called.append((sid, e))

        # execute and test
        self.sd.accept_share('share_id')
        self.assertEqual(called, [('share_id', 'bar')])
        self.assertTrue(self.hdlr.check_info("Accepting share", "share_id",
                                             "started"))
        self.assertTrue(self.hdlr.check_info("Accepting share", "share_id",
                                             "finished with error", "bar"))

    def test_accept_share_error(self):
        """Really bad error when accepting a share."""
        # monkeypatch
        e = ValueError('unexpected failure')
        self.sd.dbus.fake_share_response = defer.fail(e)
        self.sd.on_share_op_error_callback = lambda *a: None

        # execute and test
        self.sd.accept_share('share_id')
        self.assertTrue(self.hdlr.check_info("Accepting share", "share_id",
                                             "started"))
        self.assertTrue(self.hdlr.check_error(
                        "Unexpected error when accepting share", "share_id",
                        "ValueError", "unexpected failure"))

    def test_reject_share_ok(self):
        """Rejecting a share finishes ok."""
        # monkeypatch
        self.sd.dbus.fake_share_response = defer.succeed(None)
        self.sd.on_share_op_error_callback = lambda *a: None

        # execute and test
        self.sd.reject_share('share_id')
        self.assertTrue(self.hdlr.check_info("Rejecting share", "share_id",
                                             "started"))
        self.assertTrue(self.hdlr.check_info("Rejecting share", "share_id",
                                             "finished successfully"))

    def test_reject_share_failure(self):
        """Rejecting a share finishes bad."""
        # monkeypatch
        called = []
        e = ShareOperationError(share_id='foo', error='bar')
        self.sd.dbus.fake_share_response = defer.fail(e)
        self.sd.on_share_op_error_callback = \
            lambda sid, e: called.append((sid, e))

        # execute and test
        self.sd.reject_share('share_id')
        self.assertEqual(called, [('share_id', 'bar')])
        self.assertTrue(self.hdlr.check_info("Rejecting share", "share_id",
                                             "started"))
        self.assertTrue(self.hdlr.check_info("Rejecting share", "share_id",
                                             "finished with error", "bar"))

    def test_reject_share_error(self):
        """Really bad error when rejecting a share."""
        # monkeypatch
        e = ValueError('unexpected failure')
        self.sd.dbus.fake_share_response = defer.fail(e)
        self.sd.on_share_op_error_callback = lambda *a: None

        # execute and test
        self.sd.reject_share('share_id')
        self.assertTrue(self.hdlr.check_info("Rejecting share", "share_id",
                                             "started"))
        self.assertTrue(self.hdlr.check_error(
                        "Unexpected error when rejecting share", "share_id",
                        "ValueError", "unexpected failure"))

    def test_send_share_invitation_ok(self):
        """Sending a share invitation finishes ok."""
        # monkeypatch
        self.sd.dbus.fake_share_response = defer.succeed(None)

        # execute and test
        self.sd.send_share_invitation('path', 'mail_address',
                                      'sh_name', 'access_level')
        self.assertTrue(self.hdlr.check_info("Sending share invitation",
                                             "path", "mail_address",
                                             "sh_name", "access_level"))
        self.assertTrue(self.hdlr.check_info("Sending share invitation",
                                             "path", "mail_address",
                                             "sh_name", "access_level",
                                             "finished successfully"))

    def test_send_share_invitation_failure(self):
        """Sending a share invitation finished with failure."""
        # monkeypatch
        e = ShareOperationError(error='bar')
        self.sd.dbus.fake_share_response = defer.fail(e)

        # execute and test
        self.sd.send_share_invitation('path', 'mail_address',
                                      'sh_name', 'access_level')
        self.assertTrue(self.hdlr.check_info("Sending share invitation",
                                             "path", "mail_address",
                                             "sh_name", "access_level"))
        self.assertTrue(self.hdlr.check_info("Sending share invitation",
                                             "path", "mail_address",
                                             "sh_name", "access_level",
                                             "finished with error", "bar"))

    def test_send_share_invitation_error(self):
        """Sending a share invitation went really bad."""
        # monkeypatch
        e = ValueError('unexpected failure')
        self.sd.dbus.fake_share_response = defer.fail(e)

        # execute and test
        self.sd.send_share_invitation('path', 'mail_address',
                                      'sh_name', 'access_level')
        self.assertTrue(self.hdlr.check_info("Sending share invitation",
                                             "path", "mail_address",
                                             "sh_name", "access_level"))
        self.assertTrue(self.hdlr.check_error(
                        "Unexpected error when sending share invitation",
                        "path", "mail_address", "sh_name", "access_level",
                        "ValueError", "unexpected failure"))

    @defer.inlineCallbacks
    def test_subscribe_share_ok(self):
        """Subscribing a share finishes ok."""
        self.sd.dbus.fake_share_response = defer.succeed(None)
        self.sd.on_share_op_error_callback = lambda *a: None

        # execute and test
        yield self.sd.subscribe_share('share_id')
        self.assertTrue(self.hdlr.check_info(
                        "Subscribing share share_id finished successfully"))

    @defer.inlineCallbacks
    def test_subscribe_share_failure(self):
        """Subscribing a share finishes bad."""
        called = []
        exc = ShareOperationError(error="uglyerror", share_id="share_id")
        self.sd.dbus.fake_share_response = defer.fail(exc)
        self.sd.on_share_op_error_callback = lambda *a: called.append(a)

        # execute and test
        yield self.sd.subscribe_share('share_id')
        self.assertEqual(called, [("share_id", "uglyerror")])
        self.assertTrue(self.hdlr.check_info("Subscribing share", "share_id",
                                             "finished with error",
                                             "uglyerror"))

    @defer.inlineCallbacks
    def test_unsubscribe_share_ok(self):
        """Unsubscribing a share finishes ok."""
        self.sd.dbus.fake_share_response = defer.succeed(None)
        self.sd.on_share_op_error_callback = lambda *a: None

        # execute and test
        yield self.sd.unsubscribe_share('share_id')
        self.assertTrue(self.hdlr.check_info(
                        "Unsubscribing share share_id finished successfully"))

    @defer.inlineCallbacks
    def test_unsubscribe_share_failure(self):
        """Unsubscribing a share finishes bad."""
        called = []
        exc = ShareOperationError(error="uglyerror", share_id="share_id")
        self.sd.dbus.fake_share_response = defer.fail(exc)
        self.sd.on_share_op_error_callback = lambda *a: called.append(a)

        # execute and test
        yield self.sd.unsubscribe_share('share_id')
        self.assertEqual(called, [("share_id", "uglyerror")])
        self.assertTrue(self.hdlr.check_info("Unsubscribing share", "share_id",
                                             "finished with error",
                                             "uglyerror"))


class TransferTestCase(BaseTestCase):
    """Tests for all transfer behaviour."""

    def test_callback(self):
        """It's ok if the callback is not set."""
        self.sd.on_transfers_callback()

    def test_poller_instantiaton(self):
        """Get a poller at init time with correct config."""
        self.assertEqual(self.sd.transfers_poller.interval,
                         TRANSFER_POLL_INTERVAL)
        self.assertEqual(self.sd.transfers_poller.callback,
                         self.sd.get_current_transfers)

    @defer.inlineCallbacks
    def test_get_current_transfers(self):
        """Get current transfers from SD."""
        called = []
        self.sd.on_transfers_callback = lambda *a: called.extend(a)
        self.sd.dbus.get_current_uploads = lambda: defer.succeed(list("up"))
        self.sd.dbus.get_current_downloads = lambda: defer.succeed(list("dn"))
        yield self.sd.get_current_transfers()
        self.assertEqual(called[0], ["u", "p", "d", "n"])

    @defer.inlineCallbacks
    def test_initial_data_set_poller(self):
        """Set the poller to run with transferring value."""
        self.sd.queue_content = qc = FakeQueueContent()
        qc.transferring = 'foo'
        called = []
        self.sd.transfers_poller.run = lambda v: called.append(v)
        yield self.sd._get_initial_data()
        self.assertEqual(called, ['foo'])

    @defer.inlineCallbacks
    def test_run_poller_on_queue_added(self):
        """After adding something to the queue, set the poller to run."""
        self.sd.queue_content = qc = FakeQueueContent()
        qc.transferring = 'foo'
        called = []
        self.sd.transfers_poller.run = lambda v: called.append(v)
        yield self.sd.on_sd_queue_added('name', 'id', {})
        self.assertEqual(called, ['foo'])

    @defer.inlineCallbacks
    def test_run_poller_on_queue_removed(self):
        """After removing something to the queue, set the poller to run."""
        self.sd.queue_content = qc = FakeQueueContent()
        qc.transferring = 'foo'
        called = []
        self.sd.transfers_poller.run = lambda v: called.append(v)
        yield self.sd.on_sd_queue_added('name', 'id', {})
        self.assertEqual(called, ['foo'])


class PollerTestCase(TwistedTestCase):
    """Tests for the Poller behaviour."""

    def setUp(self):
        """Set up."""
        self.poller = Poller(5, lambda: defer.succeed(True))
        self.addCleanup(self.poller.run, False)

    def test_execute_callback(self):
        """Execute the callback surrounded with _inside_call flag."""
        d = defer.Deferred()
        self.poller.callback = lambda: d
        self.assertFalse(self.poller._inside_call)
        self.poller._execute()
        self.assertTrue(self.poller._inside_call)
        d.callback(True)
        self.assertFalse(self.poller._inside_call)

    @defer.inlineCallbacks
    def test_execute_call_later_yes(self):
        """Call later after execution if should."""
        self.poller._should_run = True
        yield self.poller._execute()
        self.assertTrue(self.poller._call.active())

    @defer.inlineCallbacks
    def test_execute_call_later_no(self):
        """Don't call later after execution if should not."""
        assert not self.poller._should_run
        yield self.poller._execute()
        self.assertEqual(self.poller._call, None)

    def test_run_yes_set_should_run(self):
        """Set should_run on run."""
        self.poller.run(True)
        self.assertTrue(self.poller._should_run)

    def test_run_yes_have_active_call(self):
        """Don't generate other call if have one active."""
        call = self.poller._call = reactor.callLater(100, lambda: None)
        time_done = call.getTime()
        assert not self.poller._inside_call
        self.poller.run(True)
        self.assertTrue(call is self.poller._call)
        self.assertEqual(time_done, self.poller._call.getTime())

    def test_run_yes_inside_call(self):
        """Don't generate other call if inside one."""
        self.poller._call = None
        self.poller._inside_call = True
        self.poller.run(True)
        self.assertEqual(self.poller._call, None)

    def test_run_yes_no_call(self):
        """Generate other call if doesn't have one."""
        self.poller._call = None
        assert not self.poller._inside_call
        self.poller.run(True)
        self.assertTrue(self.poller._call.active())

    def test_run_yes_call_inactive(self):
        """Generate other call if current is inactive."""
        d = defer.Deferred()

        def check():
            """Check after the call later."""
            assert not self.poller._call.active()
            assert not self.poller._inside_call
            self.poller.run(True)
            self.assertTrue(self.poller._call.active())
            d.callback(True)

        self.poller._call = reactor.callLater(0, check)
        return d

    def test_run_no_set_should_run(self):
        """Set should_run on run."""
        self.poller.run(False)
        self.assertFalse(self.poller._should_run)

    def test_run_no_have_active_call(self):
        """Cancel the call if it's active."""
        self.poller._call = reactor.callLater(100, lambda: None)
        self.poller.run(False)
        self.assertFalse(self.poller._call.active())

    def test_run_no_no_call(self):
        """Don't cancel the call if doesn't have one."""
        self.poller._call = None
        self.poller.run(False)
        self.assertEqual(self.poller._call, None)

    def test_run_no_call_inactive(self):
        """Don't cancel the call if it's not active."""
        d = defer.Deferred()

        def check():
            """Check after the call later."""
            assert not self.poller._call.active()
            self.poller.run(False)
            self.assertFalse(self.poller._call.active())
            d.callback(True)

        self.poller._call = reactor.callLater(0, check)
        return d


class SimpleCallsTestCase(BaseTestCase):
    """Some simple calls."""

    @defer.inlineCallbacks
    def test_get_free_space(self):
        """Get the free space."""
        free_space = "12345"
        vol_id = "volume_id"
        called = []
        f = lambda vol: called.append(vol) or defer.succeed(free_space)
        self.sd.dbus.get_free_space = f

        result = yield self.sd.get_free_space(vol_id)
        self.assertEqual(result, int(free_space))
        self.assertEqual(called, [vol_id])
