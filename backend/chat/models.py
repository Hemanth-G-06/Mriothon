"""
Relational models for Engineer Conversations and Multi-Turn Chat Messages.
Stores persistent conversation sessions and chronological message logs
strictly isolated per engineer and target manufacturing machine.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
    """
    Persistent conversation container belonging exclusively to an authenticated engineer
    and scoped to a specific authorized machine context.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique conversation UUID identifier.')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name=_('engineer'),
        help_text=_('Engineer owner of this conversation.')
    )
    machine = models.ForeignKey(
        'machines.Machine',
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name=_('machine'),
        help_text=_('Machine context for all manual retrieval within this conversation.')
    )
    title = models.CharField(
        _('title'),
        max_length=255,
        default='New Conversation',
        help_text=_('Conversation title, auto-generated from initial query or customized by engineer.')
    )
    is_archived = models.BooleanField(
        _('is archived'),
        default=False,
        help_text=_('Whether this conversation has been archived.')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        db_index=True
    )

    class Meta:
        db_table = 'chat_conversations'
        verbose_name = _('conversation')
        verbose_name_plural = _('conversations')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['machine', 'user']),
        ]

    def __str__(self):
        return f"{self.title} [{self.machine.machine_code}] ({self.user.email})"


class ChatMessage(models.Model):
    """
    Individual chronological message within a persistent conversation.
    Stores either user inquiries or grounded assistant answers with citations.
    """
    class Role(models.TextChoices):
        USER = 'USER', _('User')
        ASSISTANT = 'ASSISTANT', _('Assistant')

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_('Unique chat message UUID identifier.')
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('conversation'),
        help_text=_('Parent conversation this message belongs to.')
    )
    role = models.CharField(
        _('role'),
        max_length=20,
        choices=Role.choices,
        help_text=_('Role of the message sender: USER or ASSISTANT.')
    )
    content = models.TextField(
        _('content'),
        help_text=_('Message text content.')
    )
    citations = models.JSONField(
        _('citations'),
        default=list,
        blank=True,
        help_text=_('Verified source citation metadata returned by the RAG pipeline.')
    )
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Optional operational metadata (e.g. abstained status, query_id, trace_id).')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )

    class Meta:
        db_table = 'chat_messages'
        verbose_name = _('chat message')
        verbose_name_plural = _('chat messages')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:40]}... ({self.created_at})"

