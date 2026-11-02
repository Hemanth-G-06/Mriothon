import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Search,
  Filter,
  Eye,
  CheckCircle2,
  AlertOctagon,
  Clock,
  Layers,
  RefreshCw,
  User,
  Package,
  Calendar,
  AlertCircle
} from 'lucide-react';
import { inspectionService } from '../../services/inspectionService';
import InspectionStatusBadge from '../../components/inspection/InspectionStatusBadge';
import InspectionDetailModal from './InspectionDetailModal';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

/**
 * Supervisor Visual Inspection Review Page
 * Allows supervisors to audit all completed AI plate inspections, confirm or correct predictions,
 * and track model quality calibration.
 */
export default function InspectionReviewPage() {
  const [inspections, setInspections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [selectedInspection, setSelectedInspection] = useState(null);

  // Filters State
  const [filters, setFilters] = useState({
    search: '',
    review_status: 'all',
    predicted_class: 'all',
    date: ''
  });

  const fetchInspections = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const response = await inspectionService.getPendingReviews(filters);
      const list = response?.results || (Array.isArray(response) ? response : []);
      setInspections(list);
    } catch (err) {
      console.warn('Supervisor inspections fetch error:', err);
      setErrorMessage(
        getErrorMessage(
          err,
          'Unable to load inspection review queue from the backend endpoint (/api/supervisor/inspections/).'
        )
      );
      setInspections([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInspections();
  }, [filters]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleResetFilters = () => {
    setFilters({
      search: '',
      review_status: 'all',
      predicted_class: 'all',
      date: ''
    });
  };

  const handleReviewSubmitted = (updatedRecord) => {
    // Update local record in table
    setInspections((prev) =>
      prev.map((item) => (item.id === updatedRecord.id ? { ...item, ...updatedRecord } : item))
    );
    setSelectedInspection(null);
  };

  const formatConfidence = (val) => {
    if (val === undefined || val === null) return '-';
    const num = Number(val);
    if (isNaN(num)) return String(val);
    if (num <= 1) return `${(num * 100).toFixed(1)}%`;
    return `${num.toFixed(1)}%`;
  };

  return (
    <div className="container-fluid p-0">
      {/* Page Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <div className="d-flex align-items-center gap-2 mb-1">
            <h4 className="fw-bold text-dark mb-0">Visual Inspection Review</h4>
            <span className="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 d-flex align-items-center gap-1 small">
              <ShieldCheck size={12} /> Quality Audit & Override Authority
            </span>
          </div>
          <p className="text-muted small mb-0">
            Audit AI computer vision defect classifications, verify normal vs. defective verdicts, and calibrate production reliability.
          </p>
        </div>
        <div>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
            onClick={fetchInspections}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spinner-border spinner-border-sm' : ''} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {/* Error notification */}
      {errorMessage && (
        <div className="alert alert-warning py-2 small d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center gap-2">
            <Clock size={16} className="text-warning flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button className="btn btn-sm btn-link text-dark p-0" onClick={() => setErrorMessage(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-2 align-items-center">
          {/* Search by ID or Engineer */}
          <div className="col-12 col-md-3">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                name="search"
                className="form-control border-start-0"
                placeholder="Search ID, Engineer, Product..."
                value={filters.search}
                onChange={handleFilterChange}
              />
            </div>
          </div>

          {/* Review Status Filter */}
          <div className="col-6 col-md-3">
            <select
              name="review_status"
              className="form-select form-select-sm"
              value={filters.review_status}
              onChange={handleFilterChange}
            >
              <option value="all">All Review States</option>
              <option value="pending">Pending Supervisor Review</option>
              <option value="confirmed">Confirmed</option>
              <option value="corrected">Corrected</option>
            </select>
          </div>

          {/* Predicted Class Filter */}
          <div className="col-6 col-md-3">
            <select
              name="predicted_class"
              className="form-select form-select-sm"
              value={filters.predicted_class}
              onChange={handleFilterChange}
            >
              <option value="all">All Predictions</option>
              <option value="Normal">Normal</option>
              <option value="Defective">Defective</option>
            </select>
          </div>

          {/* Date Filter */}
          <div className="col-6 col-md-2">
            <input
              type="date"
              name="date"
              className="form-control form-control-sm"
              value={filters.date}
              onChange={handleFilterChange}
            />
          </div>

          {/* Reset */}
          <div className="col-6 col-md-1 text-md-end">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary w-100"
              onClick={handleResetFilters}
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Inspections Table */}
      {loading ? (
        <LoadingSpinner text="Retrieving visual quality inspection records..." size="lg" />
      ) : inspections.length === 0 ? (
        <EmptyState
          title="No Inspection Records Found"
          description="No visual inspection records match your current filter selection."
          icon={ShieldCheck}
          actionButton={
            <button className="btn btn-sm btn-outline-primary mt-2" onClick={handleResetFilters}>
              Reset Filters
            </button>
          }
        />
      ) : (
        <div className="card card-industrial bg-white overflow-hidden mb-4">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th className="small text-secondary fw-semibold">Preview</th>
                  <th className="small text-secondary fw-semibold">Inspection ID</th>
                  <th className="small text-secondary fw-semibold">Engineer</th>
                  <th className="small text-secondary fw-semibold">Product ID</th>
                  <th className="small text-secondary fw-semibold text-center">Original AI Prediction</th>
                  <th className="small text-secondary fw-semibold text-center">AI Confidence</th>
                  <th className="small text-secondary fw-semibold text-center">Review Status</th>
                  <th className="small text-secondary fw-semibold">Submission Date</th>
                  <th className="small text-secondary fw-semibold text-end">Action</th>
                </tr>
              </thead>
              <tbody>
                {inspections.map((item) => (
                  <tr key={item.id}>
                    {/* Image Preview Thumbnail */}
                    <td style={{ width: 60 }}>
                      <div
                        className="rounded bg-dark d-flex align-items-center justify-content-center overflow-hidden border"
                        style={{ width: 44, height: 44 }}
                      >
                        {item.image_url || item.thumbnail_url ? (
                          <img
                            src={item.image_url || item.thumbnail_url}
                            alt="Plate inspection preview"
                            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'cover' }}
                          />
                        ) : (
                          <Layers size={16} className="text-secondary" />
                        )}
                      </div>
                    </td>

                    {/* Inspection ID */}
                    <td className="small font-monospace text-dark fw-bold">
                      #{item.id}
                    </td>

                    {/* Engineer */}
                    <td className="small text-dark fw-medium">
                      {item.engineer_name || 'Plant Engineer'}
                    </td>

                    {/* Product ID */}
                    <td className="small font-monospace text-primary fw-semibold">
                      {item.product_id || 'P-PLATE01'}
                    </td>

                    {/* Original AI Prediction */}
                    <td className="text-center">
                      <InspectionStatusBadge type="class" value={item.predicted_class || item.prediction} />
                    </td>

                    {/* AI Confidence */}
                    <td className="text-center small font-monospace fw-bold text-dark">
                      {formatConfidence(item.confidence)}
                    </td>

                    {/* Review Status */}
                    <td className="text-center">
                      <InspectionStatusBadge type="review" value={item.review_status || 'pending'} />
                    </td>

                    {/* Submission Timestamp */}
                    <td className="small text-muted" style={{ whiteSpace: 'nowrap' }}>
                      {formatDateTime(item.created_at)}
                    </td>

                    {/* Actions */}
                    <td className="text-end">
                      <button
                        type="button"
                        className="btn btn-sm btn-primary-industrial d-inline-flex align-items-center gap-1"
                        style={{ fontSize: '0.78rem' }}
                        onClick={() => setSelectedInspection(item)}
                      >
                        <Eye size={13} /> Audit Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Supervisor Inspection Detail & Review Modal */}
      <InspectionDetailModal
        isOpen={!!selectedInspection}
        inspection={selectedInspection}
        onClose={() => setSelectedInspection(null)}
        onReviewSubmitted={handleReviewSubmitted}
      />
    </div>
  );
}
