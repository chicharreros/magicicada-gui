# -*- coding: utf-8 -*-
#
# Copyright 2010-2016 Chicharreros
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

"""Helpers for an Ubuntu application."""

from __future__ import division

import logging

from functools import wraps


def NO_OP(*a, **kw):
    """Don't do anything."""


def log(logger, level=logging.DEBUG):
    """Log input/ouput info for 'f' using 'logger'."""

    def decorator(f):
        """The decorator per se."""

        @wraps(f)
        def inner(*args, **kwargs):
            """Wrap 'f', log input args and result using 'logger'."""
            name = f.__name__
            result = None
            logger.log(level, "Calling '%s' with args '%s' and kwargs '%s'.",
                       name, args, kwargs)
            try:
                result = f(*args, **kwargs)
            except Exception:  # pylint: disable=W0703
                logger.error('Exception when calling %r with %s %s:',
                             name, args, kwargs)
                raise
            logger.log(level, "Returning from '%s' with result '%s'.",
                       name, result)
            return result

        return inner

    return decorator


# from http://code.activestate.com/recipes/
#                       577081-humanized-representation-of-a-number-of-bytes/


def humanize_bytes(numbytes, precision=1):
    """Return a humanized string representation of a number of bytes.

    Assumes `from __future__ import division`.

    >>> humanize_bytes(1)
    '1 byte'
    >>> humanize_bytes(1024)
    '1.0 kB'
    >>> humanize_bytes(1024*123)
    '123.0 kB'
    >>> humanize_bytes(1024*12342)
    '12.1 MB'
    >>> humanize_bytes(1024*12342,2)
    '12.05 MB'
    >>> humanize_bytes(1024*1234,2)
    '1.21 MB'
    >>> humanize_bytes(1024*1234*1111,2)
    '1.31 GB'
    >>> humanize_bytes(1024*1234*1111,1)
    '1.3 GB'
    """
    abbrevs = (
        (1 << 50, 'PB'),
        (1 << 40, 'TB'),
        (1 << 30, 'GB'),
        (1 << 20, 'MB'),
        (1 << 10, 'kB'),
        (1, 'bytes'))

    if numbytes == 1:
        return '1 byte'
    for factor, suffix in abbrevs:
        if numbytes >= factor:
            break
    # pylint: disable=W0631
    return '%.*f %s' % (precision, numbytes / factor, suffix)
