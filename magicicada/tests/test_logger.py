# Tests some logging functions
#
# Author: Facundo Batista <facundo@taniquetil.com.ar>
#
# Copyright 2010 Chicharreros
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

"""Tests some logging functions."""

import cStringIO
import logging
import os
import sys
import unittest

from twisted.python import log, failure
from ubuntuone.devtools.handlers import MementoHandler
from xdg.BaseDirectory import xdg_cache_home

from magicicada.logger import exception_handler, deferror_handler, get_filename


# It's ok to access private data in the test suite
# pylint: disable=W0212


class SimpleTestCase(unittest.TestCase):
    """Several simple tests for the logger module."""

    def test_log_fname_default(self):
        """The log filename by default."""
        fname = os.path.join(xdg_cache_home, 'magicicada', 'magicicada.log')
        self.assertEqual(get_filename(), fname)

    def test_log_fname_basedir(self):
        """The log filename using other base dir."""
        fname = os.path.join('tmp', 'magicicada', 'magicicada.log')
        self.assertEqual(get_filename(cache_dir='tmp'), fname)


class ExceptionTestCase(unittest.TestCase):
    """Test that we log on unhandled exceptions."""

    def _get_exception_data(self):
        """Return data from a real exception."""
        try:
            1 / 0
        except ZeroDivisionError:
            return sys.exc_info()

    def test_hook(self):
        """Check that we're hooked in sys."""
        self.assertTrue(sys.excepthook is exception_handler)

    def test_logs(self):
        """Unhandled exceptions logs in error."""
        # set up logger
        handler = MementoHandler()
        handler.setLevel(logging.DEBUG)
        l = logging.getLogger('magicicada')

        # call
        l.addHandler(handler)
        self.addCleanup(l.removeHandler, handler)
        exc = self._get_exception_data()
        try:
            exception_handler(*exc)
        finally:
            l.removeHandler(handler)

        # check
        self.assertTrue(handler.check_error("Unhandled exception",
                                            "ZeroDivisionError"))

    def test_stderr(self):
        """Unhandled exceptions are also sent to stderr."""
        fh = cStringIO.StringIO()

        # call
        orig_stderr = sys.stderr
        sys.stderr = fh
        exc = self._get_exception_data()
        try:
            exception_handler(*exc)
        finally:
            sys.stderr = orig_stderr

        # check
        shown = fh.getvalue()
        self.assertTrue("Traceback" in shown)
        self.assertTrue("ZeroDivisionError" in shown)


class DeferredTestCase(unittest.TestCase):
    """Error logging when it happened inside deferreds."""

    def test_observer_added(self):
        """Test that the observer was added to Twisted logging."""
        self.assertTrue(deferror_handler in log.theLogPublisher.observers)

    def test_noerror(self):
        """No error, no action."""
        handler = MementoHandler()
        handler.setLevel(logging.DEBUG)
        deferror_handler(dict(isError=False, message=''))
        self.assertFalse(handler.check_error("error"))

    def test_message(self):
        """Just a message."""
        handler = MementoHandler()
        handler.setLevel(logging.DEBUG)
        deferror_handler(dict(isError=True, message="foobar"))
        self.assertFalse(handler.check_error("Unhandled error in deferred",
                                             "foobar"))

    def test_failure(self):
        """Received a full failure."""
        handler = MementoHandler()
        handler.setLevel(logging.DEBUG)
        f = failure.Failure(ValueError('foobar'))
        deferror_handler(dict(isError=True, failure=f, message=''))
        self.assertFalse(handler.check_error("Unhandled error in deferred",
                                             "ValueError", "foobar"))
