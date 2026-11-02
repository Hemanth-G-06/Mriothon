"""
Models for the Machines application.

Domain models for registered machines, machine models, identifiers,
and technical metadata.
"""

from django.db import models


class Machine(models.Model):
    """
    Industrial manufacturing machine asset registered in the facility.
    """
    name = models.CharField(max_length=255, help_text="Equipment asset name")
    model_number = models.CharField(max_length=100, blank=True, default='', help_text="Manufacturer model identifier")
    serial_number = models.CharField(max_length=100, blank=True, default='', help_text="Hardware serial number")
    location = models.CharField(max_length=255, blank=True, default='Main Plant Floor', help_text="Physical installation location")
    description = models.TextField(blank=True, default='', help_text="Technical specifications and summary")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.model_number or 'Standard'})"

    @property
    def manuals_count(self):
        """
        Returns number of associated manual documents.
        """
        if hasattr(self, 'documents'):
            return self.documents.count()
        return 0
