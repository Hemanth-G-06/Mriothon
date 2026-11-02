from django.contrib import admin
from machines.models import Machine


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'model_number', 'serial_number', 'location', 'created_at')
    search_fields = ('name', 'model_number', 'serial_number', 'location')
    list_filter = ('location', 'created_at')
"""
Django Admin interface registration for Machine and MachineAssignment models.
"""

from django.contrib import admin
from machines.models import Machine, MachineAssignment


class MachineAssignmentInline(admin.TabularInline):
    model = MachineAssignment
    extra = 1
    fields = ('user', 'assigned_by', 'assigned_at', 'is_active')
    readonly_fields = ('assigned_at',)


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        'machine_code',
        'name',
        'manufacturer',
        'model_number',
        'location',
        'status',
        'created_at',
    )
    list_filter = ('status', 'manufacturer', 'created_at')
    search_fields = ('machine_code', 'name', 'manufacturer', 'model_number', 'location')
    ordering = ('machine_code',)
    inlines = [MachineAssignmentInline]
    readonly_fields = ('id', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(MachineAssignment)
class MachineAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'machine',
        'user',
        'assigned_by',
        'assigned_at',
        'is_active',
    )
    list_filter = ('is_active', 'assigned_at', 'machine')
    search_fields = ('machine__machine_code', 'machine__name', 'user__email')
    ordering = ('-assigned_at',)
    readonly_fields = ('assigned_at',)
