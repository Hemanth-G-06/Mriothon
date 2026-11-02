"""
Service layer for Machine Management and machine-level authorization.
Reusable across Documents, RAG retrieval, Query History, and Supervisor monitoring modules.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import UserRole
from machines.models import Machine, MachineAssignment, MachineStatus


def can_user_access_machine(user, machine) -> bool:
    """
    Determines if a user has permission to view or query a machine and its manuals.

    - Administrator: Full access to all machines.
    - Supervisor: Full read-only access to all machines.
    - Engineer: Access restricted to actively assigned, active machines.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return False

    if user.role == UserRole.ADMIN or user.role == UserRole.SUPERVISOR or user.is_superuser:
        return True

    if user.role == UserRole.ENGINEER:
        if not machine.is_active:
            return False
        return MachineAssignment.objects.filter(
            machine=machine,
            user=user,
            is_active=True
        ).exists()

    return False


def get_accessible_machines_queryset(user):
    """
    Returns a filtered Machine QuerySet based on user role and assignments.

    - Administrator: All machines.
    - Supervisor: All machines.
    - Engineer: Only assigned, active machines.
    - Inactive / Unauthenticated: Empty queryset.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return Machine.objects.none()

    if user.role in [UserRole.ADMIN, UserRole.SUPERVISOR] or user.is_superuser:
        return Machine.objects.all()

    if user.role == UserRole.ENGINEER:
        return Machine.objects.filter(
            assignments__user=user,
            assignments__is_active=True,
            status=MachineStatus.ACTIVE
        ).distinct()

    return Machine.objects.none()


def assign_engineer_to_machine(machine: Machine, engineer_user, assigned_by_user) -> MachineAssignment:
    """
    Assigns an engineer to a machine.
    Enforces business validation:
    - Machine must be ACTIVE.
    - Target user must be ACTIVE and have the ENGINEER role.
    - Prevents conflicting active duplicate records (reactivates historical record if present).
    """
    if not machine.is_active:
        raise ValidationError({"detail": "Cannot assign engineers to an inactive machine."})

    if not engineer_user.is_active:
        raise ValidationError({"detail": "Cannot assign an inactive user."})

    if engineer_user.role != UserRole.ENGINEER:
        raise ValidationError({"detail": "Only users with the ENGINEER role can be assigned to machines."})

    # Check for existing active assignment
    existing_active = MachineAssignment.objects.filter(
        machine=machine,
        user=engineer_user,
        is_active=True
    ).first()

    if existing_active:
        raise ValidationError({"detail": "Engineer is already actively assigned to this machine."})

    # Check for historical deactivated assignment to reactivate cleanly
    historical_assignment = MachineAssignment.objects.filter(
        machine=machine,
        user=engineer_user,
        is_active=False
    ).first()

    if historical_assignment:
        historical_assignment.is_active = True
        historical_assignment.assigned_by = assigned_by_user
        historical_assignment.assigned_at = timezone.now()
        historical_assignment.save(update_fields=['is_active', 'assigned_by', 'assigned_at'])
        return historical_assignment

    # Create new assignment record
    return MachineAssignment.objects.create(
        machine=machine,
        user=engineer_user,
        assigned_by=assigned_by_user,
        is_active=True
    )


def unassign_engineer_from_machine(machine: Machine, assignment_id: int) -> MachineAssignment:
    """
    Deactivates an engineer assignment from a machine (soft-unassign).
    Preserves audit and assignment history.
    """
    try:
        assignment = MachineAssignment.objects.get(id=assignment_id, machine=machine)
    except MachineAssignment.DoesNotExist:
        raise ValidationError({"detail": "Assignment does not exist for this machine."})

    if not assignment.is_active:
        raise ValidationError({"detail": "Assignment is already inactive."})

    assignment.is_active = False
    assignment.save(update_fields=['is_active'])
    return assignment

