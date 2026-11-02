"""
Models for the History application.

Domain models for question history, query records, supporting manual citations,
and supervisor audit history.
"""

from django.db import models
from django.conf import settings
from machines.models import Machine


class QueryRecord(models.Model):
    """
    Log of a question asked by an engineer against a machine manual,
    the resulting RAG response, evidence flags, and cited document pages.
    """
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='query_records')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='query_records'
    )
    engineer_name = models.CharField(max_length=255, blank=True, default='Plant Engineer')
    question = models.TextField()
    answer = models.TextField()
    is_insufficient_evidence = models.BooleanField(default=False)
    citations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.machine.name}] {self.question[:40]}"
