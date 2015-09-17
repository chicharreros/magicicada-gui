# logger.py
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

"""Logging set up."""


import logging
import os
import sys
import traceback

from logging.handlers import RotatingFileHandler

import twisted.python.log
import xdg.BaseDirectory


class CustomRotatingFH(RotatingFileHandler):
    """Rotating handler that starts a new file for every run."""

    def __init__(self, *args, **kwargs):
        RotatingFileHandler.__init__(self, *args, **kwargs)
        self.doRollover()


def deferror_handler(data):
    """Deferred error handler.

    We receive all stuff here, filter the errors and use correct info. Note
    that we don't send to stderr as Twisted already does that.
    """
    try:
        failure = data['failure']
    except KeyError:
        msg = data['message']
    else:
        msg = failure.getTraceback()
    logger = logging.getLogger('magicicada')
    logger.error("Unhandled error in deferred!\n%s", msg)


def exception_handler(exc_type, exc_value, tb):
    """Handle an unhandled exception."""
    exception = traceback.format_exception(exc_type, exc_value, tb)
    msg = "".join(exception)
    print >> sys.stderr, msg

    # log
    logger = logging.getLogger('magicicada')
    logger.error("Unhandled exception!\n%s", msg)


def get_filename(cache_dir=None):
    """Return the log file name."""
    if cache_dir is None:
        # choose the folder to store the logs
        cache_dir = xdg.BaseDirectory.xdg_cache_home

    return os.path.join(cache_dir, 'magicicada', 'magicicada.log')


def set_up(cache_dir=None):
    """Set up the logging."""
    logfile = get_filename(cache_dir)
    logfolder = os.path.dirname(logfile)
    if not os.path.exists(logfolder):
        os.makedirs(logfolder)

    logger = logging.getLogger('magicicada')
    handler = CustomRotatingFH(logfile, maxBytes=1e6, backupCount=10)
    logger.addHandler(handler)
    assert len(logger.handlers) == 1
    formatter = logging.Formatter("%(asctime)s - %(name)s - "
                                  "%(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.setLevel(logging.DEBUG)

    if os.getenv('MAGICICADA_DEBUG'):
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        logger.addHandler(console)
        assert len(logger.handlers) == 2
        logger.setLevel(logging.DEBUG)

    # hook the exception handler
    sys.excepthook = exception_handler

    # hook the twisted observer
    twisted.python.log.addObserver(deferror_handler)
