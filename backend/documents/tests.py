"""
Comprehensive automated test suite for Document Management and PDF Processing (Task 04).
Covers PDF validation, PyMuPDF extraction, RBAC access control, and secure file downloads.
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
import io
import shutil
import tempfile
import uuid
import pymupdf
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserRole
from documents.models import Document, DocumentPage, DocumentStatus
from documents.services import extract_document_pages
from machines.models import Machine, MachineAssignment, MachineStatus

User = get_user_model()


def generate_test_pdf_bytes(pages_text=None) -> bytes:
    """
    Generates a valid PDF in memory using PyMuPDF.
    """
    if pages_text is None:
        pages_text = ["This is page 1 of the manufacturing manual."]

    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class BaseDocumentTestCase(TestCase):
    """
    Common setup fixture providing temporary media storage and user roles.
    """

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media)
        self.settings_override.enable()

        self.client = APIClient()
        self.password = 'ComplexSecret123!'

        self.admin = User.objects.create_user(
            email='admin@docs.local',
            password=self.password,
            first_name='Admin',
            last_name='User',
            role=UserRole.ADMIN
        )
        self.supervisor = User.objects.create_user(
            email='supervisor@docs.local',
            password=self.password,
            first_name='Supervisor',
            last_name='User',
            role=UserRole.SUPERVISOR
        )
        self.engineer = User.objects.create_user(
            email='engineer@docs.local',
            password=self.password,
            first_name='Engineer',
            last_name='User',
            role=UserRole.ENGINEER
        )

        self.admin_token = str(RefreshToken.for_user(self.admin).access_token)
        self.supervisor_token = str(RefreshToken.for_user(self.supervisor).access_token)
        self.engineer_token = str(RefreshToken.for_user(self.engineer).access_token)

        self.machine1 = Machine.objects.create(
            machine_code='CNC-01',
            name='5-Axis CNC Mill',
            status=MachineStatus.ACTIVE,
            created_by=self.admin
        )
        self.machine2 = Machine.objects.create(
            machine_code='ROBOT-01',
            name='KUKA Welding Robot',
            status=MachineStatus.ACTIVE,
            created_by=self.admin
        )
        self.inactive_machine = Machine.objects.create(
            machine_code='OLD-01',
            name='Decommissioned Press',
            status=MachineStatus.INACTIVE,
            created_by=self.admin
        )

        # Assign engineer to machine1 only
        MachineAssignment.objects.create(
            machine=self.machine1,
            user=self.engineer,
            assigned_by=self.admin,
            is_active=True
        )

        self.docs_url = '/api/documents/'

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)


# ==============================================================================
# 1. Upload and Validation Tests
# ==============================================================================

class DocumentUploadValidationTestCase(BaseDocumentTestCase):
    """
    Tests for PDF file upload validation rules and edge cases.
    """

    def test_admin_can_upload_valid_pdf(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        pdf_bytes = generate_test_pdf_bytes(["Operating Guide - Page 1", "Maintenance - Page 2"])
        uploaded_file = SimpleUploadedFile("manual.pdf", pdf_bytes, content_type="application/pdf")

        response = self.client.post(
            self.docs_url,
            {
                'machine_id': str(self.machine1.id),
                'title': 'CNC Mill Operating Manual',
                'description': 'Official maintenance instructions',
                'file': uploaded_file
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data['title'], 'CNC Mill Operating Manual')
        self.assertEqual(data['original_filename'], 'manual.pdf')
        self.assertEqual(data['page_count'], 2)
        self.assertEqual(data['status'], DocumentStatus.READY)
        self.assertEqual(data['machine_code'], 'CNC-01')

        # Verify pages created
        doc = Document.objects.get(pk=data['id'])
        self.assertEqual(doc.pages.count(), 2)

    def test_missing_file_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(
            self.docs_url,
            {
                'machine_id': str(self.machine1.id),
                'title': 'Missing File Doc'
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.json())

    def test_non_pdf_extension_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        file = SimpleUploadedFile("script.py", b"print('hello')", content_type="text/x-python")
        response = self.client.post(
            self.docs_url,
            {
                'machine_id': str(self.machine1.id),
                'title': 'Fake Script',
                'file': file
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.json())

    def test_invalid_pdf_content_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        fake_pdf = SimpleUploadedFile("fake.pdf", b"Not a real PDF stream", content_type="application/pdf")
        response = self.client.post(
            self.docs_url,
            {
                'machine_id': str(self.machine1.id),
                'title': 'Corrupted Doc',
                'file': fake_pdf
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.json())

    def test_empty_file_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        empty_pdf = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        response = self.client.post(
            self.docs_url,
            {
                'machine_id': str(self.machine1.id),
                'title': 'Empty Doc',
                'file': empty_pdf
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.json())

    def test_duplicate_active_pdf_on_same_machine_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        pdf_bytes = generate_test_pdf_bytes(["Unique Machine Manual Content"])
        file1 = SimpleUploadedFile("manual_v1.pdf", pdf_bytes, content_type="application/pdf")
        file2 = SimpleUploadedFile("manual_v2.pdf", pdf_bytes, content_type="application/pdf")

        # First upload
        res1 = self.client.post(
            self.docs_url,
            {'machine_id': str(self.machine1.id), 'title': 'First', 'file': file1},
            format='multipart'
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Duplicate upload to same machine
        res2 = self.client.post(
            self.docs_url,
            {'machine_id': str(self.machine1.id), 'title': 'Second', 'file': file2},
            format='multipart'
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', res2.json())
        self.assertIn('identical active document already exists', str(res2.json()))

    def test_same_pdf_on_different_machine_allowed(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        pdf_bytes = generate_test_pdf_bytes(["Universal Standard Protocol"])
        file1 = SimpleUploadedFile("manual.pdf", pdf_bytes, content_type="application/pdf")
        file2 = SimpleUploadedFile("manual.pdf", pdf_bytes, content_type="application/pdf")

        # Machine 1
        res1 = self.client.post(
            self.docs_url,
            {'machine_id': str(self.machine1.id), 'title': 'Machine 1 Doc', 'file': file1},
            format='multipart'
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Machine 2
        res2 = self.client.post(
            self.docs_url,
            {'machine_id': str(self.machine2.id), 'title': 'Machine 2 Doc', 'file': file2},
            format='multipart'
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

    def test_upload_to_inactive_machine_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        pdf_bytes = generate_test_pdf_bytes(["Test manual content"])
        file = SimpleUploadedFile("manual.pdf", pdf_bytes, content_type="application/pdf")

        response = self.client.post(
            self.docs_url,
            {'machine_id': str(self.inactive_machine.id), 'title': 'Inactive Machine Doc', 'file': file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('machine', response.json())


# ==============================================================================
# 2. Text Extraction & Lifecycle Tests
# ==============================================================================

class PDFExtractionTestCase(BaseDocumentTestCase):
    """
    Tests for PyMuPDF text extraction, page numbering preservation, and image-only PDF handling.
    """

    def test_multi_page_extraction_and_numbering(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        pages_content = [
            "Chapter 1: Safety Regulations",
            "",  # Empty Page 2
            "Chapter 2: Daily Operation"
        ]
        pdf_bytes = generate_test_pdf_bytes(pages_content)
        file = SimpleUploadedFile("multi_page.pdf", pdf_bytes, content_type="application/pdf")

        response = self.client.post(
            self.docs_url,
            {'machine_id': str(self.machine1.id), 'title': 'Multi-Page Manual', 'file': file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(pk=response.json()['id'])

        self.assertEqual(doc.page_count, 3)
        self.assertEqual(doc.status, DocumentStatus.READY)

        pages = doc.pages.order_by('page_number')
        self.assertEqual(pages.count(), 3)
        self.assertEqual(pages[0].page_number, 1)
        self.assertIn("Safety Regulations", pages[0].text)

        # Empty page 2 preserved to maintain correct page indexing
        self.assertEqual(pages[1].page_number, 2)
        self.assertEqual(pages[1].character_count, 0)

        self.assertEqual(pages[2].page_number, 3)
        self.assertIn("Daily Operation", pages[2].text)

    def test_scanned_image_only_pdf_marked_failed(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        # Generate PDF with 0 extractable text (blank/image-only equivalent)
        pdf_bytes = generate_test_pdf_bytes(["", ""])
        file = SimpleUploadedFile("scanned_manual.pdf", pdf_bytes, content_type="application/pdf")

        response = self.client.post(
            self.docs_url,
            {'machine_id': str(self.machine1.id), 'title': 'Scanned Blueprint', 'file': file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(pk=response.json()['id'])

        self.assertEqual(doc.status, DocumentStatus.FAILED)
        self.assertIn("no extractable text", doc.processing_error)
        self.assertEqual(doc.pages.count(), 0)  # No partial pages retained


# ==============================================================================
# 3. Role-Based Access Control & Download Tests
# ==============================================================================

class DocumentAccessControlTestCase(BaseDocumentTestCase):
    """
    Tests enforcing document visibility, page retrieval, and secure download rules:
    - Admin: Full access.
    - Supervisor: Full read/download access to all documents.
    - Engineer: Access restricted to assigned active machines.
    """

    def setUp(self):
        super().setUp()
        self.pdf_bytes = generate_test_pdf_bytes(["Confidential Machine Procedures"])

        # Document on machine1 (Engineer assigned)
        self.doc_assigned = Document.objects.create(
            machine=self.machine1,
            title='Assigned Manual',
            original_filename='assigned.pdf',
            file_size=len(self.pdf_bytes),
            checksum='checksum1',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
            file=SimpleUploadedFile("assigned.pdf", self.pdf_bytes)
        )
        extract_document_pages(self.doc_assigned)

        # Document on machine2 (Engineer NOT assigned)
        self.doc_unassigned = Document.objects.create(
            machine=self.machine2,
            title='Unassigned Manual',
            original_filename='unassigned.pdf',
            file_size=len(self.pdf_bytes),
            checksum='checksum2',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
            file=SimpleUploadedFile("unassigned.pdf", self.pdf_bytes)
        )
        extract_document_pages(self.doc_unassigned)

    def test_admin_sees_all_documents(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.get(self.docs_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [d['title'] for d in response.json()]
        self.assertIn('Assigned Manual', titles)
        self.assertIn('Unassigned Manual', titles)

    def test_supervisor_sees_all_documents(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        response = self.client.get(self.docs_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [d['title'] for d in response.json()]
        self.assertIn('Assigned Manual', titles)
        self.assertIn('Unassigned Manual', titles)

    def test_engineer_only_sees_assigned_machine_documents(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(self.docs_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [d['title'] for d in response.json()]
        self.assertIn('Assigned Manual', titles)
        self.assertNotIn('Unassigned Manual', titles)  # Hidden

    def test_engineer_cannot_retrieve_unassigned_document_by_id(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(f'{self.docs_url}{self.doc_unassigned.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_engineer_cannot_download_unassigned_document(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(f'{self.docs_url}{self.doc_unassigned.id}/download/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_cannot_retrieve_unassigned_document_pages(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(f'{self.docs_url}{self.doc_unassigned.id}/pages/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_can_download_assigned_document(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(f'{self.docs_url}{self.doc_assigned.id}/download/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_engineer_can_retrieve_assigned_document_pages(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(f'{self.docs_url}{self.doc_assigned.id}/pages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.json()), 1)
        self.assertIn('Confidential Machine Procedures', response.json()[0]['text'])

    def test_supervisor_and_engineer_cannot_upload_documents(self):
        file = SimpleUploadedFile("manual.pdf", self.pdf_bytes, content_type="application/pdf")

        # Supervisor upload attempt
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        res_sup = self.client.post(self.docs_url, {'machine_id': str(self.machine1.id), 'title': 'X', 'file': file})
        self.assertEqual(res_sup.status_code, status.HTTP_403_FORBIDDEN)

        # Engineer upload attempt
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        res_eng = self.client.post(self.docs_url, {'machine_id': str(self.machine1.id), 'title': 'X', 'file': file})
        self.assertEqual(res_eng.status_code, status.HTTP_403_FORBIDDEN)

    def test_machine_specific_documents_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')

        # Machine 1 (assigned)
        res_m1 = self.client.get(f'/api/machines/{self.machine1.id}/documents/')
        self.assertEqual(res_m1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_m1.json()), 1)

        # Machine 2 (unassigned) -> Forbidden
        res_m2 = self.client.get(f'/api/machines/{self.machine2.id}/documents/')
        self.assertEqual(res_m2.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_requests_rejected(self):
        response = self.client.get(self.docs_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==============================================================================
# 4. Data Integrity & Soft-Deactivation Tests
# ==============================================================================

class DocumentDataIntegrityTestCase(BaseDocumentTestCase):
    """
    Tests ensuring soft deactivation preserves files, pages, and linkages.
    """

    def test_admin_can_soft_deactivate_document(self):
        pdf_bytes = generate_test_pdf_bytes(["Archived Manual Text"])
        doc = Document.objects.create(
            machine=self.machine1,
            title='Obsolete Manual',
            original_filename='old.pdf',
            file_size=len(pdf_bytes),
            checksum='checksum_del',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
            file=SimpleUploadedFile("old.pdf", pdf_bytes)
        )
        extract_document_pages(doc)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.delete(f'{self.docs_url}{doc.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        doc.refresh_from_db()
        self.assertFalse(doc.is_active)  # Soft deactivated
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())  # Record kept
        self.assertGreater(doc.pages.count(), 0)  # Pages preserved
