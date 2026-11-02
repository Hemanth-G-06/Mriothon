"""
Test suite for Visual Quality Inspection API endpoints.
Tests product registry, single inspection inference, batch uploads,
supervisor audit review, and RBAC permissions.
"""

import zlib
import struct
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserRole
from inspections.models import Product, InspectionRecord, BatchInspection

User = get_user_model()


def generate_valid_png_bytes(width=64, height=64, color=(128, 128, 128)):
    """Generates an in-memory valid PNG image conforming to challenge constraints."""
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw_scanlines = b''.join([b'\x00' + bytes(color) * width for _ in range(height)])
    idat = chunk(b'IDAT', zlib.compress(raw_scanlines))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend


class InspectionAPITests(APITestCase):
    """
    Test cases for /api/inspections/ and /api/products/
    """

    def setUp(self):
        # 1. Create RBAC Test Users
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            role=UserRole.ADMIN
        )

        self.engineer_user = User.objects.create_user(
            email='engineer@test.com',
            password='Password123!',
            first_name='John',
            last_name='Engineer',
            role=UserRole.ENGINEER
        )

        self.supervisor_user = User.objects.create_user(
            email='supervisor@test.com',
            password='Password123!',
            first_name='Jane',
            last_name='Supervisor',
            role=UserRole.SUPERVISOR
        )

        # 2. Seed Target Product
        self.product = Product.objects.create(
            id='P-PLATE01',
            name='Industrial Metal Base Plate',
            model_version='BIT-PLATE-CV-1.0',
            category='Milled Components',
            status='Active'
        )

        # 3. Create Sample PNG Image
        self.valid_png = generate_valid_png_bytes(128, 128)

    def test_products_list_endpoint(self):
        """GET /api/products/ should return list including P-PLATE01."""
        self.client.force_authenticate(user=self.engineer_user)
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p['id'] for p in response.data]
        self.assertIn('P-PLATE01', ids)

    def test_single_inspection_upload(self):
        """POST /api/inspections/single/ should upload plate image and return genuine AI inference."""
        self.client.force_authenticate(user=self.engineer_user)

        file = SimpleUploadedFile(
            'plate_sample.png',
            self.valid_png,
            content_type='image/png'
        )

        response = self.client.post(
            '/api/inspections/single/',
            {'file': file, 'product_id': 'P-PLATE01'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data['product_id'], 'P-PLATE01')
        self.assertIn(data['predicted_class'], ['Normal', 'Defective'])
        self.assertGreater(data['confidence'], 0.0)
        self.assertEqual(data['model_version'], 'BIT-PLATE-CV-1.0')
        self.assertIsNotNone(data['image_url'])

    def test_single_inspection_invalid_format_rejected(self):
        """Non-JPEG/PNG files must be rejected with 400 Bad Request."""
        self.client.force_authenticate(user=self.engineer_user)

        bad_file = SimpleUploadedFile(
            'document.txt',
            b'Not an image',
            content_type='text/plain'
        )

        response = self.client.post(
            '/api/inspections/single/',
            {'file': bad_file, 'product_id': 'P-PLATE01'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inspections_product_filter(self):
        """GET /api/inspections/?product_id=P-PLATE01 must return only inspections for that product."""
        # Create inspection for P-PLATE01
        rec1 = InspectionRecord.objects.create(
            product=self.product,
            product_id='P-PLATE01',
            user=self.engineer_user,
            engineer_name='John Engineer',
            predicted_class='Normal',
            confidence=0.98,
            defect_probability=0.02
        )

        # Create inspection for different product
        other_prod = Product.objects.create(id='P-OTHER99', name='Other Component')
        rec2 = InspectionRecord.objects.create(
            product=other_prod,
            product_id='P-OTHER99',
            user=self.engineer_user,
            engineer_name='John Engineer',
            predicted_class='Defective',
            confidence=0.95,
            defect_probability=0.95
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/inspections/?product_id=P-PLATE01')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['results']
        retrieved_ids = [r['id'] for r in results]
        self.assertIn(rec1.id, retrieved_ids)
        self.assertNotIn(rec2.id, retrieved_ids)

    def test_batch_inspection_upload(self):
        """POST /api/inspections/batch/ should process 1-10 files."""
        self.client.force_authenticate(user=self.engineer_user)

        file1 = SimpleUploadedFile('img1.png', self.valid_png, content_type='image/png')
        file2 = SimpleUploadedFile('img2.png', self.valid_png, content_type='image/png')

        response = self.client.post(
            '/api/inspections/batch/',
            {'files': [file1, file2], 'product_id': 'P-PLATE01'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('batch_id', response.data)
        self.assertEqual(response.data['total'], 2)
        self.assertEqual(len(response.data['items']), 2)

    def test_supervisor_review_confirm_action(self):
        """Supervisor confirming AI prediction marks it confirmed without altering AI class."""
        record = InspectionRecord.objects.create(
            product=self.product,
            product_id='P-PLATE01',
            user=self.engineer_user,
            engineer_name='John Engineer',
            predicted_class='Normal',
            confidence=0.985,
            review_status='pending'
        )

        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.post(
            f'/api/inspections/{record.id}/review/',
            {'action': 'confirm', 'comment': 'Visual inspection verified compliant.'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data['review_status'], 'confirmed')
        self.assertEqual(data['predicted_class'], 'Normal')
        self.assertEqual(data['supervisor_class'], 'Normal')
        self.assertEqual(data['supervisor_name'], self.supervisor_user.full_name)

    def test_supervisor_review_correct_action(self):
        """Supervisor correcting AI prediction overrides determination while preserving original AI class."""
        record = InspectionRecord.objects.create(
            product=self.product,
            product_id='P-PLATE01',
            user=self.engineer_user,
            engineer_name='John Engineer',
            predicted_class='Defective',
            confidence=0.88,
            review_status='pending'
        )

        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.post(
            f'/api/inspections/{record.id}/review/',
            {
                'action': 'correct',
                'corrected_class': 'Normal',
                'comment': 'Surface shadow was mistaken for hairline crack; physical dimensions pass.'
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # Original AI class must remain 'Defective'
        self.assertEqual(data['predicted_class'], 'Defective')
        # Supervisor override must be 'Normal'
        self.assertEqual(data['supervisor_class'], 'Normal')
        self.assertEqual(data['review_status'], 'corrected')

    def test_engineer_cannot_submit_supervisor_review(self):
        """Engineers must receive 403 Forbidden when attempting to submit a review."""
        record = InspectionRecord.objects.create(
            product=self.product,
            product_id='P-PLATE01',
            user=self.engineer_user,
            predicted_class='Normal'
        )

        self.client.force_authenticate(user=self.engineer_user)
        response = self.client.post(
            f'/api/inspections/{record.id}/review/',
            {'action': 'confirm'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
