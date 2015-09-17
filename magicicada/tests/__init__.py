# __init__.py
#
# Author: Natalia Bidart <nataliabidart@gmail.com>
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

"""Magicicada Test Suite."""

import os

from collections import defaultdict
from functools import wraps

from magicicada.logger import set_up as logging_set_up


# logging should not go to system's log
logging_set_up(cache_dir=os.path.join(os.path.curdir, '_logs_temp'))


class Recorder(object):
    """A class that records every call clients made to it."""

    no_wrap = ['_called']

    def __init__(self, *args, **kwargs):
        self._called = defaultdict(list)

    def __getattribute__(self, attr_name):
        """Override so we can record calls to members."""
        try:
            result = super(Recorder, self).__getattribute__(attr_name)
        except AttributeError:
            result = lambda *a, **kw: None
            super(Recorder, self).__setattr__(attr_name, result)

        if attr_name in super(Recorder, self).__getattribute__('no_wrap'):
            return result

        called = super(Recorder, self).__getattribute__('_called')

        def wrap_me(f):
            """Wrap 'f'."""
            @wraps(f)
            def inner(*a, **kw):
                """Kepp track of calls to 'f', execute it and return result."""
                called[attr_name].append((a, kw))
                return f(*a, **kw)

            return inner

        if callable(result):
            return wrap_me(result)
        else:
            return result
