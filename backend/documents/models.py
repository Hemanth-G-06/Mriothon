"""
Models for the Documents application.

Domain models for technical manuals, PDF documents, page metadata,
and file storage tracking.
"""

from django.db import models
from machines.models import Machine


class Document(models.Model):
    """
    Technical manual, OEM schematic, or operation documentation PDF asset.
    """
    MANUAL_TYPES = [
        ('Operations Manual', 'Operations Manual'),
        ('Maintenance Manual', 'Maintenance Manual'),
        ('Troubleshooting Guide', 'Troubleshooting Guide'),
        ('Safety Manual', 'Safety Manual'),
        ('Installation Guide', 'Installation Guide'),
        ('Electrical Schematics', 'Electrical Schematics'),
    ]

    STATUS_CHOICES = [
        ('Uploaded', 'Uploaded'),
        ('Processing', 'Processing'),
        ('Indexed', 'Indexed'),
        ('Failed', 'Failed'),
    ]

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255, help_text="Document or manual title")
    manual_type = models.CharField(max_length=100, choices=MANUAL_TYPES, default='Operations Manual')
    model_number = models.CharField(max_length=100, blank=True, default='')
    revision = models.CharField(max_length=50, blank=True, default='Rev 1.0')
    file = models.FileField(upload_to='manuals/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, default='')
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Indexed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.machine.name})"
