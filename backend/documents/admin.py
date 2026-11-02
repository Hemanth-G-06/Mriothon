from django.contrib import admin
from documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'machine', 'manual_type', 'model_number', 'revision', 'status', 'created_at')
    search_fields = ('title', 'model_number', 'machine__name')
    list_filter = ('status', 'manual_type', 'created_at')
