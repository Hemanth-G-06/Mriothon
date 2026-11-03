"""
Comprehensive Automated Test Suite for Round 2 Visual Quality Inspection.
Verifies:
1. Authentication & JWT access/refresh handling
2. Role-Based Access Control (RBAC) server-side enforcement
3. Strict image upload validation (size, dimensions, format, corrupt files, misleading extensions)
4. AI computer vision model integration (BIT-PLATE-CV-1.0)
5. Celery & Redis background task processing and fault isolation
6. Database persistence and immutability of original AI predictions
"""

import io
from pathlib import Path
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserRole
from inspections.models import Product, InspectionRecord, BatchInspection
from inspections.tasks import process_inspection_task
from inspections.services.image_validator import (
    validate_image,
    ImageValidationError,
    MAX_FILE_SIZE,
    MIN_DIMENSION,
    MAX_DIMENSION
)
from inspections.services.inference_service import inference_service

User = get_user_model()
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def create_in_memory_image(width=128, height=128, fmt='PNG', color=(128, 128, 128)):
    """Helper creating valid in-memory images using Pillow."""
    buf = io.BytesIO()
    img = Image.new('RGB', (width, height), color=color)
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.getvalue()


class VisualQualityInspectionTestSuite(APITestCase):
    """
    Complete end-to-end and unit test suite for Module B.
    """

    def setUp(self):
        # 1. Provision RBAC users
        self.admin = User.objects.create_user(
            email='sarah.connor@test.com',
            password='AdminPassword123!',
            first_name='Sarah',
            last_name='Connor',
            role=UserRole.ADMIN,
            is_staff=True
        )

        self.engineer = User.objects.create_user(
            email='alex.vance@test.com',
            password='EngineerPassword123!',
            first_name='Alex',
            last_name='Vance',
            role=UserRole.ENGINEER
        )

        self.other_engineer = User.objects.create_user(
            email='gordon.freeman@test.com',
            password='EngineerPassword123!',
            first_name='Gordon',
            last_name='Freeman',
            role=UserRole.ENGINEER
        )

        self.supervisor = User.objects.create_user(
            email='marcus.brody@test.com',
            password='SupervisorPassword123!',
            first_name='Marcus',
            last_name='Brody',
            role=UserRole.SUPERVISOR
        )

        # 2. Register standard product
        self.product = Product.objects.create(
            id='P-PLATE01',
            name='Demonstration metal plate',
            model_version='BIT-PLATE-CV-1.0',
            description='Synthetic centered plate with scratches or pits.',
            status='Active'
        )

        # 3. Create valid test images
        self.valid_png_bytes = create_in_memory_image(128, 128, 'PNG')
        self.valid_jpg_bytes = create_in_memory_image(128, 128, 'JPEG')

    # =========================================================================
    # SECTION 1: AUTHENTICATION & JWT SECURITY
    # =========================================================================

    def test_valid_login(self):
        """Valid credentials return JWT access, refresh tokens, and user profile."""
        response = self.client.post('/api/auth/login/', {
            'email': 'alex.vance@test.com',
            'password': 'EngineerPassword123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['role'], UserRole.ENGINEER)

    def test_invalid_login(self):
        """Invalid credentials return 401 Unauthorized."""
        response = self.client.post('/api/auth/login/', {
            'email': 'alex.vance@test.com',
            'password': 'WrongPassword!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_api_rejection(self):
        """Unauthenticated requests to protected endpoints return 401."""
        response = self.client.get('/api/inspections/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =========================================================================
    # SECTION 2: ROLE-BASED ACCESS CONTROL (RBAC)
    # =========================================================================

    def test_admin_can_register_product(self):
        """Admin is authorized to register a new product."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/products/', {
            'id': 'P-NEW01',
            'name': 'Titanium Flange',
            'model_version': 'BIT-PLATE-CV-1.0',
            'description': 'Aircraft grade flange.'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Product.objects.filter(id='P-NEW01').exists())

    def test_engineer_cannot_register_product(self):
        """Engineer attempting to register a product receives 403 Forbidden."""
        self.client.force_authenticate(user=self.engineer)
        response = self.client.post('/api/products/', {
            'id': 'P-FORBIDDEN',
            'name': 'Unauthorized Product'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Product.objects.filter(id='P-FORBIDDEN').exists())

    def test_engineer_only_views_own_inspection_history(self):
        """Engineers querying /api/inspections/ receive only their own records."""
        # Create record for Engineer 1
        rec1 = InspectionRecord.objects.create(
            product=self.product,
            user=self.engineer,
            engineer_name=self.engineer.full_name,
            predicted_class='Normal',
            confidence=0.95
        )
        # Create record for Engineer 2
        rec2 = InspectionRecord.objects.create(
            product=self.product,
            user=self.other_engineer,
            engineer_name=self.other_engineer.full_name,
            predicted_class='Defective',
            confidence=0.99
        )

        self.client.force_authenticate(user=self.engineer)
        response = self.client.get('/api/inspections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['results']
        retrieved_ids = [r['id'] for r in results]
        self.assertIn(rec1.id, retrieved_ids)
        self.assertNotIn(rec2.id, retrieved_ids)

    def test_engineer_cannot_access_other_engineer_record_detail(self):
        """Engineer requesting detail of another engineer's inspection receives 403."""
        other_rec = InspectionRecord.objects.create(
            product=self.product,
            user=self.other_engineer,
            engineer_name=self.other_engineer.full_name,
            predicted_class='Normal',
            confidence=0.90
        )
        self.client.force_authenticate(user=self.engineer)
        response = self.client.get(f'/api/inspections/{other_rec.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_cannot_submit_supervisor_review(self):
        """Direct API review call by Engineer must receive 403 Forbidden."""
        record = InspectionRecord.objects.create(
            product=self.product,
            user=self.engineer,
            predicted_class='Defective',
            confidence=0.92
        )
        self.client.force_authenticate(user=self.engineer)
        response = self.client.post(f'/api/inspections/{record.id}/review/', {
            'action': 'confirm'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_can_view_all_completed_inspections(self):
        """Supervisors can view completed inspections across all engineers."""
        InspectionRecord.objects.create(
            product=self.product,
            user=self.engineer,
            engineer_name='Alex Vance',
            predicted_class='Normal',
            confidence=0.91
        )
        InspectionRecord.objects.create(
            product=self.product,
            user=self.other_engineer,
            engineer_name='Gordon Freeman',
            predicted_class='Defective',
            confidence=0.97
        )

        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get('/api/supervisor/inspections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_supervisor_can_confirm_and_correct_predictions(self):
        """Supervisor can confirm or correct an inspection while preserving AI output."""
        rec = InspectionRecord.objects.create(
            product=self.product,
            user=self.engineer,
            predicted_class='Defective',
            confidence=0.87,
            defect_probability=0.87,
            model_version='BIT-PLATE-CV-1.0'
        )

        self.client.force_authenticate(user=self.supervisor)
        # Correct determination
        response = self.client.post(f'/api/inspections/{rec.id}/review/', {
            'action': 'correct',
            'corrected_class': 'Normal',
            'comment': 'Surface shadow anomaly, passed micrometer depth gauge.'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rec.refresh_from_db()
        # Original AI prediction must be completely intact
        self.assertEqual(rec.predicted_class, 'Defective')
        self.assertEqual(rec.confidence, 0.87)
        self.assertEqual(rec.defect_probability, 0.87)
        # Supervisor decisions stored separately
        self.assertEqual(rec.review_status, 'corrected')
        self.assertEqual(rec.supervisor_class, 'Normal')
        self.assertEqual(rec.supervisor, self.supervisor)
        self.assertEqual(rec.review_comment, 'Surface shadow anomaly, passed micrometer depth gauge.')
        self.assertIsNotNone(rec.reviewed_at)

    # =========================================================================
    # SECTION 3: IMAGE UPLOAD VALIDATION
    # =========================================================================

    def test_valid_jpeg_and_png_accepted(self):
        """Valid JPEG and PNG images pass server-side validation."""
        fmt_png, w_png, h_png = validate_image(self.valid_png_bytes, 'plate.png')
        self.assertEqual(fmt_png, 'PNG')
        self.assertEqual(w_png, 128)
        self.assertEqual(h_png, 128)

        fmt_jpg, w_jpg, h_jpg = validate_image(self.valid_jpg_bytes, 'plate.jpg')
        self.assertEqual(fmt_jpg, 'JPEG')
        self.assertEqual(w_jpg, 128)
        self.assertEqual(h_jpg, 128)

    def test_unsupported_file_extension_rejected(self):
        """Files with unsupported extensions are rejected."""
        with self.assertRaises(ImageValidationError):
            validate_image(self.valid_png_bytes, 'plate.gif')

        with self.assertRaises(ImageValidationError):
            validate_image(b'hello world', 'document.txt')

    def test_fake_jpg_content_rejected(self):
        """Non-image data renamed with .jpg extension is rejected."""
        fake_jpg = b'Plain text disguised as a JPEG image.'
        with self.assertRaises(ImageValidationError):
            validate_image(fake_jpg, 'not_an_image.jpg')

        # Test against official Validation/not_an_image.jpg
        official_fake = WORKSPACE_ROOT / "Validation" / "not_an_image.jpg"
        if official_fake.exists():
            with open(official_fake, 'rb') as f:
                with self.assertRaises(ImageValidationError):
                    validate_image(f.read(), 'not_an_image.jpg')

    def test_corrupted_image_rejected(self):
        """Corrupted/truncated images are rejected."""
        corrupt_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + b'random corrupted bytes'
        with self.assertRaises(ImageValidationError):
            validate_image(corrupt_data, 'corrupt.png')

        # Test against official Validation/corrupt_image.png
        official_corrupt = WORKSPACE_ROOT / "Validation" / "corrupt_image.png"
        if official_corrupt.exists():
            with open(official_corrupt, 'rb') as f:
                with self.assertRaises(ImageValidationError):
                    validate_image(f.read(), 'corrupt_image.png')

    def test_sub_minimum_dimensions_rejected(self):
        """Images smaller than 64x64 are rejected."""
        small_bytes = create_in_memory_image(32, 32, 'PNG')
        with self.assertRaises(ImageValidationError):
            validate_image(small_bytes, 'too_small.png')

        # Test against official Validation/too_small.png
        official_small = WORKSPACE_ROOT / "Validation" / "too_small.png"
        if official_small.exists():
            with open(official_small, 'rb') as f:
                with self.assertRaises(ImageValidationError):
                    validate_image(f.read(), 'too_small.png')

    def test_oversized_file_rejected(self):
        """Files exceeding 5 MiB are rejected."""
        oversized = b'0' * (MAX_FILE_SIZE + 1024)
        with self.assertRaises(ImageValidationError):
            validate_image(oversized, 'huge.jpg')

    def test_empty_image_rejected(self):
        """Zero-byte files are rejected."""
        with self.assertRaises(ImageValidationError):
            validate_image(b'', 'empty.png')

    def test_empty_batch_rejected(self):
        """Batch upload with 0 files returns 400 Bad Request."""
        self.client.force_authenticate(user=self.engineer)
        response = self.client.post('/api/inspections/batch/', {
            'product_id': 'P-PLATE01'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_batch_rejected(self):
        """Batch uploads with more than 10 files return 400 Bad Request."""
        self.client.force_authenticate(user=self.engineer)
        files = [
            SimpleUploadedFile(f'img_{i}.png', self.valid_png_bytes, content_type='image/png')
            for i in range(11)
        ]
        response = self.client.post('/api/inspections/batch/', {
            'files': files,
            'product_id': 'P-PLATE01'
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # SECTION 4: AI INFERENCE SERVICE
    # =========================================================================

    def test_official_inference_service(self):
        """Official inference service correctly scores sample images."""
        sample_img = WORKSPACE_ROOT / "Samples" / "images" / "inspection_001.png"
        if sample_img.exists():
            result = inference_service.run_inference(str(sample_img))
            self.assertEqual(result['predicted_class'], 'Defective')
            self.assertEqual(result['confidence'], 1.0)
            self.assertEqual(result['defect_probability'], 1.0)
            self.assertEqual(result['model_version'], 'BIT-PLATE-CV-1.0')

    def test_single_inspection_full_flow(self):
        """Single image upload runs AI model and returns complete contract payload."""
        self.client.force_authenticate(user=self.engineer)
        sample_img = WORKSPACE_ROOT / "Samples" / "images" / "inspection_002.jpg"
        if sample_img.exists():
            with open(sample_img, 'rb') as f:
                upload_file = SimpleUploadedFile('inspection_002.jpg', f.read(), content_type='image/jpeg')

            response = self.client.post('/api/inspections/single/', {
                'file': upload_file,
                'product_id': 'P-PLATE01'
            }, format='multipart')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            data = response.data
            self.assertEqual(data['product_id'], 'P-PLATE01')
            self.assertEqual(data['predicted_class'], 'Normal')
            self.assertGreater(data['confidence'], 0.9)
            self.assertEqual(data['model_version'], 'BIT-PLATE-CV-1.0')
            self.assertEqual(data['status'], 'Completed')
            self.assertIsNotNone(data['image_url'])

    # =========================================================================
    # SECTION 5: CELERY & REDIS ASYNCHRONOUS BATCH PROCESSING
    # =========================================================================

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_batch_processing_with_mixed_valid_and_invalid_files(self):
        """
        Batch containing both valid images and invalid files:
        1. Valid images are processed and scored.
        2. Invalid files are recorded as failed attempts with readable failure reasons and NO prediction.
        3. One failed item does not stop valid items.
        """
        self.client.force_authenticate(user=self.engineer)

        # 1 valid sample, 1 invalid text file
        valid_file = SimpleUploadedFile('valid.png', self.valid_png_bytes, content_type='image/png')
        invalid_file = SimpleUploadedFile('corrupt.jpg', b'Text pretending to be jpg', content_type='image/jpeg')

        response = self.client.post('/api/inspections/batch/', {
            'files': [valid_file, invalid_file],
            'product_id': 'P-PLATE01'
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        batch_id = response.data['batch_id']
        self.assertEqual(response.data['total'], 2)
        self.assertEqual(response.data['failed'], 1)

        # Poll batch status
        status_res = self.client.get(f'/api/inspections/batch/{batch_id}/')
        self.assertEqual(status_res.status_code, status.HTTP_200_OK)
        items = status_res.data['items']
        self.assertEqual(len(items), 2)

        # Verify invalid item has failure reason and no AI prediction
        failed_item = next(it for it in items if it['file_name'] == 'corrupt.jpg')
        self.assertEqual(failed_item['status'], 'Failed')
        self.assertEqual(failed_item['predicted_class'], '')
        self.assertIsNone(failed_item['confidence'])
        self.assertTrue(len(failed_item['failure_reason']) > 0)

        # Verify valid item completed successfully
        valid_item = next(it for it in items if it['file_name'] == 'valid.png')
        self.assertEqual(valid_item['status'], 'Completed')
        self.assertIn(valid_item['predicted_class'], ['Normal', 'Defective'])
        self.assertIsNotNone(valid_item['confidence'])
