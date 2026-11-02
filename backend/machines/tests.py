"""
Comprehensive automated test suite for Machine Management and Access Control (Task 03).
Covers Machine CRUD, Role-Based Access Control, and Engineer Assignments.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User, UserRole
from machines.models import Machine
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserRole
from machines.models import Machine, MachineAssignment, MachineStatus
from machines.services import (
    assign_engineer_to_machine,
    can_user_access_machine,
    get_accessible_machines_queryset,
    unassign_engineer_from_machine,
)

class MachineAPITestCase(TestCase):
    """
    Test suite for Machine list, retrieve, and RBAC creation.
    """

    def setUp(self):
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            email='admin@plantops.com',
            password='AdminPassword@123',
            role=UserRole.ADMIN
        )
        self.engineer_user = User.objects.create_user(
            email='engineer@plantops.com',
            password='EngineerPassword@123',
            role=UserRole.ENGINEER
        )

        self.machine1 = Machine.objects.create(
            name='Test Lathe A',
            model_number='TL-100',
            serial_number='SN-001',
            location='Floor 1'
        )

    def test_authenticated_user_can_list_machines(self):
        self.client.force_authenticate(user=self.engineer_user)
        response = self.client.get('/api/machines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Lathe A')

    def test_admin_can_create_machine(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'name': 'Milling Machine M2',
            'model_number': 'MM-200',
            'serial_number': 'SN-002',
            'location': 'Bay 3',
            'description': 'Heavy duty CNC milling machine'
        }
        response = self.client.post('/api/machines/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Machine.objects.count(), 2)

    def test_engineer_cannot_create_machine(self):
        self.client.force_authenticate(user=self.engineer_user)
        payload = {'name': 'Unauthorized Lathe'}
        response = self.client.post('/api/machines/', payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
User = get_user_model()


class BaseMachineTestCase(TestCase):
    """
    Common setup fixture providing Admin, Engineer, and Supervisor users.
    """

    def setUp(self):
        self.client = APIClient()

        self.password = 'ComplexSecret123!'

        self.admin = User.objects.create_user(
            email='admin@machines.local',
            password=self.password,
            first_name='Admin',
            last_name='User',
            role=UserRole.ADMIN
        )
        self.supervisor = User.objects.create_user(
            email='supervisor@machines.local',
            password=self.password,
            first_name='Supervisor',
            last_name='User',
            role=UserRole.SUPERVISOR
        )
        self.engineer1 = User.objects.create_user(
            email='engineer1@machines.local',
            password=self.password,
            first_name='Engineer',
            last_name='One',
            role=UserRole.ENGINEER
        )
        self.engineer2 = User.objects.create_user(
            email='engineer2@machines.local',
            password=self.password,
            first_name='Engineer',
            last_name='Two',
            role=UserRole.ENGINEER
        )

        self.admin_token = str(RefreshToken.for_user(self.admin).access_token)
        self.supervisor_token = str(RefreshToken.for_user(self.supervisor).access_token)
        self.engineer1_token = str(RefreshToken.for_user(self.engineer1).access_token)
        self.engineer2_token = str(RefreshToken.for_user(self.engineer2).access_token)

        self.machines_url = '/api/machines/'


# ==============================================================================
# 1. Machine CRUD API Tests
# ==============================================================================

class MachineCRUDAPITestCase(BaseMachineTestCase):
    """
    Tests for registering, retrieving, updating, and deactivating machines.
    """

    def test_admin_can_register_machine(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        payload = {
            'machine_code': 'cnc-01',  # lowercase to verify normalization
            'name': '5-Axis CNC Milling Center',
            'manufacturer': 'DMG MORI',
            'model_number': 'DMU 50',
            'location': 'Building B, Bay 4',
            'description': 'High precision milling center',
            'status': MachineStatus.ACTIVE
        }
        response = self.client.post(self.machines_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data['machine_code'], 'CNC-01')  # Normalized to uppercase
        self.assertEqual(data['name'], '5-Axis CNC Milling Center')
        self.assertEqual(data['manufacturer'], 'DMG MORI')
        self.assertEqual(data['status'], MachineStatus.ACTIVE)

        machine = Machine.objects.get(machine_code='CNC-01')
        self.assertEqual(machine.created_by, self.admin)
        self.assertTrue(isinstance(machine.id, uuid.UUID))

    def test_duplicate_machine_code_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        Machine.objects.create(
            machine_code='LATHE-01',
            name='Precision Lathe',
            created_by=self.admin
        )
        payload = {
            'machine_code': 'lathe-01',  # duplicate code
            'name': 'Duplicate Lathe',
        }
        response = self.client.post(self.machines_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('machine_code', response.json())

    def test_admin_can_retrieve_machine_details(self):
        machine = Machine.objects.create(
            machine_code='ROBOT-01',
            name='KUKA Assembly Robot',
            created_by=self.admin
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.get(f'{self.machines_url}{machine.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['id'], str(machine.id))
        self.assertEqual(data['machine_code'], 'ROBOT-01')
        self.assertEqual(data['created_by_email'], self.admin.email)

    def test_admin_can_update_machine_details(self):
        machine = Machine.objects.create(
            machine_code='PRESS-01',
            name='Hydraulic Press 100T',
            created_by=self.admin
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        payload = {
            'name': 'Hydraulic Press 120T Upgraded',
            'location': 'Shop Floor 2',
            'machine_code': 'HACKED-CODE'  # should be ignored (immutable)
        }
        response = self.client.patch(f'{self.machines_url}{machine.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        machine.refresh_from_db()
        self.assertEqual(machine.name, 'Hydraulic Press 120T Upgraded')
        self.assertEqual(machine.location, 'Shop Floor 2')
        self.assertEqual(machine.machine_code, 'PRESS-01')  # Unaltered

    def test_admin_can_deactivate_machine_soft_delete(self):
        machine = Machine.objects.create(
            machine_code='GRIND-01',
            name='Surface Grinder',
            created_by=self.admin,
            status=MachineStatus.ACTIVE
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.delete(f'{self.machines_url}{machine.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        machine.refresh_from_db()
        self.assertEqual(machine.status, MachineStatus.INACTIVE)
        self.assertFalse(machine.is_active)
        self.assertTrue(Machine.objects.filter(pk=machine.pk).exists())  # Record preserved

    def test_supervisor_cannot_create_update_or_deactivate_machine(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        machine = Machine.objects.create(
            machine_code='WELD-01',
            name='Laser Welder',
            created_by=self.admin
        )

        # Create
        res_create = self.client.post(self.machines_url, {'machine_code': 'NEW', 'name': 'New'})
        self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

        # Update
        res_update = self.client.patch(f'{self.machines_url}{machine.id}/', {'name': 'Hacked'})
        self.assertEqual(res_update.status_code, status.HTTP_403_FORBIDDEN)

        # Delete
        res_delete = self.client.delete(f'{self.machines_url}{machine.id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_cannot_create_update_or_deactivate_machine(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        machine = Machine.objects.create(
            machine_code='DRILL-01',
            name='Radial Drill',
            created_by=self.admin
        )

        res_create = self.client.post(self.machines_url, {'machine_code': 'NEW', 'name': 'New'})
        self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

        res_update = self.client.patch(f'{self.machines_url}{machine.id}/', {'name': 'Hacked'})
        self.assertEqual(res_update.status_code, status.HTTP_403_FORBIDDEN)

        res_delete = self.client.delete(f'{self.machines_url}{machine.id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_403_FORBIDDEN)


# ==============================================================================
# 2. Role-Based Access Control & Visibility Tests
# ==============================================================================

class MachineAccessControlTestCase(BaseMachineTestCase):
    """
    Tests enforcing machine visibility:
    - Admin: All machines.
    - Supervisor: All machines (read-only).
    - Engineer: ONLY assigned active machines.
    """

    def setUp(self):
        super().setUp()
        self.machine_assigned = Machine.objects.create(
            machine_code='ASSIGNED-01',
            name='Assigned Machine',
            status=MachineStatus.ACTIVE,
            created_by=self.admin
        )
        self.machine_unassigned = Machine.objects.create(
            machine_code='UNASSIGNED-01',
            name='Unassigned Machine',
            status=MachineStatus.ACTIVE,
            created_by=self.admin
        )
        self.machine_inactive_assigned = Machine.objects.create(
            machine_code='INACTIVE-01',
            name='Inactive Machine',
            status=MachineStatus.INACTIVE,
            created_by=self.admin
        )

        # Assign engineer1 to machine_assigned and machine_inactive_assigned
        MachineAssignment.objects.create(
            machine=self.machine_assigned,
            user=self.engineer1,
            assigned_by=self.admin,
            is_active=True
        )
        MachineAssignment.objects.create(
            machine=self.machine_inactive_assigned,
            user=self.engineer1,
            assigned_by=self.admin,
            is_active=True
        )

    def test_admin_sees_all_machines(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.get(self.machines_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [m['machine_code'] for m in response.json()]
        self.assertIn('ASSIGNED-01', codes)
        self.assertIn('UNASSIGNED-01', codes)
        self.assertIn('INACTIVE-01', codes)

    def test_supervisor_sees_all_machines(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        response = self.client.get(self.machines_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [m['machine_code'] for m in response.json()]
        self.assertIn('ASSIGNED-01', codes)
        self.assertIn('UNASSIGNED-01', codes)
        self.assertIn('INACTIVE-01', codes)

    def test_engineer_only_sees_assigned_active_machines(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        response = self.client.get(self.machines_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [m['machine_code'] for m in response.json()]
        self.assertIn('ASSIGNED-01', codes)
        self.assertNotIn('UNASSIGNED-01', codes)  # Unassigned machine excluded
        self.assertNotIn('INACTIVE-01', codes)    # Inactive machine excluded

    def test_engineer_cannot_retrieve_unassigned_machine_by_id(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        # Attempt to retrieve unassigned machine
        response = self.client.get(f'{self.machines_url}{self.machine_unassigned.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_engineer_can_retrieve_assigned_machine_by_id(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        response = self.client.get(f'{self.machines_url}{self.machine_assigned.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['machine_code'], 'ASSIGNED-01')

    def test_engineer_assigned_convenience_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        response = self.client.get(f'{self.machines_url}assigned/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [m['machine_code'] for m in response.json()]
        self.assertEqual(codes, ['ASSIGNED-01'])

    def test_unauthenticated_requests_rejected(self):
        response = self.client.get(self.machines_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_rejected(self):
        self.engineer1.is_active = False
        self.engineer1.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        response = self.client.get(self.machines_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==============================================================================
# 3. Machine Assignment API Tests
# ==============================================================================

class MachineAssignmentAPITestCase(BaseMachineTestCase):
    """
    Tests for engineer assignments (/api/machines/{id}/assignments/).
    """

    def setUp(self):
        super().setUp()
        self.active_machine = Machine.objects.create(
            machine_code='ACTIVE-M01',
            name='Active Machine',
            status=MachineStatus.ACTIVE,
            created_by=self.admin
        )
        self.inactive_machine = Machine.objects.create(
            machine_code='INACTIVE-M01',
            name='Inactive Machine',
            status=MachineStatus.INACTIVE,
            created_by=self.admin
        )
        self.assignments_url = f'/api/machines/{self.active_machine.id}/assignments/'

    def test_admin_can_assign_engineer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(self.assignments_url, {'user_id': self.engineer1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data['user']['email'], self.engineer1.email)
        self.assertEqual(data['machine_code'], 'ACTIVE-M01')
        self.assertTrue(data['is_active'])

        assignment = MachineAssignment.objects.get(machine=self.active_machine, user=self.engineer1)
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.assigned_by, self.admin)

    def test_duplicate_active_assignment_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        # Initial assignment
        self.client.post(self.assignments_url, {'user_id': self.engineer1.id})

        # Duplicate assignment attempt
        response = self.client.post(self.assignments_url, {'user_id': self.engineer1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already actively assigned', str(response.json()))

    def test_admin_can_unassign_engineer(self):
        assignment = MachineAssignment.objects.create(
            machine=self.active_machine,
            user=self.engineer1,
            assigned_by=self.admin,
            is_active=True
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        unassign_url = f'{self.assignments_url}{assignment.id}/'

        response = self.client.delete(unassign_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)  # Soft unassigned
        self.assertTrue(MachineAssignment.objects.filter(pk=assignment.pk).exists())  # History kept

    def test_reassignment_after_unassignment_works_cleanly(self):
        # Create and unassign
        assignment = MachineAssignment.objects.create(
            machine=self.active_machine,
            user=self.engineer1,
            assigned_by=self.admin,
            is_active=False
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(self.assignments_url, {'user_id': self.engineer1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)  # Reactivated without duplicate active conflicts

    def test_cannot_assign_inactive_user(self):
        self.engineer2.is_active = False
        self.engineer2.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(self.assignments_url, {'user_id': self.engineer2.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inactive user', str(response.json()))

    def test_cannot_assign_non_engineer_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        # Attempt to assign a supervisor as an engineer
        response = self.client.post(self.assignments_url, {'user_id': self.supervisor.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ENGINEER role', str(response.json()))

    def test_cannot_assign_engineer_to_inactive_machine(self):
        inactive_url = f'/api/machines/{self.inactive_machine.id}/assignments/'
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.post(inactive_url, {'user_id': self.engineer1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inactive machine', str(response.json()))

    def test_supervisors_cannot_assign_engineers(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        response = self.client.post(self.assignments_url, {'user_id': self.engineer1.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineers_cannot_assign_themselves_or_others(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        response = self.client.post(self.assignments_url, {'user_id': self.engineer1.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_view_assignments_rbac(self):
        MachineAssignment.objects.create(
            machine=self.active_machine,
            user=self.engineer1,
            assigned_by=self.admin,
            is_active=True
        )
        MachineAssignment.objects.create(
            machine=self.active_machine,
            user=self.engineer2,
            assigned_by=self.admin,
            is_active=True
        )

        # Admin sees all
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        res_admin = self.client.get(self.assignments_url)
        self.assertEqual(len(res_admin.json()), 2)

        # Supervisor sees all (read-only)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.supervisor_token}')
        res_sup = self.client.get(self.assignments_url)
        self.assertEqual(len(res_sup.json()), 2)

        # Engineer1 only sees their own assignment
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.engineer1_token}')
        res_eng = self.client.get(self.assignments_url)
        self.assertEqual(len(res_eng.json()), 1)
        self.assertEqual(res_eng.json()[0]['user']['email'], self.engineer1.email)
