"""
Serializers for Machine Management and Engineer Assignments.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import UserRole
from machines.models import Machine, MachineAssignment, MachineStatus

User = get_user_model()


class MachineListSerializer(serializers.ModelSerializer):
    """
    Compact serializer for listing machines.
    """

    class Meta:
        model = Machine
        fields = [
            'id',
            'machine_code',
            'name',
            'manufacturer',
            'model_number',
            'location',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class MachineDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for inspecting machine specifications and audit metadata.
    """
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    assigned_engineers_count = serializers.SerializerMethodField()

    class Meta:
        model = Machine
        fields = [
            'id',
            'machine_code',
            'name',
            'manufacturer',
            'model_number',
            'location',
            'description',
            'status',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_email',
            'assigned_engineers_count',
        ]
        read_only_fields = fields

    def get_assigned_engineers_count(self, obj) -> int:
        return obj.assignments.filter(is_active=True).count()


class MachineCreateSerializer(serializers.ModelSerializer):
    """
    Administrator serializer for registering new manufacturing machines.
    Enforces machine_code formatting, normalization, and uniqueness.
    """
    machine_code = serializers.CharField(
        max_length=50,
        required=True,
        help_text='Unique alphanumeric machine identifier (normalized to uppercase).'
    )
    name = serializers.CharField(max_length=255, required=True)
    status = serializers.ChoiceField(
        choices=MachineStatus.choices,
        default=MachineStatus.ACTIVE,
        required=False
    )

    class Meta:
        model = Machine
        fields = [
            'id',
            'machine_code',
            'name',
            'manufacturer',
            'model_number',
            'location',
            'description',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_machine_code(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("Machine code cannot be blank.")
        if Machine.objects.filter(machine_code=normalized).exists():
            raise serializers.ValidationError(f"Machine with code '{normalized}' already exists.")
        return normalized

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Machine name cannot be blank.")
        return value.strip()


class MachineUpdateSerializer(serializers.ModelSerializer):
    """
    Administrator serializer for updating existing machines.
    Machine code is immutable to preserve document, citation, and RAG integrity.
    """
    status = serializers.ChoiceField(choices=MachineStatus.choices, required=False)

    class Meta:
        model = Machine
        fields = [
            'id',
            'machine_code',
            'name',
            'manufacturer',
            'model_number',
            'location',
            'description',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'machine_code', 'created_at', 'updated_at']

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Machine name cannot be blank.")
        return value.strip()


class AssignmentUserSummarySerializer(serializers.ModelSerializer):
    """
    Compact user representation embedded in assignment responses.
    """

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role']
        read_only_fields = fields


class MachineAssignmentSerializer(serializers.ModelSerializer):
    """
    Read serializer for machine engineer assignments.
    """
    machine_id = serializers.UUIDField(source='machine.id', read_only=True)
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    user = AssignmentUserSummarySerializer(read_only=True)
    assigned_by_email = serializers.EmailField(source='assigned_by.email', read_only=True)

    class Meta:
        model = MachineAssignment
        fields = [
            'id',
            'machine_id',
            'machine_code',
            'machine_name',
            'user',
            'assigned_by',
            'assigned_by_email',
            'assigned_at',
            'is_active',
        ]
        read_only_fields = fields


class MachineAssignmentCreateSerializer(serializers.Serializer):
    """
    Input serializer for assigning an engineer to a machine.
    """
    user_id = serializers.IntegerField(
        required=True,
        help_text='User ID of the active Engineer to assign.'
    )

    def validate_user_id(self, value):
        try:
            target_user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        if not target_user.is_active:
            raise serializers.ValidationError("Cannot assign an inactive user.")

        if target_user.role != UserRole.ENGINEER:
            raise serializers.ValidationError("Only users with the ENGINEER role can be assigned to machines.")

        return value
