"""
Tests for the Machines application.
"""

from django.test import SimpleTestCase


class MachinesAppTestCase(SimpleTestCase):
    """
    Test suite for Machines application configuration.
    """

    def test_machines_app_configuration(self):
        """
        Verify that Machines application loads cleanly.
        """
        from machines.apps import MachinesConfig
        self.assertEqual(MachinesConfig.name, 'machines')
