"""
Custom User and Role models for the Manufacturing Manual Assistant.
Email is the sole authentication identifier (username removed entirely).
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.managers import UserManager


class UserRole(models.TextChoices):
    """
    Application roles for Role-Based Access Control (RBAC).

    - ADMIN: Manage users, machines, and uploaded manuals.
    - ENGINEER: Access assigned machines, query manuals, view personal history.
    - SUPERVISOR: Monitor engineer activity, access aggregate query history.
    """
    ADMIN = 'ADMIN', _('Administrator')
    ENGINEER = 'ENGINEER', _('Engineer')
    SUPERVISOR = 'SUPERVISOR', _('Supervisor')


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model using email as the sole authentication identifier.
    Completely decoupled from username.
    """
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(
        _('email address'),
        unique=True,
        max_length=255,
        db_index=True,
        error_messages={
            'unique': _('A user with that email address already exists.'),
        },
    )
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    role = models.CharField(
        _('application role'),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.ENGINEER,
        db_index=True,
        help_text=_('Designates application-level access permissions.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of physically deleting accounts.'
        ),
    )
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def full_name(self):
        """Return the user's full name, or their email if blank."""
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.email

    @property
    def is_admin_role(self):
        """Check if user has application Administrator privileges."""
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_engineer_role(self):
        """Check if user has application Engineer privileges."""
        return self.role == UserRole.ENGINEER

    @property
    def is_supervisor_role(self):
        """Check if user has application Supervisor privileges."""
        return self.role == UserRole.SUPERVISOR
