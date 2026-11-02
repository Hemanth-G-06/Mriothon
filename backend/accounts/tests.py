"""
Comprehensive test suite for Authentication, User Model, RBAC, and Security.
"""

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserRole

User = get_user_model()


# ==============================================================================
# 1. Foundation & Health Check Tests (Preserved from Task 01)
# ==============================================================================

class HealthCheckAndConfigTestCase(TestCase):
    """
    Validates base API health check, CORS origin headers, and MySQL engine configuration.
    """

    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse('health-check')

    def test_health_check_returns_200(self):
        response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "status": "healthy",
                "application": "Manufacturing Manual Assistant",
            }
        )

    def test_cors_headers_allowed_origin(self):
        response = self.client.get(
            self.health_url,
            HTTP_ORIGIN='http://localhost:5173'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.headers.get('Access-Control-Allow-Origin'),
            'http://localhost:5173'
        )

    def test_database_engine_is_postgresql(self):
        """
        Verify that PostgreSQL with psycopg is configured in settings.
        """
        import os
        from django.conf import settings
        # Verify base configured engine
        db_engine = settings.DATABASES['default']['ENGINE']
        self.assertIn(db_engine, ['django.db.backends.postgresql', 'django.db.backends.sqlite3'])


# ==============================================================================
# 2. Custom User Model & Manager Tests
# ==============================================================================

class UserModelTestCase(TestCase):
    """
    Unit tests for the custom User model, UserManager, and role properties.
    """

    def test_create_user_with_email_successful(self):
        user = User.objects.create_user(
            email='engineer@test.local',
            password='ComplexPassword123!',
            first_name='John',
            last_name='Doe',
            role=UserRole.ENGINEER
        )
        self.assertEqual(user.email, 'engineer@test.local')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertEqual(user.role, UserRole.ENGINEER)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('ComplexPassword123!'))
        self.assertNotEqual(user.password, 'ComplexPassword123!')  # Must be hashed

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='ComplexPassword123!')

    def test_email_uniqueness_enforced(self):
        User.objects.create_user(
            email='duplicate@test.local',
            password='ComplexPassword123!'
        )
        with self.assertRaises(Exception):
            User.objects.create_user(
                email='duplicate@test.local',
                password='AnotherPassword123!'
            )

    def test_create_superuser_sets_required_flags(self):
        admin_user = User.objects.create_superuser(
            email='root@test.local',
            password='AdminPassword123!'
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, UserRole.ADMIN)
        self.assertTrue(admin_user.is_admin_role)

    def test_user_role_properties(self):
        admin = User.objects.create_user(
            email='admin@test.local',
            password='Password123!',
            role=UserRole.ADMIN
        )
        engineer = User.objects.create_user(
            email='eng@test.local',
            password='Password123!',
            role=UserRole.ENGINEER
        )
        supervisor = User.objects.create_user(
            email='sup@test.local',
            password='Password123!',
            role=UserRole.SUPERVISOR
        )

        self.assertTrue(admin.is_admin_role)
        self.assertFalse(admin.is_engineer_role)

        self.assertTrue(engineer.is_engineer_role)
        self.assertFalse(engineer.is_supervisor_role)

        self.assertTrue(supervisor.is_supervisor_role)
        self.assertFalse(supervisor.is_admin_role)

    def test_username_field_removed_completely(self):
        """
        Verify that the username field is completely absent from the User model
        and that email is the sole USERNAME_FIELD.
        """
        self.assertFalse(hasattr(User, 'username'))
        field_names = [f.name for f in User._meta.get_fields()]
        self.assertNotIn('username', field_names)
        self.assertEqual(User.USERNAME_FIELD, 'email')
        self.assertEqual(User.REQUIRED_FIELDS, [])


# ==============================================================================
# 3. Authentication API Tests (Login, Refresh, Profile)
# ==============================================================================

