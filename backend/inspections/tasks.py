"""
Celery Background Tasks for Asynchronous Batch Image Inspection.
Provides distributed processing, fault isolation, and progress tracking via Redis.
"""

import time
import logging
from celery import shared_task
from django.db import transaction, OperationalError
from django.utils import timezone

logger = logging.getLogger(__name__)


def update_batch_progress(batch_id, delta_queued=0, delta_processing=0, delta_completed=0, delta_failed=0):
    """Resilient helper to update BatchInspection counters with retry."""
    if not batch_id:
        return
    from inspections.models import BatchInspection
    for attempt in range(5):
        try:
            with transaction.atomic():
                batch_obj = BatchInspection.objects.filter(batch_id=batch_id).first()
                if not batch_obj:
                    return
                if delta_queued != 0:
                    batch_obj.queued_count = max(0, batch_obj.queued_count + delta_queued)
                if delta_processing != 0:
                    batch_obj.processing_count = max(0, batch_obj.processing_count + delta_processing)
                if delta_completed != 0:
                    batch_obj.completed_count += delta_completed
                if delta_failed != 0:
                    batch_obj.failed_count += delta_failed

                if (batch_obj.completed_count + batch_obj.failed_count) >= batch_obj.total_images:
                    batch_obj.status = 'Completed' if batch_obj.completed_count > 0 else 'Failed'
                elif batch_obj.processing_count > 0 or batch_obj.completed_count > 0:
                    batch_obj.status = 'Processing'

                batch_obj.save()
                return
        except OperationalError:
            time.sleep(0.1 * (attempt + 1))
        except Exception as e:
            logger.warning(f"Could not update batch {batch_id} progress: {e}")
            return


@shared_task(bind=True, autoretry_for=(OperationalError,), retry_backoff=True, max_retries=5)
def process_inspection_task(self, record_id: int):
    """
    Celery task that runs AI visual inspection on a single validated image record.
    Guarantees isolation: failures here never affect other batch items.
    """
    from inspections.models import InspectionRecord
    from inspections.services.inference_service import inference_service

    try:
        record = InspectionRecord.objects.get(pk=record_id)
    except InspectionRecord.DoesNotExist:
        logger.error(f"[Celery] InspectionRecord #{record_id} does not exist.")
        return {"status": "error", "message": f"Record #{record_id} not found"}

    batch_id = record.batch_id

    # Transition to Processing
    record.status = InspectionRecord.STATUS_PROCESSING
    record.save(update_fields=['status', 'updated_at'])
    update_batch_progress(batch_id, delta_queued=-1, delta_processing=1)

    # Execute AI model inference
    try:
        if not record.image or not record.image.path:
            raise FileNotFoundError("Image file path is missing from inspection record.")

        prediction = inference_service.run_inference(record.image.path)

        # Store AI inference outputs (immutable)
        record.predicted_class = prediction['predicted_class']
        record.confidence = prediction['confidence']
        record.defect_probability = prediction['defect_probability']
        record.model_version = prediction['model_version']
        record.status = InspectionRecord.STATUS_COMPLETED
        record.failure_reason = ''
        record.save(update_fields=[
            'predicted_class',
            'confidence',
            'defect_probability',
            'model_version',
            'status',
            'failure_reason',
            'updated_at'
        ])

        update_batch_progress(batch_id, delta_processing=-1, delta_completed=1)
        logger.info(f"[Celery] InspectionRecord #{record_id} completed: {prediction['predicted_class']}")
        return {
            "status": "success",
            "record_id": record.id,
            "predicted_class": prediction['predicted_class'],
            "confidence": prediction['confidence']
        }

    except Exception as exc:
        logger.error(f"[Celery] Inference failed for record #{record_id}: {str(exc)}")
        record.status = InspectionRecord.STATUS_FAILED
        record.failure_reason = f"AI inference processing failed: {str(exc)}"
        record.save(update_fields=['status', 'failure_reason', 'updated_at'])

        update_batch_progress(batch_id, delta_processing=-1, delta_failed=1)
        return {
            "status": "failed",
            "record_id": record.id,
            "error": str(exc)
        }
