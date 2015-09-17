# -*- coding: utf-8 -*-

# Author: Natalia Bidart <nataliabidart@gmail.com>
#
# Copyright 2010-2011 Chicharreros
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

"""Generic helpers for the UI code."""

import os

# pylint: disable=E0611
from gi.repository import GdkPixbuf, Gtk
# pylint: enable=E0611

from magicicada.magicicadaconfig import get_data_file


def get_builder(builder_file_name):
    """Return a fully-instantiated Gtk.Builder instance from specified ui file.

    :param builder_file_name: The name of the builder file, without extension.
        Assumed to be in the 'ui' directory under the data path.
    """
    # Look for the ui file that describes the user interface.
    ui_filename = get_data_file('ui', builder_file_name)
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = Gtk.Builder()
    builder.set_translation_domain('magicicada')
    builder.add_from_file(ui_filename)
    return builder


def build_icon_dict(image_size):
    """Return a dict with icons for 'image_size'."""
    result = {}

    for style in ('idle', 'working', 'alert'):
        fname = get_data_file('media', 'icon-%s-%s.png' % (style, image_size))
        result[style] = GdkPixbuf.Pixbuf.new_from_file(fname)

    return result


class Buildable(object):
    """A buildable object from an .ui file."""

    filename = None

    def __init__(self, builder=None):
        super(Buildable, self).__init__()
        if builder is None:
            assert self.filename is not None
            self.builder = get_builder(self.filename)
        else:
            self.builder = builder
        self.builder.connect_signals(self)

        for obj in self.builder.get_objects():
            name = getattr(obj, 'name', None)
            if name is None and isinstance(obj, Gtk.Buildable):
                # work around bug lp:507739
                name = Gtk.Buildable.get_name(obj)
            if name is not None:
                setattr(self, name, obj)
