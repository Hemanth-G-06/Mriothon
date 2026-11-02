"""
Tests for the Documents application.
"""

from django.test import SimpleTestCase


class DocumentsAppTestCase(SimpleTestCase):
    """
    Test suite for Documents application configuration.
    """

    def test_documents_app_configuration(self):
        """
        Verify that Documents application loads cleanly.
        """
        from documents.apps import DocumentsConfig
        self.assertEqual(DocumentsConfig.name, 'documents')
