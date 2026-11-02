from django.contrib import admin
from machines.models import Machine


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'model_number', 'serial_number', 'location', 'created_at')
    search_fields = ('name', 'model_number', 'serial_number', 'location')
    list_filter = ('location', 'created_at')
