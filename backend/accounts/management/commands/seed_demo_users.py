"""
Idempotent Django management command to provision the three required demo accounts:
- Administrator: sarah.connor@gmail.com
- Engineer:      alex.vance@gmail.com
- Supervisor:    marcus.brody@gmail.com

Ensures correct roles, secure password hashing, active status, and active machine assignment
for the engineer account, while preserving existing records and database safety.
"""

import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserRole
from machines.models import Machine, MachineAssignment, MachineStatus


class Command(BaseCommand):
    help = "Idempotently provision the required Administrator, Engineer, and Supervisor demo accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force provisioning even if DEBUG is False.',
        )

    def handle(self, *args, **options):
        # Environment Safety Guard
        is_dev_or_demo = settings.DEBUG or os.getenv('ENVIRONMENT', 'development').lower() in ['development', 'demo', 'test']
        if not is_dev_or_demo and not options['force']:
            raise CommandError(
                "Demo account provisioning is restricted to development/demo environments. "
                "Set DEBUG=True or pass --force if you are certain this is intended."
            )

        demo_users_specs = [
            {
                'email': os.getenv('DEMO_ADMIN_EMAIL', 'sarah.connor@gmail.com').strip(),
                'password': os.getenv('DEMO_ADMIN_PASSWORD', 'Admin@123'),
                'role': UserRole.ADMIN,
                'first_name': 'Sarah',
                'last_name': 'Connor',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'email': os.getenv('DEMO_ENGINEER_EMAIL', 'alex.vance@gmail.com').strip(),
                'password': os.getenv('DEMO_ENGINEER_PASSWORD', 'Engineer@123'),
                'role': UserRole.ENGINEER,
                'first_name': 'Alex',
                'last_name': 'Vance',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'email': os.getenv('DEMO_SUPERVISOR_EMAIL', 'marcus.brody@gmail.com').strip(),
                'password': os.getenv('DEMO_SUPERVISOR_PASSWORD', 'Supervisor@123'),
                'role': UserRole.SUPERVISOR,
                'first_name': 'Marcus',
                'last_name': 'Brody',
                'is_staff': False,
                'is_superuser': False,
            },
        ]

        admin_instance = None
        engineer_instance = None

        self.stdout.write(self.style.NOTICE("Starting demo account provisioning..."))

        with transaction.atomic():
            for spec in demo_users_specs:
                email = spec['email']
                role = spec['role']
                password = spec['password']
                first_name = spec['first_name']
                last_name = spec['last_name']
                is_staff = spec['is_staff']
                is_superuser = spec['is_superuser']

                user = User.objects.filter(email__iexact=email).first()

                if user:
                    # Update existing record idempotently
                    user.role = role
                    user.first_name = first_name
                    user.last_name = last_name
                    user.is_active = True
                    user.is_staff = is_staff
                    user.is_superuser = is_superuser
                    user.set_password(password)  # Securely hashes with PBKDF2/SHA-256
                    user.save()
                    status_text = "Updated"
                else:
                    # Create new user record
                    user = User.objects.create(
                        email=email,
                        role=role,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=True,
                        is_staff=is_staff,
                        is_superuser=is_superuser,
                    )
                    user.set_password(password)  # Securely hashes with PBKDF2/SHA-256
                    user.save()
                    status_text = "Created"

                if role == UserRole.ADMIN:
                    admin_instance = user
                elif role == UserRole.ENGINEER:
                    engineer_instance = user

                # Output account status without ever logging passwords or sensitive tokens
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{status_text}] {user.email} | Role: {user.role} | Active: {user.is_active} | Staff: {user.is_staff}"
                    )
                )

            # Provision Machine Assignment for the Engineer
            if engineer_instance:
                # Find an active machine with uploaded manuals if possible
                target_machine = (
                    Machine.objects.filter(
                        machine_code='ABB-IRB-6700-01',
                        status=MachineStatus.ACTIVE
                    ).first()
                    or Machine.objects.filter(
                        status=MachineStatus.ACTIVE,
                        documents__isnull=False
                    ).distinct().first()
                    or Machine.objects.filter(
                        status=MachineStatus.ACTIVE
                    ).first()
                )

                if target_machine:
                    assignment, created = MachineAssignment.objects.update_or_create(
                        machine=target_machine,
                        user=engineer_instance,
                        defaults={
                            'is_active': True,
                            'assigned_by': admin_instance or engineer_instance,
                            'assigned_at': timezone.now(),
                        }
                    )
                    assign_status = "Assigned (New)" if created else "Assigned (Existing)"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{assign_status}] Engineer {engineer_instance.email} -> "
                            f"{target_machine.name} ({target_machine.machine_code})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "  [Warning] No active machine found in database to assign engineer. Demo machine should be created."
                        )
                    )

        self.stdout.write(self.style.NOTICE("Demo account provisioning complete."))
