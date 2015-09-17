#
# Author: Facundo Batista <facundo@taniquetil.com.ar>
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

"""Tests Apport integration."""

from twisted.trial.unittest import TestCase

from magicicada import logger


class ApportTestCase(TestCase):
    """Test the Apport usage."""

    def test_attach_log_file(self):
        """Attach the log file."""
        called = []
        import source_magicicada
        self.patch(source_magicicada, 'attach_file_if_exists',
                   lambda *a: called.extend(a))
        d = {}
        source_magicicada.add_info(d)
        self.assertIs(called[0], d)
        self.assertEqual(called[1], logger.get_filename())
        self.assertEqual(called[2], 'MagicicadaLog')

    def test_attach_package_info_u1client(self):
        """Attach the package information for ubuntuone-client."""
        called = []
        import source_magicicada
        self.patch(source_magicicada, 'attach_related_packages',
                   lambda *a: called.extend(a))
        d = {}
        source_magicicada.add_info(d)
        self.assertIs(called[0], d)
        self.assertEqual(called[1], ['ubuntuone-client'])

ApportTestCase.skip = 'Fails with ImportError: cannot import name _API when ' \
    'running in Precise.'
