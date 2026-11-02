from django.contrib import admin
from history.models import QueryRecord


@admin.register(QueryRecord)
class QueryRecordAdmin(admin.ModelAdmin):
    list_display = ('machine', 'engineer_name', 'question', 'is_insufficient_evidence', 'created_at')
    search_fields = ('question', 'answer', 'engineer_name', 'machine__name')
    list_filter = ('is_insufficient_evidence', 'machine', 'created_at')
