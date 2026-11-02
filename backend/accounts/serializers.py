"""
Serializers for authentication, profile management, and administrator user provisioning.
Email is the sole authentication and user identifier (username removed).
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User, UserRole


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT Token serializer using email as the sole authentication identifier.
    Returns JWT access & refresh tokens along with core user profile details.
    """
    username_field = 'email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Custom claims embedded into JWT payload
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.full_name
        return token

    def validate(self, attrs):
        if 'email' in attrs and isinstance(attrs['email'], str):
            attrs['email'] = attrs['email'].strip().lower()

        # Authenticates user and verifies account active status
        data = super().validate(attrs)

        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
        }
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for public/authenticated user profile views (/api/auth/me/).
    Excludes sensitive fields and internal flags.
    """

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'date_joined',
        ]
        read_only_fields = fields


class UserAdminCreateSerializer(serializers.ModelSerializer):
    """
    Administrator-only serializer for creating new application users.
    Enforces password validation, hashing, and role validation.
    Explicitly ignores is_staff/is_superuser to prevent privilege escalation.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='User password satisfying standard complexity rules.'
    )
    role = serializers.ChoiceField(
        choices=UserRole.choices,
        default=UserRole.ENGINEER,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'password',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def validate_password(self, value):
        """Validate password complexity against Django password validators."""
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        """Securely create user using UserManager.create_user with password hashing."""
        # Strip potential privilege escalation flags
        validated_data.pop('is_staff', None)
        validated_data.pop('is_superuser', None)

        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    """
    Administrator-only serializer for updating existing application users.
    Guards against accidental deactivation or demotion of the last active Administrator.
    """
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'date_joined',
        ]
        read_only_fields = ['id', 'email', 'date_joined']

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.role == UserRole.ADMIN and instance.is_active:
            target_is_active = attrs.get('is_active', instance.is_active)
            target_role = attrs.get('role', instance.role)

            is_deactivating = target_is_active is False
            is_demoting = target_role != UserRole.ADMIN

            if is_deactivating or is_demoting:
                other_active_admins = User.objects.filter(
                    role=UserRole.ADMIN,
                    is_active=True
                ).exclude(pk=instance.pk)

                if not other_active_admins.exists():
                    action = "deactivate" if is_deactivating else "demote"
                    raise serializers.ValidationError({
                        "detail": f"Cannot {action} the last active Administrator."
                    })

        return attrs
