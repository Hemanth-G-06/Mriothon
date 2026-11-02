"""
Tests for the Documents application.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from documents.models import Document
from machines.models import Machine


class DocumentAPITestCase(TestCase):
    """
    Test suite for Document listing, filtering, upload, and PDF viewing.
    """

    def setUp(self):
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            email='admin@plantops.com',
            password='AdminPassword@123',
            role=UserRole.ADMIN
        )

        self.engineer_user = User.objects.create_user(
            email='engineer@plantops.com',
            password='EngineerPassword@123',
            role=UserRole.ENGINEER
        )

        self.machine1 = Machine.objects.create(
            name='HP-200 CNC',
            model_number='HP-200',
            serial_number='SN-001'
        )

        self.machine2 = Machine.objects.create(
            name='AC-90 Compressor',
            model_number='AC-90',
            serial_number='SN-002'
        )

        self.doc1 = Document.objects.create(
            machine=self.machine1,
            title='HP-200 Operations Manual',
            manual_type='Operations Manual',
            model_number='HP-200',
            revision='Rev 1.0',
            file_name='hp200_ops.pdf',
            file_size=1024000,
            status='Indexed'
        )

        self.doc2 = Document.objects.create(
            machine=self.machine2,
            title='AC-90 Maintenance Guide',
            manual_type='Maintenance Manual',
            model_number='AC-90',
            revision='Rev 2.0',
            file_name='ac90_maint.pdf',
            file_size=2048000,
            status='Indexed'
        )

    def test_authenticated_user_can_list_documents(self):
        self.client.force_authenticate(user=self.engineer_user)
        response = self.client.get('/api/documents/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filter_documents_by_machine(self):
        self.client.force_authenticate(user=self.engineer_user)
        response = self.client.get(f'/api/documents/?machine_id={self.machine1.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'HP-200 Operations Manual')

    def test_admin_can_upload_document(self):
        self.client.force_authenticate(user=self.admin_user)
        pdf_file = SimpleUploadedFile(
            'schematic.pdf',
            b'%PDF-1.4 test binary content',
            content_type='application/pdf'
        )
        payload = {
            'machine_id': self.machine1.id,
            'title': 'HP-200 Schematics',
            'manual_type': 'Electrical Schematics',
            'model_number': 'HP-200',
            'revision': 'Rev 3.0',
            'file': pdf_file
        }
        response = self.client.post('/api/documents/', payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Document.objects.count(), 3)
        self.assertEqual(response.data['status'], 'Indexed')

    def test_engineer_cannot_upload_document(self):
        self.client.force_authenticate(user=self.engineer_user)
        payload = {
            'machine_id': self.machine1.id,
            'title': 'Unauthorized Manual'
        }
        response = self.client.post('/api/documents/', payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_view_document_pdf_stream(self):
        self.client.force_authenticate(user=self.engineer_user)
        response = self.client.get(f'/api/documents/{self.doc1.id}/pdf/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
