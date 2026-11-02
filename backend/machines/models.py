"""
Machine and MachineAssignment models for the Manufacturing Manual Assistant.
Provides machine registration, metadata, and engineer assignment access control.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class MachineStatus(models.TextChoices):
    """
    Operational status of a machine.
    """
    ACTIVE = 'ACTIVE', _('Active')
    INACTIVE = 'INACTIVE', _('Inactive')


class Machine(models.Model):
    """
    Represents a manufacturing machine in the facility.
    Primary key is a UUID to avoid predictable enumeration.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique machine UUID primary identifier.')
    )
    machine_code = models.CharField(
        _('machine code'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Unique normalized machine code (e.g. CNC-MILL-01).')
    )
    name = models.CharField(_('machine name'), max_length=255)
    manufacturer = models.CharField(_('manufacturer'), max_length=255, blank=True)
    model_number = models.CharField(_('model number'), max_length=100, blank=True)
    location = models.CharField(
        _('location'),
        max_length=255,
        blank=True,
        help_text=_('Physical location, shop floor, or production line.')
    )
    description = models.TextField(_('description'), blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=MachineStatus.choices,
        default=MachineStatus.ACTIVE,
        db_index=True,
        help_text=_('Operational status: ACTIVE or INACTIVE.')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_machines',
        verbose_name=_('created by')
    )

    class Meta:
        db_table = 'machines'
        verbose_name = _('machine')
        verbose_name_plural = _('machines')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.machine_code} - {self.name}"

    def save(self, *args, **kwargs):
        if self.machine_code:
            self.machine_code = self.machine_code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == MachineStatus.ACTIVE


class MachineAssignment(models.Model):
    """
    Associates an Engineer with a specific Machine.
    Controls engineer-level access for manual retrieval and RAG question answering.
    """
    id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_('machine')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='machine_assignments',
        verbose_name=_('assigned engineer')
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_machines_by',
        verbose_name=_('assigned by')
    )
    assigned_at = models.DateTimeField(_('assigned at'), auto_now_add=True)
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        db_index=True,
        help_text=_('Indicates whether this engineer assignment is currently active.')
    )

    class Meta:
        db_table = 'machine_assignments'
        verbose_name = _('machine assignment')
        verbose_name_plural = _('machine assignments')
        ordering = ['-assigned_at']
        constraints = [
            models.UniqueConstraint(
                fields=['machine', 'user'],
                condition=models.Q(is_active=True),
                name='unique_active_machine_assignment'
            )
        ]

    def __str__(self):
        status_label = "Active" if self.is_active else "Inactive"
        return f"{self.user.email} -> {self.machine.machine_code} [{status_label}]"
