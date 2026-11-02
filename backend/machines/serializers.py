"""
Serializers for the Machines application.
"""

from rest_framework import serializers
from machines.models import Machine


class MachineSerializer(serializers.ModelSerializer):
    """
    Serializer for Machine model supporting list, retrieve, and creation.
    """
    manuals_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Machine
        fields = [
            'id',
            'name',
            'model_number',
            'serial_number',
            'location',
            'description',
            'manuals_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'manuals_count']
