"""
Serializers for Engineer Chat Conversations and Messages.
"""

from rest_framework import serializers
from chat.models import Conversation, ChatMessage
from machines.models import Machine, MachineStatus
from machines.services import can_user_access_machine


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Serializes a single chat message with its role, content, and verified citations.
    """
    conversation_id = serializers.UUIDField(source='conversation.id', read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'conversation_id',
            'role',
            'content',
            'citations',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'conversation_id', 'created_at']


class ConversationListSerializer(serializers.ModelSerializer):
    """
    Summary serializer for listing an engineer's conversations.
    Includes machine context and preview of the most recent message.
    """
    machine_id = serializers.UUIDField(source='machine.id', read_only=True)
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'title',
            'machine_id',
            'machine_name',
            'machine_code',
            'is_archived',
            'created_at',
            'updated_at',
            'message_count',
            'last_message',
        ]
        read_only_fields = fields

    def get_message_count(self, obj) -> int:
        return obj.messages.count()

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if not last_msg:
            return None
        return {
            'role': last_msg.role,
            'content': last_msg.content[:120],
            'created_at': last_msg.created_at,
        }


class ConversationDetailSerializer(serializers.ModelSerializer):
    """
    Full conversation serializer including all messages in chronological order.
    """
    machine_id = serializers.UUIDField(source='machine.id', read_only=True)
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    machine_code = serializers.CharField(source='machine.machine_code', read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = [
            'id',
            'title',
            'machine_id',
            'machine_name',
            'machine_code',
            'is_archived',
            'created_at',
            'updated_at',
            'messages',
        ]
        read_only_fields = fields


class ConversationCreateSerializer(serializers.Serializer):
    """
    Validates creation of a new conversation session for an authorized machine.
    """
    machine_id = serializers.UUIDField(required=True)
    title = serializers.CharField(required=False, allow_blank=True, max_length=255, default='New Conversation')

    def validate_machine_id(self, value):
        try:
            machine = Machine.objects.get(id=value)
        except Machine.DoesNotExist:
            raise serializers.ValidationError(f"Machine '{value}' does not exist.")

        if machine.status != MachineStatus.ACTIVE:
            raise serializers.ValidationError(f"Machine '{machine.machine_code}' is currently inactive.")

        user = self.context.get('request').user
        if not can_user_access_machine(user, machine):
            raise serializers.ValidationError(f"User is not assigned to access machine '{machine.machine_code}'.")

        self.context['machine'] = machine
        return value


class ConversationUpdateSerializer(serializers.ModelSerializer):
    """
    Allows renaming an existing conversation.
    """
    title = serializers.CharField(required=True, max_length=255, allow_blank=False)

    class Meta:
        model = Conversation
        fields = ['title']


class ChatMessageCreateSerializer(serializers.Serializer):
    """
    Validates an incoming user message within a conversation.
    Supports either 'content' or 'message' field name.
    """
    content = serializers.CharField(required=False, allow_blank=False)
    message = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        content = attrs.get('content') or attrs.get('message')
        if not content or not content.strip():
            raise serializers.ValidationError({"content": "Message content cannot be blank."})
        attrs['content'] = content.strip()
        return attrs

