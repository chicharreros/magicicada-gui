# -*- coding: utf-8 -*-
#
# Author: Natalia Bidart <nataliabidart@gmail.com>
#
# Copyright 2011 Chicharreros
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

"""Magicicada GTK UI Test Suite."""

import logging

# pylint: disable=E0611
from gi.repository import Gtk
# pylint: enable=E0611

from twisted.internet import defer
from twisted.trial.unittest import TestCase
from ubuntuone.devtools.handlers import MementoHandler

from magicicada import syncdaemon
from magicicada.dbusiface import (
    FolderData,
    PublicFilesData,
    ShareData,
)
from magicicada.helpers import NO_OP
from magicicada.tests import Recorder


# It's ok to access private data in the test suite
# pylint: disable=W0212

# Instance of 'A' has no 'y' member
# pylint: disable=E1101

# Instance of 'A' has no 'y' member (but some types could not be inferred)
# pylint: disable=E1103

SAMPLE_FOLDERS = (
    FolderData(node=u'a721d8a0',
               path=u'/home/user/udf0',
               suggested_path=u'~/udf0',
               subscribed=True,
               volume=u'f5cc6b0d'),
    FolderData(node=u'db3db7cc551d',
               path=u'/home/user/foo/bar',
               suggested_path=u'~/foo/bar',
               subscribed=False,
               volume=u'd993b721d8af'),
)

SAMPLE_SHARES_TO_ME = (
    ShareData(accepted=True,
              access_level=u'Modify',
              free_bytes=12345678,
              name=u'Yadda',
              node_id=u'5cce03b0c511',
              other_username=u'ugly-username',
              other_visible_name=u'My Best Friend',
              path=u'/home/user/Ubuntu One/Shared With Me/Yadda',
              volume_id=u'',
              subscribed=False),
    ShareData(accepted=True,
              access_level=u'View',
              free_bytes=89793450,
              name=u'Books ❥',
              node_id=u'5caadrf0c511',
              other_username=u'loginid',
              other_visible_name=u'José Cuervo',
              path=u'/home/user/Ubuntu One/Shared With Me/Books',
              volume_id=u'',
              subscribed=True),
)

SAMPLE_SHARES_TO_OTHERS = (
    ShareData(accepted=True,
              access_level=u'View',
              free_bytes=None,
              name=u'Fotografías',
              node_id=u'bd42c41538cb',
              other_username=u'foobar',
              other_visible_name=u'The Bar Foo',
              path=u'/home/user/udf0/test',
              volume_id=u'f5cc6b0d',
              subscribed=None),
)

SAMPLE_PUBLIC_FILES = (
    PublicFilesData(volume=u'',
                    node=u'4d0ffa01',
                    path=u'/home/user/Ubuntu One/test.png',
                    public_url=u'http://ubuntuone.com/p/CUG/'),
    PublicFilesData(volume=u'',
                    node=u'1be1ea29',
                    path=u'/home/user/Ubuntu One/public/text.txt',
                    public_url=u'http://ubuntuone.com/p/6TX/'),
    PublicFilesData(volume=u'f5cc6b0d',
                    node=u'8dba0484',
                    path=u'/home/user/udf0/yadda.py',
                    public_url=u'http://ubuntuone.com/p/U4R/'),
)


class FakedQueueContent(object):
    """A faked QueueContent."""

    def __init__(self):
        self.node_ops = []

    def __len__(self):
        return len(self.node_ops)

    def clear(self):
        """Cleat the contents."""
        self.node_ops = []


class FakedSyncdaemon(Recorder):
    """A faked syncdaemon."""

    no_wrap = [
        '_called', '_next_id', '_meta_paths',
        'current_state',
        'on_connected_callback',
        'on_disconnected_callback',
        'on_folder_op_error_callback',
        'on_initial_data_ready_callback',
        'on_initial_online_data_ready_callback',
        'on_metadata_ready_callback',
        'on_node_ops_changed_callback',
        'on_offline_callback',
        'on_online_callback',
        'on_started_callback',
        'on_stopped_callback',
        'queue_content',
        'status_changed_callback',
    ]

    def __init__(self):
        super(FakedSyncdaemon, self).__init__()
        self._next_id = 0
        self._meta_paths = []

        self.current_state = syncdaemon.State()
        self.queue_content = FakedQueueContent()

        self.on_started_callback = NO_OP
        self.on_stopped_callback = NO_OP
        self.on_connected_callback = NO_OP
        self.on_disconnected_callback = NO_OP
        self.on_online_callback = NO_OP
        self.on_offline_callback = NO_OP
        self.status_changed_callback = NO_OP
        self.on_node_ops_changed_callback = NO_OP
        self.on_metadata_ready_callback = None  # mandatory
        self.on_initial_data_ready_callback = NO_OP
        self.on_initial_online_data_ready_callback = NO_OP
        self.on_folder_op_error_callback = NO_OP

        self.shutdown = NO_OP

        # Lambda may not be necessary
        # pylint: disable=W0108

        self.start = lambda: setattr(self.current_state, 'is_started', True)
        self.quit = lambda: setattr(self.current_state, 'is_started', False)
        self.connect = lambda: setattr(self.current_state,
                                       'is_connected', True)
        self.disconnect = (lambda:
                           setattr(self.current_state, 'is_connected', False))
        self.get_metadata = self._meta_paths.append

    def accept_share(self, share_id):
        """Fake accept_share."""
        return defer.succeed(share_id)

    def reject_share(self, share_id):
        """Fake reject_share."""
        return defer.succeed(share_id)

    def create_folder(self, path):
        """Fake create_folder."""
        result = self._next_id
        self._next_id += 1
        return defer.succeed(result)

    def delete_folder(self, volume_id):
        """Fake delete_folder."""
        return defer.succeed(volume_id)

    def subscribe_folder(self, volume_id):
        """Fake subscribe_folder."""
        return defer.succeed(volume_id)

    def unsubscribe_folder(self, volume_id):
        """Fake unsubscribe_folder."""
        return defer.succeed(volume_id)


