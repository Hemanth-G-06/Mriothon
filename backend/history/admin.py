from django.contrib import admin
from history.models import QueryRecord


@admin.register(QueryRecord)
class QueryRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'machine', 'user', 'question', 'abstained', 'created_at')
    search_fields = ('question', 'answer', 'user__email', 'machine__name', 'machine__machine_code')
    list_filter = ('abstained', 'machine', 'created_at')
    readonly_fields = ('id', 'created_at')
