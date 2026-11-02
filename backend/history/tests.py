"""
Tests for the History application.
"""

from django.test import SimpleTestCase


class HistoryAppTestCase(SimpleTestCase):
    """
    Test suite for History application configuration.
    """

    def test_history_app_configuration(self):
        """
        Verify that History application loads cleanly.
        """
        from history.apps import HistoryConfig
        self.assertEqual(HistoryConfig.name, 'history')