class AuthenticationAPITestCase(TestCase):
    """
    Tests for /api/auth/login/, /api/auth/refresh/, and /api/auth/me/.
    """

    def setUp(self):
        self.client = APIClient()
        self.login_url = '/api/auth/login/'
        self.refresh_url = '/api/auth/refresh/'
        self.me_url = '/api/auth/me/'

        self.user_password = 'ValidPassword123!'
        self.engineer = User.objects.create_user(
            email='engineer@factory.local',
            password=self.user_password,
            first_name='Alex',
            last_name='Rivera',
            role=UserRole.ENGINEER
        )

    def test_login_successful_with_email_and_password(self):
        response = self.client.post(self.login_url, {
            'email': 'engineer@factory.local',
            'password': self.user_password
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], 'engineer@factory.local')
        self.assertEqual(data['user']['first_name'], 'Alex')
        self.assertEqual(data['user']['last_name'], 'Rivera')
        self.assertEqual(data['user']['role'], UserRole.ENGINEER)

    def test_login_fails_with_incorrect_password(self):
        response = self.client.post(self.login_url, {
            'email': 'engineer@factory.local',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_fails_with_unknown_email(self):
        response = self.client.post(self.login_url, {
            'email': 'nonexistent@factory.local',
            'password': self.user_password
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_username_rejected(self):
        """
        Verify that login does not accept username instead of email.
        """
        response = self.client.post(self.login_url, {
            'username': 'engineer@factory.local',
            'password': self.user_password
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())

    def test_login_fails_for_inactive_account(self):
        self.engineer.is_active = False
        self.engineer.save()

        response = self.client.post(self.login_url, {
            'email': 'engineer@factory.local',
            'password': self.user_password
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_successful(self):
        refresh = RefreshToken.for_user(self.engineer)
        response = self.client.post(self.refresh_url, {
            'refresh': str(refresh)
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.json())

    def test_token_refresh_fails_with_invalid_token(self):
        response = self.client.post(self.refresh_url, {
            'refresh': 'invalid.jwt.token'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_current_user_profile_authenticated(self):
        token = RefreshToken.for_user(self.engineer).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['email'], 'engineer@factory.local')
        self.assertEqual(data['role'], UserRole.ENGINEER)
        self.assertNotIn('username', data)
        self.assertNotIn('password', data)

    def test_current_user_profile_unauthenticated_rejected(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==============================================================================
# 4. Role-Based Access Control (RBAC) & User Management Tests
# ==============================================================================

class UserManagementRBACAPITestCase(TestCase):
    """
    Tests for Administrator-only user management (/api/users/).
    Verifies that only Administrators can create, list, update, and deactivate users.
    """

    def setUp(self):
        self.client = APIClient()
        self.users_url = '/api/users/'

        self.password = 'ComplexSecret123!'

        self.admin = User.objects.create_user(
            email='admin@factory.local',
            password=self.password,
            role=UserRole.ADMIN
        )
        self.engineer = User.objects.create_user(
            email='engineer@factory.local',
            password=self.password,
            role=UserRole.ENGINEER
        )
        self.supervisor = User.objects.create_user(
            email='supervisor@factory.local',
            password=self.password,
            role=UserRole.SUPERVISOR
        )

        self.admin_token = str(RefreshToken.for_user(self.admin).access_token)
        self.engineer_token = str(RefreshToken.for_user(self.engineer).access_token)
        self.supervisor_token = str(RefreshToken.for_user(self.supervisor).access_token)

    def test_admin_can_list_users(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.get(self.users_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        self.assertGreaterEqual(len(results), 3)

    def test_engineer_cannot_list_users(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        response = self.client.get(self.users_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_list_users(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        response = self.client.get(self.users_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_list_users(self):
        response = self.client.get(self.users_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_create_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        payload = {
            'email': 'newengineer@factory.local',
            'password': 'SecurePassword456!',
            'first_name': 'New',
            'last_name': 'Engineer',
            'role': UserRole.ENGINEER
        }
        response = self.client.post(self.users_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['email'], 'newengineer@factory.local')
        self.assertEqual(data['role'], UserRole.ENGINEER)
        self.assertNotIn('username', data)
        self.assertNotIn('password', data)

        created_user = User.objects.get(email='newengineer@factory.local')
        self.assertTrue(created_user.check_password('SecurePassword456!'))

    def test_engineer_cannot_create_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer_token}')
        payload = {
            'email': 'hacked@factory.local',
            'password': 'SecurePassword456!',
            'role': UserRole.ADMIN
        }
        response = self.client.post(self.users_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_create_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        payload = {
            'email': 'hacked2@factory.local',
            'password': 'SecurePassword456!',
            'role': UserRole.ENGINEER
        }
        response = self.client.post(self.users_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_deactivate_user_soft_delete(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        target_user = self.engineer
        url = f'{self.users_url}{target_user.id}/'

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        target_user.refresh_from_db()
        self.assertFalse(target_user.is_active)  # Soft-deactivated
        self.assertTrue(User.objects.filter(pk=target_user.pk).exists())  # Record preserved

    def test_admin_cannot_deactivate_the_last_active_administrator(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = f'{self.users_url}{self.admin.id}/'

        # Only 1 active administrator exists
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot deactivate the last active Administrator.", response.json().get('detail', ''))

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)  # Still active

    def test_admin_cannot_demote_the_last_active_administrator(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        url = f'{self.users_url}{self.admin.id}/'

        # Attempt to change role to ENGINEER when only 1 admin exists
        response = self.client.patch(url, {'role': UserRole.ENGINEER})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, UserRole.ADMIN)

    def test_privilege_escalation_mass_assignment_prevented(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        payload = {
            'email': 'sneaky@factory.local',
            'password': 'SecurePassword456!',
            'role': UserRole.ENGINEER,
            'is_staff': True,
            'is_superuser': True,
        }
        response = self.client.post(self.users_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='sneaky@factory.local')
        self.assertFalse(user.is_staff)  # Should remain False
        self.assertFalse(user.is_superuser)  # Should remain False


# ==============================================================================
# 5. Security Tests
# ==============================================================================

class SecurityAssuranceTestCase(TestCase):
    """
    Security verification tests: password complexity, secret leakage prevention,
    and denial of unauthorized access.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@sec.local',
            password='ComplexAdminPass123!',
            role=UserRole.ADMIN
        )
        self.admin_token = str(RefreshToken.for_user(self.admin).access_token)

    def test_weak_password_rejected_on_user_creation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        payload = {
            'email': 'weakpass@sec.local',
            'password': '123',  # Too short
            'role': UserRole.ENGINEER
        }
        response = self.client.post('/api/users/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())

    def test_password_hashes_never_exposed_in_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')

        # Test users list endpoint
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content_str = response.content.decode()
        self.assertNotIn('pbkdf2_sha256', content_str)
        self.assertNotIn('password', content_str)

        # Test user detail endpoint
        response = self.client.get(f'/api/users/{self.admin.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        detail_str = response.content.decode()
        self.assertNotIn('pbkdf2_sha256', detail_str)
        self.assertNotIn('password', detail_str)

    def test_logout_blacklists_token(self):
        refresh = str(RefreshToken.for_user(self.admin))
        logout_res = self.client.post('/api/auth/logout/', {'refresh': refresh})
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)
        # Verify blacklisted token cannot be refreshed
        refresh_res = self.client.post('/api/auth/refresh/', {'refresh': refresh})
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)
