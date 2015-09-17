"""The test suite that performs code style checks."""

import os
import pep8
from collections import defaultdict
from cStringIO import StringIO
from unittest import TestCase

from mock import patch
from pyflakes.scripts.pyflakes import checkPath

import magicicada


class PackagePep8TestCase(TestCase):
    """PEP8 checker."""

    maxDiff = None
    packages = []
    exclude = []

    def setUp(self):
        self.errors = {}
        self.pep8style = pep8.StyleGuide(
            counters=defaultdict(int),
            doctest='',
            exclude=self.exclude,
            filename=['*.py'],
            ignore=[],
            messages=self.errors,
            repeat=True,
            select=[],
            show_pep8=False,
            show_source=False,
            max_line_length=79,
            quiet=0,
            statistics=False,
            testsuite='',
            verbose=0,
        )

    def message(self, text):
        """Gather messages."""
        self.errors.append(text)

    def test_all_code(self):
        """Check all the code."""
        for package in self.packages:
            self.pep8style.input_dir(os.path.dirname(package.__file__))
        self.assertEqual(self.pep8style.options.report.total_errors, 0)


class MagicicadaPep8TestCase(PackagePep8TestCase):
    """PEP8 checker for Magicicada."""
    packages = [magicicada]


class PyFlakesTestCase(TestCase):
    """PyFlakes checker."""

    def test_pyflakes(self):
        """Check all the code."""
        stdout = StringIO()
        with patch('sys.stdout', stdout):
            for dirpath, _, filenames in os.walk('src'):
                for filename in filenames:
                    if filename.endswith('.py'):
                        checkPath(os.path.join(dirpath, filename))

        errors = [line.strip() for line in stdout.getvalue().splitlines()
                  if line.strip()]
        if errors:
            self.fail('\n'.join(errors))
