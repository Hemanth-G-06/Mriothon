"""
Tests for the Machines application.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User, UserRole
from machines.models import Machine


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
