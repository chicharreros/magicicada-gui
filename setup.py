#!/usr/bin/env python

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

"""Build tar.gz and related for magicicada."""

import os
import sys

try:
    import DistUtilsExtra.auto
except ImportError:
    url = 'https://launchpad.net/python-distutils-extra'
    print >> sys.stderr, 'To build magicicada you need', url
    sys.exit(1)

msg = 'needs DistUtilsExtra.auto >= 2.18'
assert DistUtilsExtra.auto.__version__ >= '2.18', msg


def update_data_path(prefix, oldvalue=None):
    """Update data path."""

    try:
        fin = file('magicicada/magicicadaconfig.py', 'r')
        fout = file(fin.name + '.new', 'w')

        for line in fin:
            fields = line.split(' = ')  # Separate variable from value
            if fields[0] == '__magicicada_data_directory__':
                # update to prefix, store oldvalue
                if not oldvalue:
                    oldvalue = fields[1]
                    line = "%s = '%s'\n" % (fields[0], prefix)
                else:  # restore oldvalue
                    line = "%s = %s" % (fields[0], oldvalue)
            fout.write(line)

        fout.flush()
        fout.close()
        fin.close()
        os.rename(fout.name, fin.name)
    except (OSError, IOError):
        print ("ERROR: Can't find magicicada/magicicadaconfig.py")
        sys.exit(1)
    return oldvalue


def update_desktop_file(datadir):
    """Update desktop file."""

    try:
        fin = file('magicicada.desktop.in', 'r')
        fout = file(fin.name + '.new', 'w')

        for line in fin:
            if 'Icon=' in line:
                line = "Icon=%s\n" % (datadir + 'media/icon.png')
            fout.write(line)
        fout.flush()
        fout.close()
        fin.close()
        os.rename(fout.name, fin.name)
    except (OSError, IOError):
        print ("ERROR: Can't find magicicada.desktop.in")
        sys.exit(1)


class InstallAndUpdateDataDirectory(DistUtilsExtra.auto.install_auto):
    """Install and update data dir."""

    def run(self):
        """Run."""
        previous_value = update_data_path(self.prefix + '/share/magicicada/')
        update_desktop_file(self.prefix + '/share/magicicada/')
        DistUtilsExtra.auto.install_auto.run(self)
        update_data_path(self.prefix, previous_value)


DistUtilsExtra.auto.setup(
    name='magicicada',
    version='0.5',
    license='GPL-3',
    author='Natalia Bidart',
    author_email='nataliabidart@gmail.com',
    description='GTK+ frontend for Ubuntu One File Sync service.',
    long_description=('This application provides a GTK frontend to manage '
                      'the file synchronisation service from Ubuntu One.'),
    url='http://launchpad.net/magicicada',
    packages=['magicicada', 'magicicada.tests', 'magicicada.gui',
              'magicicada.gui.gtk', 'magicicada.gui.gtk.tests'],
    data_files=[('share/apport/package-hooks/', ['source_magicicada.py'])],
    cmdclass={'install': InstallAndUpdateDataDirectory},
)
