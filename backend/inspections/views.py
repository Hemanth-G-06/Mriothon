"""
API Views for the Inspections application.

Provides REST endpoints for:
1. Product management (/api/products/)
2. Single image inspection inference (/api/inspections/single/)
3. High-throughput batch image inspection (/api/inspections/batch/)
4. Persistent inspection history query & filtering (/api/inspections/)
5. Supervisor quality review audit & calibration (/api/inspections/:id/review/)
"""

import os
import uuid
from datetime import datetime
from django.db.models import Q
from django.utils import timezone
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
from accounts.permissions import IsAdmin, IsSupervisor
from inspections.models import Product, InspectionRecord, BatchInspection
from inspections.serializers import (
    ProductSerializer,
    InspectionRecordSerializer,
    SupervisorReviewSerializer,
    BatchInspectionSerializer
)
from inspections.classifier import classifier, validate_image_bytes, ImageValidationError


DEFAULT_PLATE_PRODUCT = {
    'id': 'P-PLATE01',
    'name': 'Industrial Metal Base Plate',
    'model_version': 'BIT-PLATE-CV-1.0',
    'category': 'Milled Components',
    'description': 'Precision milled metallic mounting plate inspected for surface cracks, porosities, and machining defects.',
    'status': 'Active',
    'min_dimensions': '64x64',
    'max_dimensions': '4096x4096'
}


def ensure_default_product_exists():
    """Idempotently seeds P-PLATE01 in the database if not present."""
    Product.objects.get_or_create(
        id='P-PLATE01',
        defaults=DEFAULT_PLATE_PRODUCT
    )


# ==============================================================================
# 1. Product Registry Endpoints
# ==============================================================================

