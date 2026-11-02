"""
Tests for the RAG application.
"""

from django.test import SimpleTestCase


class RagAppTestCase(SimpleTestCase):
    """
    Test suite for RAG application configuration.
    """

    def test_rag_app_configuration(self):
        """
        Verify that RAG application loads cleanly.
        """
        from rag.apps import RagConfig
        self.assertEqual(RagConfig.name, 'rag')
