import React from 'react';
import {
  CheckCircle2,
  AlertOctagon,
  Cpu,
  Calendar,
  Hash,
  Activity,
  Layers,
  FileCheck,
  ShieldCheck,
  Percent
} from 'lucide-react';
import InspectionStatusBadge from './InspectionStatusBadge';
import { formatDateTime } from '../../utils/formatters';

/**
 * InspectionResultCard Component
 * Displays the verified inspection outcome returned by the AI inspection backend.
 */
export default function InspectionResultCard({ result, onReset }) {
  if (!result) return null;

  // Normalized values
  const predictedClass = result.predicted_class || result.prediction || 'Unknown';
  const isNormal = predictedClass.toLowerCase() === 'normal';
  const isDefective = predictedClass.toLowerCase() === 'defective';

  // Format confidence to percentage string
  const formatPercentage = (val) => {
    if (val === undefined || val === null) return 'N/A';
    const num = Number(val);
    if (isNaN(num)) return String(val);
    if (num <= 1) {
      return `${(num * 100).toFixed(1)}%`;
    }
    return `${num.toFixed(1)}%`;
  };

  const confidenceDisplay = formatPercentage(result.confidence);
  const defectProbDisplay =
    result.defect_probability !== undefined
      ? formatPercentage(result.defect_probability)
      : isDefective
      ? confidenceDisplay
      : formatPercentage(1 - (Number(result.confidence) || 1));

  const modelVersion = result.model_version || 'BIT-PLATE-CV-1.0';
  const inspectionId = result.id || result.inspection_id || 'INSP-' + Date.now();
  const timestamp = result.created_at || result.timestamp || new Date().toISOString();
  const productId = result.product_id || 'P-PLATE01';
  const processingStatus = result.status || 'Completed';

  return (
    <div className="card card-industrial bg-white p-4 overflow-hidden border">
      {/* Top Banner: Verdict */}
      <div
        className={`p-3 rounded-3 d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-2 mb-4 ${
          isNormal
            ? 'bg-success bg-opacity-10 border border-success border-opacity-25'
            : isDefective
            ? 'bg-danger bg-opacity-10 border border-danger border-opacity-25'
            : 'bg-light border'
        }`}
      >
        <div className="d-flex align-items-center gap-3">
          <div
            className={`p-2 rounded-circle ${
              isNormal ? 'bg-success text-white' : isDefective ? 'bg-danger text-white' : 'bg-secondary text-white'
            }`}
          >
            {isNormal ? <CheckCircle2 size={28} /> : <AlertOctagon size={28} />}
          </div>
          <div>
            <div className="text-muted small fw-semibold text-uppercase" style={{ fontSize: '0.72rem' }}>
              AI Inspection Outcome
            </div>
            <h4
              className={`mb-0 fw-bold ${
                isNormal ? 'text-success' : isDefective ? 'text-danger' : 'text-dark'
              }`}
            >
              Class: {predictedClass}
            </h4>
          </div>
        </div>

        <div className="d-flex flex-wrap align-items-center gap-2 text-sm-end">
          <div className="pe-sm-3 border-sm-end">
            <div className="text-muted small" style={{ fontSize: '0.7rem' }}>Confidence</div>
            <div className="fw-bold text-dark fs-5">{confidenceDisplay}</div>
          </div>
          <InspectionStatusBadge type="processing" value={processingStatus} />
        </div>
      </div>

      <div className="row g-4 align-items-start">
        {/* Left: Original Inspected Image Preview */}
        <div className="col-12 col-lg-5 text-center">
          <div className="border rounded bg-dark p-1 overflow-hidden position-relative">
            {result.image_url || result.previewUrl ? (
              <img
                src={result.image_url || result.previewUrl}
                alt="Inspected Plate"
                className="img-fluid rounded"
                style={{ maxHeight: '320px', width: '100%', objectFit: 'contain' }}
              />
            ) : (
              <div
                className="d-flex flex-column align-items-center justify-content-center text-muted p-5"
                style={{ height: '240px' }}
              >
                <Layers size={36} className="mb-2" />
                <span className="small">No image preview stream available</span>
              </div>
            )}
            <div
              className="position-absolute bottom-0 start-0 m-2 badge bg-dark bg-opacity-75 text-white"
              style={{ fontSize: '0.7rem' }}
            >
              Product ID: {productId}
            </div>
          </div>
        </div>

        {/* Right: Technical Inspection Telemetry */}
        <div className="col-12 col-lg-7">
          <h6 className="fw-bold text-dark mb-3 pb-2 border-bottom d-flex align-items-center gap-2">
            <Activity size={17} className="text-primary" /> Technical Inspection Parameters
          </h6>

          <div className="row g-3 mb-3">
            <div className="col-6 col-sm-6">
              <div className="card p-2 bg-light border-0">
                <span className="text-muted small" style={{ fontSize: '0.72rem' }}>INSPECTION ID</span>
                <span className="fw-bold font-monospace text-dark text-truncate" title={inspectionId}>
                  #{inspectionId}
                </span>
              </div>
            </div>

            <div className="col-6 col-sm-6">
              <div className="card p-2 bg-light border-0">
                <span className="text-muted small" style={{ fontSize: '0.72rem' }}>PRODUCT TARGET</span>
                <span className="fw-bold text-primary font-monospace">{productId}</span>
              </div>
            </div>

            <div className="col-6 col-sm-6">
              <div className="card p-2 bg-light border-0">
                <span className="text-muted small" style={{ fontSize: '0.72rem' }}>AI CLASSIFIER MODEL</span>
                <span className="fw-bold text-dark font-monospace">{modelVersion}</span>
              </div>
            </div>

            <div className="col-6 col-sm-6">
              <div className="card p-2 bg-light border-0">
                <span className="text-muted small" style={{ fontSize: '0.72rem' }}>DEFECT PROBABILITY</span>
                <span className={`fw-bold font-monospace ${isDefective ? 'text-danger' : 'text-success'}`}>
                  {defectProbDisplay}
                </span>
              </div>
            </div>

            <div className="col-12">
              <div className="card p-2 bg-light border-0">
                <span className="text-muted small" style={{ fontSize: '0.72rem' }}>SUBMISSION TIMESTAMP</span>
                <span className="fw-medium text-dark small">{formatDateTime(timestamp)}</span>
              </div>
            </div>
          </div>

          {/* Supervisor Review Information (if present) */}
          {result.review_status && result.review_status !== 'pending' && (
            <div className="alert alert-info py-2 px-3 small border mb-3">
              <div className="d-flex align-items-center gap-1 fw-bold mb-1">
                <ShieldCheck size={14} /> Supervisor Audit Feedback
              </div>
              <div className="d-flex justify-content-between mb-1">
                <span>Supervisor Decision:</span>
                <span className="fw-semibold">{result.supervisor_class || result.review_status}</span>
              </div>
              {result.supervisor_name && (
                <div className="text-muted" style={{ fontSize: '0.72rem' }}>
                  Reviewed by: <strong>{result.supervisor_name}</strong> on {formatDateTime(result.reviewed_at)}
                </div>
              )}
              {result.review_comment && (
                <div className="mt-1 p-2 bg-white rounded border fst-italic">
                  "{result.review_comment}"
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          {onReset && (
            <div className="pt-2 border-top">
              <button
                type="button"
                className="btn btn-sm btn-outline-primary"
                onClick={onReset}
              >
                Inspect Another Plate Image
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