class ProductListCreateView(APIView):
    """
    GET  /api/products/ - List all registered inspection products.
    POST /api/products/ - Register new product (Admin only).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ensure_default_product_exists()
        products = Product.objects.all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not (request.user.role == UserRole.ADMIN or request.user.is_superuser):
            return Response(
                {'detail': 'Only administrators can register inspection products.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    """
    GET /api/products/<str:pk>/ - Retrieve specifications for a registered product.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ensure_default_product_exists()
        try:
            product = Product.objects.get(id=pk.upper())
            serializer = ProductSerializer(product)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response(
                {'detail': f"Product '{pk}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )


# ==============================================================================
# 2. Inspection Query & History Endpoints
# ==============================================================================

class InspectionListView(APIView):
    """
    GET /api/inspections/
    Retrieves inspection records filtered by product, class, status, review, and search query.

    Role Permissions:
    - Admin: View all inspection records across any product.
    - Supervisor: View all completed inspections.
    - Engineer: View only their own inspection submissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = InspectionRecord.objects.all().order_by('-created_at')

        # Role Scoping
        is_admin_or_super = (
            request.user.role in (UserRole.ADMIN, UserRole.SUPERVISOR) or
            request.user.is_superuser
        )

        product_id = request.query_params.get('product_id', '').strip()

        # If user is an engineer and not querying admin product details, scope to user
        if not is_admin_or_super:
            queryset = queryset.filter(user=request.user)

        # Filter by Product ID (e.g. ?product_id=P-PLATE01)
        if product_id:
            queryset = queryset.filter(
                Q(product__id__iexact=product_id) |
                Q(product__name__iexact=product_id)
            )

        # Keyword Search
        search = request.query_params.get('search', '').strip()
        if search:
            if search.isdigit():
                queryset = queryset.filter(
                    Q(id=int(search)) |
                    Q(engineer_name__icontains=search) |
                    Q(product__id__icontains=search)
                )
            else:
                queryset = queryset.filter(
                    Q(engineer_name__icontains=search) |
                    Q(product__id__icontains=search) |
                    Q(product__name__icontains=search) |
                    Q(file_name__icontains=search)
                )

        # Class Filter (Normal / Defective)
        predicted_class = request.query_params.get('predicted_class', '').strip()
        if predicted_class and predicted_class.lower() != 'all':
            queryset = queryset.filter(predicted_class__iexact=predicted_class)

        # Processing Status Filter (Completed, Processing, Failed)
        status_param = request.query_params.get('status', '').strip()
        if status_param and status_param.lower() != 'all':
            queryset = queryset.filter(status__iexact=status_param)

        # Review Status Filter (pending, confirmed, corrected)
        review_status = request.query_params.get('review_status', '').strip()
        if review_status and review_status.lower() != 'all':
            queryset = queryset.filter(review_status__iexact=review_status)

        # Date Filter (YYYY-MM-DD)
        date_param = request.query_params.get('date', '').strip()
        if date_param:
            queryset = queryset.filter(created_at__date=date_param)

        total_count = queryset.count()

        # Optional pagination support
        page_str = request.query_params.get('page')
        if page_str and page_str.isdigit():
            page = max(1, int(page_str))
            page_size = 12
            start = (page - 1) * page_size
            queryset = queryset[start:start + page_size]

        serializer = InspectionRecordSerializer(queryset, many=True, context={'request': request})
        return Response({
            'count': total_count,
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Alias redirecting POST /api/inspections/ to SingleInspectionView."""
        return SingleInspectionView().post(request)


class InspectionDetailView(APIView):
    """
    GET /api/inspections/<int:pk>/
    Retrieves full telemetry for a single inspection record.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            record = InspectionRecord.objects.get(pk=pk)
            # Engineers can only view their own record unless admin/supervisor
            is_admin_or_super = (
                request.user.role in (UserRole.ADMIN, UserRole.SUPERVISOR) or
                request.user.is_superuser
            )
            if not is_admin_or_super and record.user != request.user:
                return Response(
                    {'detail': 'You do not have permission to view this inspection record.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = InspectionRecordSerializer(record, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except InspectionRecord.DoesNotExist:
            return Response(
                {'detail': f"Inspection record #{pk} not found."},
                status=status.HTTP_404_NOT_FOUND
            )


# ==============================================================================
# 3. Single Image Inspection Inference Endpoint
# ==============================================================================

class SingleInspectionView(APIView):
    """
    POST /api/inspections/single/ (also POST /api/inspections/)
    Uploads a single plate image for AI computer vision inference.

    Payload: multipart/form-data
    - file: Image file (JPEG/PNG, max 5 MiB, 64x64 to 4096x4096)
    - product_id: Target product ID (e.g. "P-PLATE01")
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'detail': "An image file is required under the 'file' parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        product_id = request.data.get('product_id', 'P-PLATE01').strip().upper()
        ensure_default_product_exists()
        product = Product.objects.filter(id=product_id).first()

        try:
            file_bytes = uploaded_file.read()
            # 1. Structural image validation
            img_format, width, height = validate_image_bytes(file_bytes, uploaded_file.name)

            # 2. Run genuine Computer Vision inference model (BIT-PLATE-CV-1.0)
            prediction = classifier.predict(file_bytes, uploaded_file.name)

            # 3. Persist InspectionRecord
            record = InspectionRecord(
                product=product,
                product_id=product_id,
                user=request.user,
                engineer_name=request.user.full_name,
                file_name=uploaded_file.name,
                file_size=len(file_bytes),
                image_width=width,
                image_height=height,
                predicted_class=prediction['predicted_class'],
                confidence=prediction['confidence'],
                defect_probability=prediction['defect_probability'],
                model_version=prediction['model_version'],
                status=InspectionRecord.STATUS_COMPLETED,
                review_status=InspectionRecord.REVIEW_PENDING
            )

            # Save uploaded image file to media storage
            record.image.save(uploaded_file.name, ContentFile(file_bytes), save=False)
            record.save()

            serializer = InspectionRecordSerializer(record, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ImageValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'detail': f"Inference processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==============================================================================
# 4. Batch Image Inspection Endpoint
# ==============================================================================

class BatchInspectionView(APIView):
    """
    POST /api/inspections/batch/
    Uploads a batch of 1 to 10 images for high-throughput automated inspection.
    Fault-isolated: A corrupted image does not prevent remaining valid images from being processed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Support both 'files' and 'images' parameter names
        file_list = request.FILES.getlist('files') or request.FILES.getlist('images')
        if not file_list:
            return Response(
                {'detail': "Please select between 1 and 10 image files under the 'files' field."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(file_list) > 10:
            return Response(
                {'detail': f"Maximum batch limit exceeded. You submitted {len(file_list)} images, but maximum allowed is 10."},
                status=status.HTTP_400_BAD_REQUEST
            )

        product_id = request.data.get('product_id', 'P-PLATE01').strip().upper()
        ensure_default_product_exists()
        product = Product.objects.filter(id=product_id).first()

        batch_id = f"BATCH-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        batch_obj = BatchInspection.objects.create(
            batch_id=batch_id,
            product_id=product_id,
            user=request.user,
            total_images=len(file_list),
            status='Processing'
        )

        completed_items = []
        completed_count = 0
        failed_count = 0

        for uploaded_file in file_list:
            try:
                file_bytes = uploaded_file.read()
                img_format, width, height = validate_image_bytes(file_bytes, uploaded_file.name)
                prediction = classifier.predict(file_bytes, uploaded_file.name)

                record = InspectionRecord(
                    product=product,
                    product_id=product_id,
                    user=request.user,
                    engineer_name=request.user.full_name,
                    file_name=uploaded_file.name,
                    file_size=len(file_bytes),
                    image_width=width,
                    image_height=height,
                    predicted_class=prediction['predicted_class'],
                    confidence=prediction['confidence'],
                    defect_probability=prediction['defect_probability'],
                    model_version=prediction['model_version'],
                    status=InspectionRecord.STATUS_COMPLETED,
                    review_status=InspectionRecord.REVIEW_PENDING,
                    batch_id=batch_id
                )
                record.image.save(uploaded_file.name, ContentFile(file_bytes), save=False)
                record.save()

                completed_count += 1
                serialized = InspectionRecordSerializer(record, context={'request': request}).data
                completed_items.append(serialized)

            except ImageValidationError as val_err:
                failed_count += 1
                completed_items.append({
                    'id': None,
                    'file_name': uploaded_file.name,
                    'status': 'Failed',
                    'error': str(val_err)
                })
            except Exception as e:
                failed_count += 1
                completed_items.append({
                    'id': None,
                    'file_name': uploaded_file.name,
                    'status': 'Failed',
                    'error': f"Processing error: {str(e)}"
                })

        batch_obj.completed_count = completed_count
        batch_obj.failed_count = failed_count
        batch_obj.status = 'Completed'
        batch_obj.save()

        return Response({
            'batch_id': batch_id,
            'total': len(file_list),
            'completed': completed_count,
            'failed': failed_count,
            'items': completed_items
        }, status=status.HTTP_201_CREATED)


class BatchStatusView(APIView):
    """
    GET /api/inspections/batch/<str:batch_id>/
    Polls the progress status of an asynchronous or executed batch inspection.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id):
        try:
            batch_obj = BatchInspection.objects.get(batch_id=batch_id)
            serializer = BatchInspectionSerializer(batch_obj, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BatchInspection.DoesNotExist:
            return Response(
                {'detail': f"Batch '{batch_id}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )


# ==============================================================================
# 5. Supervisor Inspection Review & Audit Endpoints
# ==============================================================================

class SupervisorInspectionListView(APIView):
    """
    GET /api/supervisor/inspections/
    Queue of completed visual quality inspections for supervisor review.
    Accessible strictly by Supervisors and Administrators.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.role in (UserRole.SUPERVISOR, UserRole.ADMIN) or request.user.is_superuser):
            return Response(
                {'detail': 'Only Supervisors or Administrators can access the inspection review queue.'},
                status=status.HTTP_403_FORBIDDEN
            )

        queryset = InspectionRecord.objects.all().order_by('-created_at')

        review_status = request.query_params.get('review_status', '').strip()
        if review_status and review_status.lower() != 'all':
            queryset = queryset.filter(review_status__iexact=review_status)

        predicted_class = request.query_params.get('predicted_class', '').strip()
        if predicted_class and predicted_class.lower() != 'all':
            queryset = queryset.filter(predicted_class__iexact=predicted_class)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(engineer_name__icontains=search) |
                Q(product__id__icontains=search) |
                Q(product__name__icontains=search) |
                Q(file_name__icontains=search)
            )

        date_param = request.query_params.get('date', '').strip()
        if date_param:
            queryset = queryset.filter(created_at__date=date_param)

        serializer = InspectionRecordSerializer(queryset, many=True, context={'request': request})
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class SupervisorReviewView(APIView):
    """
    POST /api/inspections/<int:pk>/review/ (and /api/supervisor/inspections/<int:pk>/review/)
    Submits supervisor confirmation or correction.

    Guarantees:
    - The original AI prediction is NEVER overwritten.
    - Captures supervisor identity, reviewed class, timestamp, and optional comment.
    - Strictly authorized to Supervisors and Administrators.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (request.user.role in (UserRole.SUPERVISOR, UserRole.ADMIN) or request.user.is_superuser):
            return Response(
                {'detail': 'Only Supervisors or Administrators are authorized to review inspection records.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            record = InspectionRecord.objects.get(pk=pk)
        except InspectionRecord.DoesNotExist:
            return Response(
                {'detail': f"Inspection record #{pk} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        review_serializer = SupervisorReviewSerializer(data=request.data)
        if not review_serializer.is_valid():
            return Response(review_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = review_serializer.validated_data['action']
        comment = review_serializer.validated_data.get('comment', '').strip()

        if action == 'confirm':
            record.review_status = InspectionRecord.REVIEW_CONFIRMED
            # Confirming retains the original AI class as the approved verdict
            record.supervisor_class = record.predicted_class
        elif action == 'correct':
            record.review_status = InspectionRecord.REVIEW_CORRECTED
            record.supervisor_class = review_serializer.validated_data['corrected_class']

        # Capture audit trail metadata
        record.supervisor = request.user
        record.supervisor_name = request.user.full_name
        record.review_comment = comment
        record.reviewed_at = timezone.now()
        record.save()

        # Return updated record with full supervisor details
        output_serializer = InspectionRecordSerializer(record, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)
