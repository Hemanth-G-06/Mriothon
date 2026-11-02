"""
Comprehensive integration and unit tests for Engineer Chat Conversations and Messages.
Verifies RBAC access restriction (Engineer-only), cross-user and cross-machine isolation,
persistent conversation lifecycle, chronological ordering, and RAG integration.
"""

from unittest.mock import MagicMock, patch
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserRole
from chat.models import ChatMessage, Conversation
from documents.models import Document, DocumentPage, DocumentStatus
from machines.models import Machine, MachineAssignment, MachineStatus
from rag.services.generation_service import GroundedAnswer
from rag.services.llm.base import LLMRateLimitError
from rag.services.retrieval_service import RetrievedChunkContext

User = get_user_model()


class EngineerChatAPITestCase(TestCase):
    """
    Test suite covering all aspects of persistent conversation management,
    RBAC enforcement, cross-user and cross-machine isolation.
    """

    def setUp(self):
        self.client = APIClient()

        # Users
        self.admin = User.objects.create_user(
            email='admin@factory.local', password='Password123!', role=UserRole.ADMIN
        )
        self.supervisor = User.objects.create_user(
            email='supervisor@factory.local', password='Password123!', role=UserRole.SUPERVISOR
        )
        self.engineer1 = User.objects.create_user(
            email='engineer1@factory.local', password='Password123!', role=UserRole.ENGINEER
        )
        self.engineer2 = User.objects.create_user(
            email='engineer2@factory.local', password='Password123!', role=UserRole.ENGINEER
        )

        # Machines
        self.machine1 = Machine.objects.create(
            name='Hydraulic Press HP-200',
            machine_code='HP-200',
            status=MachineStatus.ACTIVE,
            created_by=self.admin,
        )
        self.machine2 = Machine.objects.create(
            name='Air Compressor AC-90',
            machine_code='AC-90',
            status=MachineStatus.ACTIVE,
            created_by=self.admin,
        )
        self.inactive_machine = Machine.objects.create(
            name='Inactive Lathe L-10',
            machine_code='L-10',
            status=MachineStatus.INACTIVE,
            created_by=self.admin,
        )

        # Assignments: Engineer1 assigned to Machine1; Engineer2 assigned to Machine2
        self.assignment1 = MachineAssignment.objects.create(
            user=self.engineer1, machine=self.machine1, is_active=True, assigned_by=self.admin
        )
        self.assignment2 = MachineAssignment.objects.create(
            user=self.engineer2, machine=self.machine2, is_active=True, assigned_by=self.admin
        )

        # Document on Machine1
        self.doc1 = Document.objects.create(
            machine=self.machine1,
            title='HP-200 Operations Manual',
            original_filename='hp200_ops.pdf',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
        )
        self.page1 = DocumentPage.objects.create(
            document=self.doc1,
            page_number=4,
            text='Normal operating pressure is 180 to 200 bar. Relief valve RV-1 cracks at 220 bar.',
            character_count=80,
        )

    def test_engineer_can_create_conversation(self):
        """Engineer can successfully create a new conversation for an assigned active machine."""
        self.client.force_authenticate(user=self.engineer1)
        response = self.client.post('/api/chat/conversations/', {
            'machine_id': str(self.machine1.id),
            'title': 'Pressure Checks',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['title'], 'Pressure Checks')
        self.assertEqual(data['machine_id'], str(self.machine1.id))
        self.assertEqual(data['machine_code'], 'HP-200')
        self.assertTrue(Conversation.objects.filter(id=data['id'], user=self.engineer1).exists())

    def test_engineer_cannot_create_conversation_for_unassigned_machine(self):
        """Engineer cannot create a conversation for a machine they are not assigned to (400/403)."""
        self.client.force_authenticate(user=self.engineer1)
        response = self.client.post('/api/chat/conversations/', {
            'machine_id': str(self.machine2.id),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not assigned', str(response.json()))

    def test_engineer_cannot_create_conversation_for_inactive_machine(self):
        """Inactive machines cannot be used for new conversations."""
        MachineAssignment.objects.create(
            user=self.engineer1, machine=self.inactive_machine, is_active=True, assigned_by=self.admin
        )
        self.client.force_authenticate(user=self.engineer1)
        response = self.client.post('/api/chat/conversations/', {
            'machine_id': str(self.inactive_machine.id),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inactive', str(response.json()))

    def test_admin_and_supervisor_denied_access_to_conversations(self):
        """Admin and Supervisor roles must receive HTTP 403 on chat conversation endpoints."""
        for user in [self.admin, self.supervisor]:
            self.client.force_authenticate(user=user)
            res_list = self.client.get('/api/chat/conversations/')
            self.assertEqual(res_list.status_code, status.HTTP_403_FORBIDDEN)

            res_create = self.client.post('/api/chat/conversations/', {'machine_id': str(self.machine1.id)})
            self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_lists_only_own_conversations(self):
        """Conversations list strictly isolates conversations by the authenticated engineer."""
        c1 = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='Eng1 Conv')
        c2 = Conversation.objects.create(user=self.engineer2, machine=self.machine2, title='Eng2 Conv')

        self.client.force_authenticate(user=self.engineer1)
        response = self.client.get('/api/chat/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [c['id'] for c in response.json()]
        self.assertIn(str(c1.id), ids)
        self.assertNotIn(str(c2.id), ids)

    def test_engineer_retrieves_own_conversation_chronologically(self):
        """Retrieving conversation returns all messages ordered chronologically."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='History Test')
        m1 = ChatMessage.objects.create(
            conversation=conv, role=ChatMessage.Role.USER, content='What is the relief pressure?'
        )
        m2 = ChatMessage.objects.create(
            conversation=conv, role=ChatMessage.Role.ASSISTANT, content='Relief pressure is 220 bar.',
            citations=[{'document_id': str(self.doc1.id), 'page_number': 4}]
        )
        m3 = ChatMessage.objects.create(
            conversation=conv, role=ChatMessage.Role.USER, content='Is there a secondary valve?'
        )

        self.client.force_authenticate(user=self.engineer1)
        response = self.client.get(f'/api/chat/conversations/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['messages']), 3)
        self.assertEqual(data['messages'][0]['id'], str(m1.id))
        self.assertEqual(data['messages'][1]['id'], str(m2.id))
        self.assertEqual(data['messages'][2]['id'], str(m3.id))
        self.assertEqual(data['messages'][1]['citations'][0]['page_number'], 4)

    def test_cross_user_conversation_access_blocked(self):
        """Engineer2 cannot retrieve or message Engineer1's conversation."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='Private Conv')

        self.client.force_authenticate(user=self.engineer2)
        res_get = self.client.get(f'/api/chat/conversations/{conv.id}/')
        self.assertEqual(res_get.status_code, status.HTTP_403_FORBIDDEN)

        res_msg = self.client.post(f'/api/chat/conversations/{conv.id}/messages/', {'content': 'Sneak query'})
        self.assertEqual(res_msg.status_code, status.HTTP_403_FORBIDDEN)

        res_del = self.client.delete(f'/api/chat/conversations/{conv.id}/')
        self.assertEqual(res_del.status_code, status.HTTP_403_FORBIDDEN)

    def test_unassigned_machine_access_denied_on_existing_conversation(self):
        """If an engineer is unassigned from a machine, existing conversations cannot be retrieved or continued."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='Old Conv')

        # Revoke assignment
        self.assignment1.is_active = False
        self.assignment1.save()

        self.client.force_authenticate(user=self.engineer1)
        res_get = self.client.get(f'/api/chat/conversations/{conv.id}/')
        self.assertEqual(res_get.status_code, status.HTTP_403_FORBIDDEN)

        res_msg = self.client.post(f'/api/chat/conversations/{conv.id}/messages/', {'content': 'Query after unassign'})
        self.assertEqual(res_msg.status_code, status.HTTP_403_FORBIDDEN)

    @patch('chat.services.get_retrieval_service')
    @patch('chat.services.GroundedAnswerGenerationService')
    def test_send_message_executes_rag_and_persists_answer_and_citations(self, MockGen, MockGetSvc):
        """Sending a message invokes RAG, saves both USER and ASSISTANT messages, and records citations."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='New Conversation')

        mock_svc = MockGetSvc.return_value
        mock_svc.retrieve_context.return_value = [
            RetrievedChunkContext(
                source_id='DOC-HP-P4-C0',
                document_id=str(self.doc1.id),
                document_title=self.doc1.title,
                original_filename='hp200_ops.pdf',
                machine_id=str(self.machine1.id),
                page_number=4,
                chunk_index=0,
                chunk_text='Relief valve RV-1 cracks at 220 bar.',
                similarity_score=0.97,
                chroma_vector_id='vec1',
            )
        ]
        MockGen.return_value.generate_answer.return_value = GroundedAnswer(
            answer='Relief valve RV-1 cracks at 220 bar under normal hydraulic conditions.',
            citations=[{
                'document_id': str(self.doc1.id),
                'document_title': self.doc1.title,
                'page_number': 4,
                'source_id': 'DOC-HP-P4-C0',
            }],
            abstained=False,
        )

        self.client.force_authenticate(user=self.engineer1)
        response = self.client.post(f'/api/chat/conversations/{conv.id}/messages/', {
            'content': 'What is the relief valve cracking pressure?',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        # Check returned response structure
        self.assertIn('user_message', data)
        self.assertIn('assistant_message', data)
        self.assertEqual(data['user_message']['content'], 'What is the relief valve cracking pressure?')
        self.assertIn('220 bar', data['assistant_message']['content'])
        self.assertEqual(len(data['assistant_message']['citations']), 1)
        self.assertEqual(data['assistant_message']['citations'][0]['page_number'], 4)

        # Check persistence in database
        self.assertEqual(conv.messages.count(), 2)
        user_msg = conv.messages.filter(role=ChatMessage.Role.USER).first()
        asst_msg = conv.messages.filter(role=ChatMessage.Role.ASSISTANT).first()
        self.assertIsNotNone(user_msg)
        self.assertIsNotNone(asst_msg)
        self.assertEqual(user_msg.content, 'What is the relief valve cracking pressure?')
        self.assertEqual(asst_msg.citations[0]['document_id'], str(self.doc1.id))

        # Check auto-title update
        conv.refresh_from_db()
        self.assertIn('relief valve cracking pressure', conv.title.lower())

    @patch('chat.services.get_retrieval_service')
    @patch('chat.services.GroundedAnswerGenerationService')
    def test_provider_failure_does_not_create_fake_assistant_message(self, MockGen, MockGetSvc):
        """When the LLM provider fails, user message is preserved but NO assistant message is created."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='Error Test')

        MockGetSvc.return_value.retrieve_context.return_value = []
        MockGen.return_value.generate_answer.side_effect = LLMRateLimitError('Rate limit exceeded')

        self.client.force_authenticate(user=self.engineer1)
        response = self.client.post(f'/api/chat/conversations/{conv.id}/messages/', {
            'content': 'Trigger rate limit error',
        })
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.json().get('error_type'), 'llm_rate_limit')

        # Verify user message exists but assistant message was NOT created
        self.assertEqual(conv.messages.filter(role=ChatMessage.Role.USER).count(), 1)
        self.assertEqual(conv.messages.filter(role=ChatMessage.Role.ASSISTANT).count(), 0)

    def test_rename_and_delete_conversation(self):
        """Engineer can rename and delete their conversation with all child messages removed."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='Original Title')
        ChatMessage.objects.create(conversation=conv, role=ChatMessage.Role.USER, content='Msg')

        self.client.force_authenticate(user=self.engineer1)

        # Rename
        res_patch = self.client.patch(f'/api/chat/conversations/{conv.id}/', {'title': 'Updated Title'})
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        conv.refresh_from_db()
        self.assertEqual(conv.title, 'Updated Title')

        # Delete
        res_del = self.client.delete(f'/api/chat/conversations/{conv.id}/')
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)
        self.assertFalse(Conversation.objects.filter(id=conv.id).exists())
        self.assertEqual(ChatMessage.objects.filter(conversation_id=conv.id).count(), 0)

    def test_conversation_persists_across_token_refresh(self):
        """Conversations and messages persist across JWT authentication cycles."""
        conv = Conversation.objects.create(user=self.engineer1, machine=self.machine1, title='Persistence Test')
        ChatMessage.objects.create(conversation=conv, role=ChatMessage.Role.USER, content='Persisted query')

        # Obtain fresh tokens
        refresh = RefreshToken.for_user(self.engineer1)
        token = str(refresh.access_token)

        new_client = APIClient()
        new_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = new_client.get(f'/api/chat/conversations/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['title'], 'Persistence Test')
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['messages'][0]['content'], 'Persisted query')

