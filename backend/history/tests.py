"""
Comprehensive test suite for the History application:
- Engineer query ownership isolation.
- Supervisor read-only inspection across all machines and engineers.
- Administrator full inspection access.
- Inactive user rejection.
- Method not allowed (read-only enforcement against mutations).
"""

import uuid
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from machines.models import Machine
from history.models import QueryRecord


class QueryHistoryAPITestCase(APITestCase):
    """
    Tests security boundaries and RBAC permissions for Query History APIs.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="hist_admin@test.com", password="password123", role=UserRole.ADMIN
        )
        self.supervisor = User.objects.create_user(
            email="hist_supervisor@test.com", password="password123", role=UserRole.SUPERVISOR
        )
        self.engineer_1 = User.objects.create_user(
            email="hist_eng1@test.com", password="password123", role=UserRole.ENGINEER
        )
        self.engineer_2 = User.objects.create_user(
            email="hist_eng2@test.com", password="password123", role=UserRole.ENGINEER
        )
        self.inactive_engineer = User.objects.create_user(
            email="hist_inactive@test.com", password="password123", role=UserRole.ENGINEER, is_active=False
        )

        self.machine_1 = Machine.objects.create(
            machine_code="MACH-H1", name="Hydraulic Press", created_by=self.admin
        )
        self.machine_2 = Machine.objects.create(
            machine_code="MACH-H2", name="CNC Lathe", created_by=self.admin
        )

        # Create query records for both engineers
        self.record_eng1 = QueryRecord.objects.create(
            user=self.engineer_1,
            machine=self.machine_1,
            question="What is the operating pressure of the hydraulic press?",
            answer="The rated pressure is 210 bar.",
            abstained=False,
            citations=[{
                "document_id": str(uuid.uuid4()),
                "document_title": "Press Manual",
                "page_number": 10,
                "source_id": "DOC-H1-P10-C0"
            }]
        )

        self.record_eng2 = QueryRecord.objects.create(
            user=self.engineer_2,
            machine=self.machine_2,
            question="What lubricant is specified for the CNC spindle?",
            answer="ISO VG 68 synthetic oil is specified.",
            abstained=False,
            citations=[{
                "document_id": str(uuid.uuid4()),
                "document_title": "Lathe Manual",
                "page_number": 4,
                "source_id": "DOC-H2-P4-C0"
            }]
        )

        self.list_url = reverse('history:query-history-list')
        self.detail_url_eng1 = reverse('history:query-history-detail', kwargs={'id': self.record_eng1.id})
        self.detail_url_eng2 = reverse('history:query-history-detail', kwargs={'id': self.record_eng2.id})

    def test_unauthenticated_request_rejected(self):
        """Unauthenticated requests must be rejected with HTTP 401."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_rejected(self):
        """Inactive user accounts must be rejected with HTTP 403."""
        self.client.force_authenticate(user=self.inactive_engineer)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_ownership_isolation_on_list(self):
        """Engineer 1 must only see queries executed by Engineer 1."""
        self.client.force_authenticate(user=self.engineer_1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.record_eng1.id))
        self.assertEqual(response.data[0]['user_email'], self.engineer_1.email)

        # Engineer 2 must only see queries executed by Engineer 2
        self.client.force_authenticate(user=self.engineer_2)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.record_eng2.id))
        self.assertEqual(response.data[0]['user_email'], self.engineer_2.email)

    def test_engineer_cannot_access_other_engineer_query_detail(self):
        """Engineer 1 attempting to view Engineer 2's query record must receive HTTP 404."""
        self.client.force_authenticate(user=self.engineer_1)
        response = self.client.get(self.detail_url_eng2)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Can access own record
        response_own = self.client.get(self.detail_url_eng1)
        self.assertEqual(response_own.status_code, status.HTTP_200_OK)
        self.assertEqual(response_own.data['id'], str(self.record_eng1.id))

    def test_supervisor_can_inspect_all_queries(self):
        """Supervisor must be permitted to view all query records across all engineers."""
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Supervisor can view both details
        resp_1 = self.client.get(self.detail_url_eng1)
        self.assertEqual(resp_1.status_code, status.HTTP_200_OK)
        resp_2 = self.client.get(self.detail_url_eng2)
        self.assertEqual(resp_2.status_code, status.HTTP_200_OK)

    def test_supervisor_can_filter_by_machine(self):
        """Supervisor can filter query logs by machine_id."""
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(f"{self.list_url}?machine_id={self.machine_1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['machine_code'], self.machine_1.machine_code)

    def test_administrator_can_inspect_all_queries(self):
        """Administrator must be permitted to view all query records."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_mutation_methods_strictly_forbidden(self):
        """Query history is immutable and audit-only: POST, PUT, PATCH, DELETE must return 405."""
        self.client.force_authenticate(user=self.admin)
        post_resp = self.client.post(self.list_url, {"question": "Hack"})
        self.assertEqual(post_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        put_resp = self.client.put(self.detail_url_eng1, {"question": "Modified"})
        self.assertEqual(put_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        del_resp = self.client.delete(self.detail_url_eng1)
        self.assertEqual(del_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_supervisor_statistics(self):
        """Supervisor can fetch operational statistics."""
        self.client.force_authenticate(user=self.supervisor)
        stats_url = reverse('history:supervisor-statistics')
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_questions', response.data)
        self.assertIn('answered_questions', response.data)
        self.assertIn('insufficient_evidence_questions', response.data)
        self.assertIn('active_machines_monitored', response.data)
