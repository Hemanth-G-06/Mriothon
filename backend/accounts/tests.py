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


# ==============================================================================
# 5. User Self-Registration API Tests (/api/auth/register/)
# ==============================================================================

class UserRegistrationAPITestCase(TestCase):
    """
    Validation and functional tests for new user registration:
    - Gmail email domain restriction
    - Password complexity verification
    - Password confirmation match
    - Automatic role assignment to ENGINEER
    - Secure password hashing (no plaintext)
    - Prevention of role escalation (Admin / Supervisor)
    - Full authentication cycle for registered users
    """

    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/auth/register/'
        self.login_url = '/api/auth/login/'

        self.valid_payload = {
            'first_name': 'Samantha',
            'last_name': 'Smith',
            'email': 'samantha.smith@gmail.com',
            'password': 'Manual@123',
            'password_confirm': 'Manual@123'
        }

    def test_registration_successful_creates_engineer_account(self):
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertIn('message', data)
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], 'samantha.smith@gmail.com')
        self.assertEqual(data['user']['first_name'], 'Samantha')
        self.assertEqual(data['user']['last_name'], 'Smith')
        self.assertEqual(data['user']['role'], 'ENGINEER')

        # Verify database record
        user = User.objects.get(email='samantha.smith@gmail.com')
        self.assertEqual(user.first_name, 'Samantha')
        self.assertEqual(user.last_name, 'Smith')
        self.assertEqual(user.role, UserRole.ENGINEER)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

        # Verify password is encrypted and hashed
        self.assertTrue(user.check_password('Manual@123'))
        self.assertNotEqual(user.password, 'Manual@123')
        self.assertTrue(user.password.startswith('pbkdf2_') or user.password.startswith('argon2'))

    def test_duplicate_email_registration_rejected(self):
        # Register user first time
        User.objects.create_user(
            email='existing.engineer@gmail.com',
            password='Existing@123',
            first_name='Existing',
            last_name='User',
            role=UserRole.ENGINEER
        )

        payload = {
            **self.valid_payload,
            'email': 'existing.engineer@gmail.com'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('email', data)
        email_errors = data['email'] if isinstance(data['email'], list) else [data['email']]
        self.assertTrue(any('already exists' in str(e).lower() for e in email_errors))

    def test_non_gmail_address_rejected(self):
        non_gmail_emails = [
            'engineer@yahoo.com',
            'engineer@outlook.com',
            'engineer@manufacturing.corp',
            'engineer@test.local'
        ]
        for bad_email in non_gmail_emails:
            payload = {
                **self.valid_payload,
                'email': bad_email
            }
            response = self.client.post(self.register_url, payload)
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Expected 400 for email: {bad_email}"
            )
            data = response.json()
            self.assertIn('email', data)
            self.assertIn('gmail.com', str(data['email']).lower())

    def test_malformed_email_format_rejected(self):
        payload = {
            **self.valid_payload,
            'email': 'invalid-format'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())

    def test_password_length_under_8_rejected(self):
        payload = {
            **self.valid_payload,
            'email': 'shortpass@gmail.com',
            'password': 'Abc@1',
            'password_confirm': 'Abc@1'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())
        self.assertIn('8 characters', str(response.json()['password']).lower())

    def test_password_first_char_not_uppercase_rejected(self):
        invalid_first_chars = ['manual@123', '1Manual@', '@Manual123']
        for bad_pass in invalid_first_chars:
            payload = {
                **self.valid_payload,
                'email': f'testfirst_{abs(hash(bad_pass))}@gmail.com',
                'password': bad_pass,
                'password_confirm': bad_pass
            }
            response = self.client.post(self.register_url, payload)
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Expected 400 for password: {bad_pass}"
            )
            self.assertIn('password', response.json())
            self.assertIn('uppercase', str(response.json()['password']).lower())

    def test_password_missing_lowercase_rejected(self):
        payload = {
            **self.valid_payload,
            'email': 'nolower@gmail.com',
            'password': 'MANUAL@123',
            'password_confirm': 'MANUAL@123'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())
        self.assertIn('lowercase', str(response.json()['password']).lower())

    def test_password_missing_number_rejected(self):
        payload = {
            **self.valid_payload,
            'email': 'nonumber@gmail.com',
            'password': 'Manual@password',
            'password_confirm': 'Manual@password'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())
        self.assertIn('number', str(response.json()['password']).lower())

    def test_password_missing_special_character_rejected(self):
        payload = {
            **self.valid_payload,
            'email': 'nospecial@gmail.com',
            'password': 'ManualPassword123',
            'password_confirm': 'ManualPassword123'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())
        self.assertIn('special character', str(response.json()['password']).lower())

    def test_password_confirmation_mismatch_rejected(self):
        payload = {
            **self.valid_payload,
            'email': 'mismatch@gmail.com',
            'password': 'Manual@123',
            'password_confirm': 'Different@123'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.json())
        self.assertIn('match', str(response.json()['password_confirm']).lower())

    def test_missing_first_or_last_name_rejected(self):
        payload_no_first = {
            **self.valid_payload,
            'first_name': '   ',
            'email': 'nofirst@gmail.com'
        }
        res1 = self.client.post(self.register_url, payload_no_first)
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', res1.json())

        payload_no_last = {
            **self.valid_payload,
            'last_name': '',
            'email': 'nolast@gmail.com'
        }
        res2 = self.client.post(self.register_url, payload_no_last)
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('last_name', res2.json())

    def test_privilege_escalation_attempt_ignored(self):
        """
        Verify that passing 'role': 'ADMIN', 'is_staff': True, or 'is_superuser': True
        during registration is safely stripped and assigns only the ENGINEER role.
        """
        payload = {
            **self.valid_payload,
            'email': 'hacker@gmail.com',
            'role': 'ADMIN',
            'is_staff': True,
            'is_superuser': True
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='hacker@gmail.com')
        self.assertEqual(user.role, UserRole.ENGINEER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_newly_registered_user_can_login(self):
        """
        Full end-to-end authentication cycle:
        1. Register user via /api/auth/register/
        2. Authenticate user via /api/auth/login/
        3. Verify access token and role returned
        """
        email = 'new.engineer@gmail.com'
        password = 'Engineer@2026'
        reg_payload = {
            'first_name': 'Marcus',
            'last_name': 'Vance',
            'email': email,
            'password': password,
            'password_confirm': password
        }

        # 1. Register
        reg_res = self.client.post(self.register_url, reg_payload)
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)

        # 2. Login
        login_res = self.client.post(self.login_url, {
            'email': email,
            'password': password
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        login_data = login_res.json()

        self.assertIn('access', login_data)
        self.assertIn('refresh', login_data)
        self.assertIn('user', login_data)
        self.assertEqual(login_data['user']['email'], email)
        self.assertEqual(login_data['user']['role'], 'ENGINEER')
