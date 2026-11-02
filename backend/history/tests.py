"""
Tests for the History application.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User, UserRole
from machines.models import Machine
from history.models import QueryRecord


class HistoryAPITestCase(TestCase):
    """
    Test suite for supervisor audit history and statistics API endpoints.
    """

    def setUp(self):
        self.client = APIClient()

        self.supervisor_user = User.objects.create_user(
            email='supervisor@plantops.com',
            password='SupervisorPassword@123',
            role=UserRole.SUPERVISOR
        )

        self.machine = Machine.objects.create(
            name='AC-90 Compressor',
            model_number='AC-90',
            serial_number='SN-AC001'
        )

        self.record1 = QueryRecord.objects.create(
            machine=self.machine,
            user=self.supervisor_user,
            engineer_name='Alex Vance',
            question='What is the cutoff pressure?',
            answer='14.5 bar emergency interlock.',
            is_insufficient_evidence=False,
            citations=[{'page_number': 12, 'document_title': 'AC-90 Manual'}]
        )

        self.record2 = QueryRecord.objects.create(
            machine=self.machine,
            user=self.supervisor_user,
            engineer_name='Alex Vance',
            question='Can mineral oil be used?',
            answer='No documentation found in manuals.',
            is_insufficient_evidence=True,
            citations=[]
        )

    def test_supervisor_can_list_history(self):
        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.get('/api/supervisor/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 2)
        self.assertEqual(len(response.data['results']), 2)

    def test_supervisor_history_filtering(self):
        self.client.force_authenticate(user=self.supervisor_user)
        # Filter by status=answered
        response = self.client.get('/api/supervisor/history/?status=answered')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertFalse(response.data['results'][0]['is_insufficient_evidence'])

        # Filter by status=insufficient_evidence
        response = self.client.get('/api/supervisor/history/?status=insufficient_evidence')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertTrue(response.data['results'][0]['is_insufficient_evidence'])

        # Search filter
        response = self.client.get('/api/supervisor/history/?search=cutoff')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)

    def test_supervisor_can_get_history_detail(self):
        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.get(f'/api/supervisor/history/{self.record1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['question'], 'What is the cutoff pressure?')
        self.assertEqual(response.data['machine_name'], 'AC-90 Compressor')

    def test_supervisor_can_get_statistics(self):
        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.get('/api/supervisor/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_questions'], 2)
        self.assertEqual(response.data['answered_questions'], 1)
        self.assertEqual(response.data['insufficient_evidence_questions'], 1)
        self.assertEqual(response.data['active_machines_monitored'], 1)

    def test_history_alias_endpoints(self):
        self.client.force_authenticate(user=self.supervisor_user)
        response_hist = self.client.get('/api/history/')
        self.assertEqual(response_hist.status_code, status.HTTP_200_OK)
        self.assertEqual(response_hist.data['total'], 2)

        response_stats = self.client.get('/api/history/statistics/')
        self.assertEqual(response_stats.status_code, status.HTTP_200_OK)
        self.assertEqual(response_stats.data['total_questions'], 2)
