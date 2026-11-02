"""
Serializers for the Inspections application.
Transforms Product, InspectionRecord, and BatchInspection domain entities
into contract-compliant JSON representations.
"""

from rest_framework import serializers
from inspections.models import Product, InspectionRecord, BatchInspection


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for registered manufactured products.
    """
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'model_version',
            'category',
            'description',
            'status',
            'min_dimensions',
            'max_dimensions',
            'created_at',
            'updated_at'
        ]


class InspectionRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for visual inspection records with media URL generation and
    complete supervisor calibration details.
    """
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = InspectionRecord
        fields = [
            'id',
            'product_id',
            'image_url',
            'thumbnail_url',
            'predicted_class',
            'confidence',
            'defect_probability',
            'model_version',
            'status',
            'error_message',
            'review_status',
            'supervisor_class',
            'supervisor_name',
            'review_comment',
            'reviewed_at',
            'engineer_name',
            'file_name',
            'file_size',
            'image_width',
            'image_height',
            'batch_id',
            'created_at',
            'updated_at'
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        try:
            url = obj.image.url
            if request:
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None

    def get_thumbnail_url(self, obj):
        return self.get_image_url(obj)


class SupervisorReviewSerializer(serializers.Serializer):
    """
    Validates supervisor review determinations.
    Supported actions:
    - confirm: Approves the original model prediction.
    - correct: Overrides the classification with a human decision.
    """
    action = serializers.ChoiceField(choices=['confirm', 'correct'])
    corrected_class = serializers.ChoiceField(
        choices=['Normal', 'Defective'],
        required=False,
        allow_blank=True
    )
    comment = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        action = attrs.get('action')
        corrected_class = attrs.get('corrected_class')
        if action == 'correct' and not corrected_class:
            raise serializers.ValidationError({
                'corrected_class': "The 'corrected_class' field ('Normal' or 'Defective') is required when action is 'correct'."
            })
        return attrs


class BatchInspectionSerializer(serializers.ModelSerializer):
    """
    Serializer for batch inspection status and items.
    """
    items = serializers.SerializerMethodField()

    class Meta:
        model = BatchInspection
        fields = [
            'batch_id',
            'product_id',
            'total_images',
            'completed_count',
            'failed_count',
            'status',
            'created_at',
            'updated_at',
            'items'
        ]

    def get_items(self, obj):
        records = InspectionRecord.objects.filter(batch_id=obj.batch_id).order_by('id')
        return InspectionRecordSerializer(records, many=True, context=self.context).data
