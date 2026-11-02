import React, { useState } from 'react';
import {
  X,
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  Clock,
  User,
  Package,
  Layers,
  Edit3,
  CheckCheck,
  AlertCircle
} from 'lucide-react';
import InspectionStatusBadge from '../../components/inspection/InspectionStatusBadge';
import { inspectionService } from '../../services/inspectionService';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

/**
 * Supervisor Inspection Detail & Review Modal
 *
 * Implements two distinct review actions:
 * 1. Confirm AI prediction
 * 2. Correct AI prediction (select Normal or Defective)
 * With optional comment, pre-submission confirmation dialog, and
 * guarantees that original AI predictions are NEVER overwritten.
 */
export default function InspectionDetailModal({ isOpen, inspection, onClose, onReviewSubmitted }) {
  if (!isOpen || !inspection) return null;

  // Review Form States
  const [reviewAction, setReviewAction] = useState('confirm'); // 'confirm' or 'correct'
  const [correctedClass, setCorrectedClass] = useState(
    inspection.predicted_class?.toLowerCase() === 'normal' ? 'Defective' : 'Normal'
  );
  const [comment, setComment] = useState('');
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorFeedback, setErrorFeedback] = useState(null);
  const [successFeedback, setSuccessFeedback] = useState(null);

  // Original AI telemetry
  const originalClass = inspection.predicted_class || inspection.prediction || 'Normal';
  const confidence = inspection.confidence;
  const defectProb = inspection.defect_probability;
  const modelVersion = inspection.model_version || 'BIT-PLATE-CV-1.0';
  const inspectionId = inspection.id;

  const formatConfidence = (val) => {
    if (val === undefined || val === null) return 'N/A';
    const num = Number(val);
    if (isNaN(num)) return String(val);
    if (num <= 1) return `${(num * 100).toFixed(1)}%`;
    return `${num.toFixed(1)}%`;
  };

  const handleOpenConfirmation = (e) => {
    e.preventDefault();
    setErrorFeedback(null);
    setShowConfirmation(true);
  };

  const handleFinalSubmit = async () => {
    setIsSubmitting(true);
    setErrorFeedback(null);

    const payload = {
      action: reviewAction,
      corrected_class: reviewAction === 'correct' ? correctedClass : originalClass,
      comment: comment.trim()
    };

    try {
      const response = await inspectionService.submitInspectionReview(inspectionId, payload);
      setSuccessFeedback('Inspection review submitted successfully!');
      setShowConfirmation(false);

      if (onReviewSubmitted) {
        onReviewSubmitted(response || {
          ...inspection,
          review_status: reviewAction === 'confirm' ? 'confirmed' : 'corrected',
          supervisor_class: payload.corrected_class,
          review_comment: payload.comment,
          reviewed_at: new Date().toISOString()
        });
      }
    } catch (err) {
      console.error('Review submission failed:', err);
      setErrorFeedback(
        getErrorMessage(
          err,
          'Failed to submit supervisor review to backend endpoint (/api/inspections/:id/review/).'
        )
      );
      setShowConfirmation(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const finalDeterminedClass = reviewAction === 'confirm' ? originalClass : correctedClass;

  return (
    <div
      className="modal fade show d-block"
      tabIndex="-1"
      style={{ backgroundColor: 'rgba(15, 23, 42, 0.75)', zIndex: 1060 }}
    >
      <div className="modal-dialog modal-lg modal-dialog-centered">
        <div className="modal-content border-0 shadow-lg">
          {/* Modal Header */}
          <div className="modal-header bg-white border-bottom py-3">
            <div>
              <div className="d-flex align-items-center gap-2 mb-1">
                <InspectionStatusBadge type="class" value={originalClass} />
                <span className="badge bg-light text-secondary border font-monospace">
                  ID: #{inspectionId}
                </span>
                <InspectionStatusBadge type="review" value={inspection.review_status || 'pending'} />
              </div>
              <h5 className="modal-title fw-bold text-dark mb-0">
                Supervisor Quality Inspection Audit
              </h5>
            </div>
            <button
              type="button"
              className="btn-close"
              onClick={onClose}
              disabled={isSubmitting}
              aria-label="Close"
            />
          </div>

          <div className="modal-body p-4 bg-light overflow-auto" style={{ maxHeight: '78vh' }}>
            {/* Feedback Alerts */}
            {successFeedback && (
              <div className="alert alert-success py-2 small d-flex align-items-center gap-2 mb-3">
                <CheckCircle2 size={16} />
                <span>{successFeedback}</span>
              </div>
            )}

            {errorFeedback && (
              <div className="alert alert-danger py-2 small d-flex align-items-center gap-2 mb-3">
                <AlertCircle size={16} />
                <span>{errorFeedback}</span>
              </div>
            )}

            {/* Inspection Visual & Telemetry */}
            <div className="row g-3 mb-3">
              {/* Image Preview */}
              <div className="col-12 col-md-5 text-center">
                <div className="border rounded bg-dark p-1 overflow-hidden h-100 d-flex align-items-center justify-content-center">
                  {inspection.image_url || inspection.thumbnail_url ? (
                    <img
                      src={inspection.image_url || inspection.thumbnail_url}
                      alt="Inspected plate"
                      className="img-fluid rounded"
                      style={{ maxHeight: '260px', width: '100%', objectFit: 'contain' }}
                    />
                  ) : (
                    <div className="p-4 text-muted small">No image preview stream available</div>
                  )}
                </div>
              </div>

              {/* Original AI Telemetry Details */}
              <div className="col-12 col-md-7">
                <div className="card card-industrial p-3 bg-white h-100">
                  <div className="d-flex align-items-center justify-content-between pb-2 mb-2 border-bottom">
                    <span className="text-muted small fw-semibold text-uppercase" style={{ fontSize: '0.72rem' }}>
                      Original AI Model Determination
                    </span>
                    <span className="badge bg-light text-dark border font-monospace" style={{ fontSize: '0.7rem' }}>
                      {modelVersion}
                    </span>
                  </div>

                  <div className="row g-2 small mb-2">
                    <div className="col-6">
                      <span className="text-secondary">Original AI Class:</span>
                      <div className="mt-1">
                        <InspectionStatusBadge type="class" value={originalClass} />
                      </div>
                    </div>

                    <div className="col-6">
                      <span className="text-secondary">Confidence Score:</span>
                      <div className="fw-bold fs-6 font-monospace text-dark">
                        {formatConfidence(confidence)}
                      </div>
                    </div>

                    <div className="col-6">
                      <span className="text-secondary">Target Product:</span>
                      <div className="fw-bold font-monospace text-primary">
                        {inspection.product_id || 'P-PLATE01'}
                      </div>
                    </div>

                    <div className="col-6">
                      <span className="text-secondary">Defect Probability:</span>
                      <div className="fw-bold font-monospace">
                        {defectProb !== undefined ? formatConfidence(defectProb) : 'N/A'}
                      </div>
                    </div>

                    <div className="col-6">
                      <span className="text-secondary">Operator / Engineer:</span>
                      <div className="fw-medium text-dark">
                        {inspection.engineer_name || 'Plant Engineer'}
                      </div>
                    </div>

                    <div className="col-6">
                      <span className="text-secondary">Submission Date:</span>
                      <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                        {formatDateTime(inspection.created_at)}
                      </div>
                    </div>
                  </div>

                  {/* Previous Supervisor Audit Display */}
                  {inspection.review_status && inspection.review_status !== 'pending' && (
                    <div className="p-2 rounded bg-light border mt-2 small">
                      <div className="fw-bold text-dark d-flex align-items-center gap-1 mb-1" style={{ fontSize: '0.75rem' }}>
                        <ShieldCheck size={13} className="text-success" /> Existing Supervisor Audit
                      </div>
                      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.75rem' }}>
                        <span>Supervisor Decision:</span>
                        <span className="fw-bold text-primary">{inspection.supervisor_class || inspection.review_status}</span>
                      </div>
                      {inspection.supervisor_name && (
                        <div className="text-muted" style={{ fontSize: '0.7rem' }}>
                          Audited by {inspection.supervisor_name} on {formatDateTime(inspection.reviewed_at)}
                        </div>
                      )}
                      {inspection.review_comment && (
                        <div className="mt-1 p-2 bg-white rounded border fst-italic text-secondary" style={{ fontSize: '0.74rem' }}>
                          "{inspection.review_comment}"
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Supervisor Action Form */}
            <div className="card card-industrial p-3 bg-white">
              <h6 className="fw-bold text-dark mb-3 pb-2 border-bottom d-flex align-items-center gap-2">
                <ShieldCheck size={16} className="text-primary" /> Supervisor Review Action
              </h6>

              <form onSubmit={handleOpenConfirmation}>
                {/* Action Radios: Confirm vs Correct */}
                <div className="mb-3">
                  <label className="form-label small fw-semibold text-secondary mb-2">Select Review Action:</label>
                  <div className="d-flex flex-column flex-sm-row gap-3">
                    <div
                      className={`p-3 rounded border flex-grow-1 cursor-pointer transition-all ${
                        reviewAction === 'confirm'
                          ? 'border-primary bg-primary bg-opacity-10'
                          : 'bg-light hover-shadow'
                      }`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setReviewAction('confirm')}
                    >
                      <div className="form-check mb-1">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="reviewAction"
                          id="actionConfirm"
                          value="confirm"
                          checked={reviewAction === 'confirm'}
                          onChange={() => setReviewAction('confirm')}
                        />
                        <label className="form-check-label fw-bold text-dark small" htmlFor="actionConfirm">
                          Confirm AI Prediction
                        </label>
                      </div>
                      <p className="text-muted small mb-0 ps-4" style={{ fontSize: '0.75rem' }}>
                        Verify and approve the model's determination as <strong>{originalClass}</strong>.
                      </p>
                    </div>

                    <div
                      className={`p-3 rounded border flex-grow-1 cursor-pointer transition-all ${
                        reviewAction === 'correct'
                          ? 'border-warning bg-warning bg-opacity-10'
                          : 'bg-light hover-shadow'
                      }`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setReviewAction('correct')}
                    >
                      <div className="form-check mb-1">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="reviewAction"
                          id="actionCorrect"
                          value="correct"
                          checked={reviewAction === 'correct'}
                          onChange={() => setReviewAction('correct')}
                        />
                        <label className="form-check-label fw-bold text-dark small" htmlFor="actionCorrect">
                          Correct AI Prediction
                        </label>
                      </div>
                      <p className="text-muted small mb-0 ps-4" style={{ fontSize: '0.75rem' }}>
                        Override model determination. The original prediction is preserved in audit records.
                      </p>
                    </div>
                  </div>
                </div>

                {/* If Correction is selected, choose correct class */}
                {reviewAction === 'correct' && (
                  <div className="mb-3 p-3 rounded bg-warning bg-opacity-10 border border-warning border-opacity-25">
                    <label className="form-label small fw-bold text-dark mb-2">
                      Supervisor Corrected Determination:
                    </label>
                    <div className="d-flex gap-3">
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="correctedClass"
                          id="classNormal"
                          value="Normal"
                          checked={correctedClass === 'Normal'}
                          onChange={(e) => setCorrectedClass(e.target.value)}
                        />
                        <label className="form-check-label fw-semibold text-success small" htmlFor="classNormal">
                          Normal (Component acceptable)
                        </label>
                      </div>
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="radio"
                          name="correctedClass"
                          id="classDefective"
                          value="Defective"
                          checked={correctedClass === 'Defective'}
                          onChange={(e) => setCorrectedClass(e.target.value)}
                        />
                        <label className="form-check-label fw-semibold text-danger small" htmlFor="classDefective">
                          Defective (Defects present)
                        </label>
                      </div>
                    </div>
                  </div>
                )}

                {/* Review Comment */}
                <div className="mb-3">
                  <label className="form-label small fw-semibold text-secondary">
                    Review Comment & Quality Notes (Optional)
                  </label>
                  <textarea
                    rows={2}
                    className="form-control form-control-sm"
                    placeholder="Enter technical justification or reason for confirmation/correction..."
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    disabled={isSubmitting}
                  />
                </div>

                <div className="d-flex justify-content-end gap-2 pt-2 border-top">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary"
                    onClick={onClose}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-sm btn-primary-industrial d-flex align-items-center gap-1"
                    disabled={isSubmitting}
                  >
                    <ShieldCheck size={15} /> Review Inspection
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Confirmation Sub-Modal Dialog */}
          {showConfirmation && (
            <div
              className="modal fade show d-block"
              tabIndex="-1"
              style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', zIndex: 1070 }}
            >
              <div className="modal-dialog modal-dialog-centered modal-sm">
                <div className="modal-content border-0 shadow">
                  <div className="modal-header py-2 bg-light">
                    <h6 className="modal-title fw-bold text-dark mb-0">Confirm Review Submission</h6>
                    <button
                      type="button"
                      className="btn-close"
                      onClick={() => setShowConfirmation(false)}
                      disabled={isSubmitting}
                    />
                  </div>
                  <div className="modal-body p-3 small">
                    <p className="mb-2">Are you sure you want to submit this audit determination?</p>
                    <div className="p-2 bg-light rounded border mb-2">
                      <div>
                        Action: <strong>{reviewAction === 'confirm' ? 'Confirm AI' : 'Correct AI'}</strong>
                      </div>
                      <div>
                        Original AI Class: <strong>{originalClass}</strong>
                      </div>
                      <div>
                        Supervisor Final Class: <strong className="text-primary">{finalDeterminedClass}</strong>
                      </div>
                    </div>
                    <div className="text-muted" style={{ fontSize: '0.72rem' }}>
                      The original AI prediction will remain permanently logged in the audit trail.
                    </div>
                  </div>
                  <div className="modal-footer py-2 bg-light">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => setShowConfirmation(false)}
                      disabled={isSubmitting}
                    >
                      Back
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-primary-industrial d-flex align-items-center gap-1"
                      onClick={handleFinalSubmit}
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <>
                          <span className="spinner-border spinner-border-sm" />
                          <span>Submitting...</span>
                        </>
                      ) : (
                        <span>Confirm & Submit</span>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
