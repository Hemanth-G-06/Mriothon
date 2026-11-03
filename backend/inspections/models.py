"""
Models for the Inspections application.
Tracks registered manufactured products, inspection records, model inference telemetry,
and supervisor audit history.
"""

from django.db import models
from django.conf import settings


class Product(models.Model):
    """
    Manufactured product registered for AI visual quality inspection.
    Example: P-PLATE01 (Demonstration metal plate).
    """
    id = models.CharField(
        max_length=100,
        primary_key=True,
        help_text="Unique Product ID (e.g. P-PLATE01)"
    )
    name = models.CharField(max_length=255, default='Demonstration metal plate', help_text="Product name")
    model_version = models.CharField(
        max_length=100,
        default='BIT-PLATE-CV-1.0',
        help_text="Target computer vision classifier model"
    )
    category = models.CharField(max_length=100, default='Milled Components')
    description = models.TextField(
        blank=True,
        default='Synthetic centered plate with scratches or pits.'
    )
    status = models.CharField(max_length=50, default='Active')
    min_dimensions = models.CharField(max_length=50, default='64x64')
    max_dimensions = models.CharField(max_length=50, default='4096x4096')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.id} — {self.name}"


class BatchInspection(models.Model):
    """
    Tracks bulk upload batch execution state, Celery tasks, and progress.
    """
    batch_id = models.CharField(max_length=100, primary_key=True)
    product_id = models.CharField(max_length=100, default='P-PLATE01')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batch_inspections'
    )
    total_images = models.IntegerField(default=0)
    completed_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    processing_count = models.IntegerField(default=0)
    queued_count = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='Queued')  # Queued, Processing, Completed, Failed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Batch {self.batch_id} ({self.completed_count}/{self.total_images})"


class InspectionRecord(models.Model):
    """
    Visual quality inspection record for a single manufactured component image.
    Preserves original AI prediction and any subsequent supervisor review decisions.
    """
    CLASS_NORMAL = 'Normal'
    CLASS_DEFECTIVE = 'Defective'
    CLASS_CHOICES = [
        (CLASS_NORMAL, 'Normal'),
        (CLASS_DEFECTIVE, 'Defective'),
    ]

    STATUS_QUEUED = 'Queued'
    STATUS_PROCESSING = 'Processing'
    STATUS_COMPLETED = 'Completed'
    STATUS_FAILED = 'Failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    REVIEW_PENDING = 'pending'
    REVIEW_CONFIRMED = 'confirmed'
    REVIEW_CORRECTED = 'corrected'
    REVIEW_CHOICES = [
        (REVIEW_PENDING, 'Pending Review'),
        (REVIEW_CONFIRMED, 'Confirmed'),
        (REVIEW_CORRECTED, 'Corrected'),
    ]

    product = models.ForeignKey(
        Product,
        to_field='id',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default='P-PLATE01',
        related_name='inspections'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspections'
    )
    engineer_name = models.CharField(max_length=255, blank=True, default='Plant Engineer')

    image = models.FileField(upload_to='inspections/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, default='')
    file_size = models.BigIntegerField(default=0)
    image_width = models.IntegerField(default=0)
    image_height = models.IntegerField(default=0)

    # Genuine AI Inference Outputs (Immutable once set; empty for invalid/failed items)
    predicted_class = models.CharField(max_length=50, blank=True, default='')
    confidence = models.FloatField(null=True, blank=True, default=None)
    defect_probability = models.FloatField(null=True, blank=True, default=None)
    model_version = models.CharField(max_length=100, default='BIT-PLATE-CV-1.0')

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    failure_reason = models.TextField(blank=True, default='')

    # Backward compatibility alias
    @property
    def error_message(self):
        return self.failure_reason

    @error_message.setter
    def error_message(self, val):
        self.failure_reason = val

    # Supervisor Review Audit Section (Kept strictly separate from AI predictions)
    review_status = models.CharField(max_length=50, choices=REVIEW_CHOICES, default=REVIEW_PENDING, db_index=True)
    supervisor_class = models.CharField(max_length=50, blank=True, default='')
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_inspections'
    )
    supervisor_name = models.CharField(max_length=255, blank=True, default='')
    review_comment = models.TextField(blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    batch_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        pred = self.predicted_class or "No prediction"
        conf_str = f" ({self.confidence * 100:.1f}%)" if self.confidence is not None else ""
        return f"[{self.product_id}] Inspection #{self.id}: {pred}{conf_str} - {self.status}"