class BaseTestCase(TestCase):
    """UI test cases for Magicicada UI."""

    kwargs = {}
    store = None
    ui_class = None

    @defer.inlineCallbacks
    def setUp(self):
        yield super(BaseTestCase, self).setUp()
        self.sd = FakedSyncdaemon()
        self.patch(syncdaemon, 'SyncDaemon', lambda: self.sd)

        self.ui = None
        if self.ui_class is not None:
            # self.ui_class is not callable, pylint: disable=E1102
            self.ui = self.ui_class(**self.kwargs)
            self.addCleanup(self.ui.destroy)

        self._called = False
        self._set_called = (lambda *args, **kwargs:
                            setattr(self, '_called', (args, kwargs)))

        if getattr(self.ui, 'logger', None) is not None:
            self.memento = MementoHandler()
            self.memento.setLevel(logging.DEBUG)
            self.ui.logger.addHandler(self.memento)
            self.ui.logger.setLevel(logging.DEBUG)
            self.addCleanup(self.ui.logger.removeHandler, self.memento)

        if getattr(self.ui, 'on_destroy', None) is not None:
            self.addCleanup(self.ui.on_destroy)

    def assert_store_correct(self, items, store=None):
        """Test that 'store' has 'items' as content."""
        if store is None:
            store = self.store
            assert store is not None, 'class must provide a store'

        msg = 'amount of rows for %s must be %s (got %s).'
        self.assertEqual(len(store), len(items),
                         msg % (store, len(items), len(store)))

        def unicodeize(elem):
            """Return the unicode repr of 'elem'."""
            if isinstance(elem, str):
                result = elem.decode('utf-8')
            else:
                result = elem
            return result

        def scan_tree(tree_iter, items):
            """Scan a whole tree."""
            msg = "row must be %r (got %r instead)"
            while tree_iter is not None:
                expected, children = items.pop()
                actual = store.get(tree_iter, *range(len(expected)))
                actual = map(unicodeize, actual)
                self.assertEqual(expected, actual,
                                 msg % (expected, actual))
                self.assertEqual(len(children),
                                 store.iter_n_children(tree_iter))

                if children:
                    child_iter = store.iter_children(tree_iter)
                    scan_tree(child_iter, children)

                tree_iter = store.iter_next(tree_iter)

        # assert rows content equal to items content
        root_iter = store.get_iter_first()
        tmp = list(reversed(items))
        scan_tree(root_iter, tmp)

    def debug_store(self):
        """Print the whole content of a store."""
        store_iter = self.store.get_iter_first()
        columns = self.store.get_n_columns()
        print '\nShowing contents of store:', self.store
        while store_iter is not None:
            print self.store.get(store_iter, *range(columns))
            store_iter = self.store.iter_next(store_iter)

    def assert_dialog_properties(self, dialog, title=None, modal=True,
                                 position=Gtk.WindowPosition.CENTER_ON_PARENT):
        """The dialog has correct properties."""
        msg = 'Must %sbe modal.'
        self.assertEqual(modal, dialog.get_modal(),
                         msg % ('' if modal else 'not '))

        actual_position = dialog.get_property('window-position')
        msg = 'dialog must have %s position (got %s instead).'
        self.assertEqual(position, actual_position,
                         msg % (position, actual_position))

        actual = dialog.get_title()
        msg = 'Title must be %r (got %r instead)'
        self.assertEqual(title, actual, msg % (title, actual))

        msg = 'Must not skip taskbar.'
        self.assertFalse(dialog.get_skip_taskbar_hint(), msg)

    def assert_function_logs(self, level, func, *args, **kwargs):
        """Check 'funcion' logs its inputs as 'level'."""
        name = func.__name__
        msg = '%s must be logged with level %r'
        try:
            func(*args, **kwargs)
        except Exception:  # pylint: disable=W0703
            self.assertTrue(self.memento.check_error(name),
                            'function (%s) must be logged as ERROR' % name)

        memento_func = getattr(self.memento, 'check_%s' % level.lower())
        self.assertTrue(memento_func(name), msg % (name, level))
        for arg in args:
            self.assertTrue(memento_func(str(arg)), msg % (arg, level))
        for key, val in kwargs.iteritems():
            arg = "'%s': %r" % (key, val)
            self.assertTrue(memento_func(arg), msg % (arg, level))

    def assert_method_called(self, obj, method, *args, **kwargs):
        """Check that obj.method(*args, **kwargs) was called."""
        self.assertEqual(getattr(obj, '_called')[method], [(args, kwargs)],
                         'Method %r was not called with the args %r and '
                         'kwargs %r' % (method, args, kwargs))

    def assert_methods_called(self, obj, methods):
        """Check that every method in 'methods' was called on 'obj'."""
        expected = dict((k, [((), {})]) for k in methods)
        self.assertEqual(getattr(obj, '_called'), expected)

    def assert_no_method_called(self, obj):
        """Check that obj.method was NOT called."""
        self.assertEqual(getattr(obj, '_called'), {})
