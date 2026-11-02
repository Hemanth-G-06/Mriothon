import React, { useState, useEffect } from 'react';
import {
  History,
  Search,
  Filter,
  Eye,
  Calendar,
  Layers,
  CheckCircle2,
  AlertOctagon,
  Clock,
  ShieldCheck,
  Package,
  RefreshCw,
  X
} from 'lucide-react';
import { inspectionService } from '../../services/inspectionService';
import InspectionStatusBadge from '../../components/inspection/InspectionStatusBadge';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

/**
 * InspectionHistoryPage
 * Displays persistent visual quality inspection records scoped to the authenticated engineer.
 */
export default function InspectionHistoryPage() {
  const [inspections, setInspections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Filters State
  const [filters, setFilters] = useState({
    search: '',
    predicted_class: 'all',
    status: 'all',
    review_status: 'all',
    date: '',
    page: 1
  });

  const [totalCount, setTotalCount] = useState(0);

  const fetchHistory = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const response = await inspectionService.getInspectionHistory(filters);
      const list = response?.results || (Array.isArray(response) ? response : []);
      setInspections(list);
      setTotalCount(response?.count || list.length);
    } catch (err) {
      console.warn('Inspection history fetch error:', err);
      setErrorMessage(
        getErrorMessage(
          err,
          'Unable to load inspection history from the backend endpoint (/api/inspections/).'
        )
      );
      setInspections([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [filters]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value, page: 1 }));
  };

  const handleResetFilters = () => {
    setFilters({
      search: '',
      predicted_class: 'all',
      status: 'all',
      review_status: 'all',
      date: '',
      page: 1
    });
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
            <h4 className="fw-bold text-dark mb-0">Inspection History</h4>
            <span className="badge bg-secondary bg-opacity-10 text-secondary border small">
              Operator Log
            </span>
          </div>
          <p className="text-muted small mb-0">
            Review past automated plate quality evaluations, model predictions, confidence telemetry, and supervisor audits.
          </p>
        </div>
        <div>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
            onClick={fetchHistory}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spinner-border spinner-border-sm' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error alert */}
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
          {/* Search by ID */}
          <div className="col-12 col-md-3">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                name="search"
                className="form-control border-start-0"
                placeholder="Search Inspection ID..."
                value={filters.search}
                onChange={handleFilterChange}
              />
            </div>
          </div>

          {/* Predicted Class Filter */}
          <div className="col-6 col-md-2">
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

          {/* Processing Status Filter */}
          <div className="col-6 col-md-2">
            <select
              name="status"
              className="form-select form-select-sm"
              value={filters.status}
              onChange={handleFilterChange}
            >
              <option value="all">All Processing</option>
              <option value="Completed">Completed</option>
              <option value="Processing">Processing</option>
              <option value="Failed">Failed</option>
            </select>
          </div>

          {/* Review Status Filter */}
          <div className="col-6 col-md-2">
            <select
              name="review_status"
              className="form-select form-select-sm"
              value={filters.review_status}
              onChange={handleFilterChange}
            >
              <option value="all">All Reviews</option>
              <option value="pending">Pending Review</option>
              <option value="confirmed">Confirmed</option>
              <option value="corrected">Corrected</option>
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

          {/* Reset button */}
          <div className="col-12 col-md-1 text-md-end">
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

      {/* History Table */}
      {loading ? (
        <LoadingSpinner text="Loading inspection logs..." size="lg" />
      ) : inspections.length === 0 ? (
        <EmptyState
          title="No Inspection Records Found"
          description={
            filters.search || filters.predicted_class !== 'all' || filters.status !== 'all' || filters.review_status !== 'all' || filters.date
              ? 'No inspection records matched the selected criteria.'
              : 'You have not submitted any visual quality plate inspections yet.'
          }
          icon={Layers}
          actionButton={
            <button className="btn btn-sm btn-outline-primary mt-2" onClick={handleResetFilters}>
              Clear Filters
            </button>
          }
        />
      ) : (
        <div className="card card-industrial bg-white overflow-hidden mb-4">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th className="small text-secondary fw-semibold">Thumbnail</th>
                  <th className="small text-secondary fw-semibold">Inspection ID</th>
                  <th className="small text-secondary fw-semibold">Product ID</th>
                  <th className="small text-secondary fw-semibold text-center">Prediction</th>
                  <th className="small text-secondary fw-semibold text-center">Confidence</th>
                  <th className="small text-secondary fw-semibold text-center">Status</th>
                  <th className="small text-secondary fw-semibold text-center">Review</th>
                  <th className="small text-secondary fw-semibold">Submitted</th>
                  <th className="small text-secondary fw-semibold text-end">Action</th>
                </tr>
              </thead>
              <tbody>
                {inspections.map((item) => (
                  <tr key={item.id}>
                    {/* Thumbnail */}
                    <td style={{ width: 60 }}>
                      <div
                        className="rounded bg-dark d-flex align-items-center justify-content-center overflow-hidden border"
                        style={{ width: 44, height: 44 }}
                      >
                        {item.image_url || item.thumbnail_url ? (
                          <img
                            src={item.image_url || item.thumbnail_url}
                            alt="Plate thumbnail"
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

                    {/* Product ID */}
                    <td className="small font-monospace text-primary fw-semibold">
                      {item.product_id || 'P-PLATE01'}
                    </td>

                    {/* Predicted Class */}
                    <td className="text-center">
                      <InspectionStatusBadge type="class" value={item.predicted_class || item.prediction} />
                    </td>

                    {/* Confidence */}
                    <td className="text-center small font-monospace fw-bold text-dark">
                      {formatConfidence(item.confidence)}
                    </td>

                    {/* Processing Status */}
                    <td className="text-center">
                      <InspectionStatusBadge type="processing" value={item.status || 'Completed'} />
                    </td>

                    {/* Review Status */}
                    <td className="text-center">
                      <InspectionStatusBadge type="review" value={item.review_status || 'pending'} />
                    </td>

                    {/* Timestamp */}
                    <td className="small text-muted" style={{ whiteSpace: 'nowrap' }}>
                      {formatDateTime(item.created_at)}
                    </td>

                    {/* Action */}
                    <td className="text-end">
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1"
                        style={{ fontSize: '0.78rem' }}
                        onClick={() => setSelectedRecord(item)}
                      >
                        <Eye size={13} /> Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Inspection Detail Modal */}
      {selectedRecord && (
        <div
          className="modal fade show d-block"
          tabIndex="-1"
          style={{ backgroundColor: 'rgba(15, 23, 42, 0.75)', zIndex: 1050 }}
        >
          <div className="modal-dialog modal-lg modal-dialog-centered">
            <div className="modal-content border-0 shadow-lg">
              <div className="modal-header bg-white border-bottom py-3">
                <div className="d-flex align-items-center gap-2">
                  <InspectionStatusBadge type="class" value={selectedRecord.predicted_class || selectedRecord.prediction} />
                  <span className="badge bg-light text-secondary border font-monospace">
                    ID: #{selectedRecord.id}
                  </span>
                </div>
                <button type="button" className="btn-close" onClick={() => setSelectedRecord(null)} />
              </div>

              <div className="modal-body p-4 bg-light">
                <div className="row g-4">
                  {/* Left: Image preview */}
                  <div className="col-12 col-md-5 text-center">
                    <div className="border rounded bg-dark p-1 overflow-hidden">
                      {selectedRecord.image_url || selectedRecord.thumbnail_url ? (
                        <img
                          src={selectedRecord.image_url || selectedRecord.thumbnail_url}
                          alt="Plate inspection"
                          className="img-fluid rounded"
                          style={{ maxHeight: '280px', objectFit: 'contain' }}
                        />
                      ) : (
                        <div className="p-4 text-muted small">No image preview stream</div>
                      )}
                    </div>
                  </div>

                  {/* Right: Telemetry Details */}
                  <div className="col-12 col-md-7">
                    <div className="card card-industrial p-3 bg-white mb-3">
                      <h6 className="fw-bold text-dark mb-2 pb-2 border-bottom small text-uppercase">
                        Classification Telemetry
                      </h6>
                      <div className="row g-2 small">
                        <div className="col-6">
                          <span className="text-secondary">Predicted Class:</span>
                          <div className="fw-bold">{selectedRecord.predicted_class || selectedRecord.prediction || 'N/A'}</div>
                        </div>
                        <div className="col-6">
                          <span className="text-secondary">Model Confidence:</span>
                          <div className="fw-bold font-monospace">{formatConfidence(selectedRecord.confidence)}</div>
                        </div>
                        <div className="col-6">
                          <span className="text-secondary">Target Product:</span>
                          <div className="fw-bold font-monospace text-primary">{selectedRecord.product_id || 'P-PLATE01'}</div>
                        </div>
                        <div className="col-6">
                          <span className="text-secondary">Model Version:</span>
                          <div className="fw-bold font-monospace">{selectedRecord.model_version || 'BIT-PLATE-CV-1.0'}</div>
                        </div>
                        <div className="col-12">
                          <span className="text-secondary">Submission Timestamp:</span>
                          <div className="fw-medium text-dark">{formatDateTime(selectedRecord.created_at)}</div>
                        </div>
                      </div>
                    </div>

                    {/* Supervisor Review Details if present */}
                    <div className="card card-industrial p-3 bg-white">
                      <h6 className="fw-bold text-dark mb-2 pb-2 border-bottom small text-uppercase d-flex align-items-center gap-1">
                        <ShieldCheck size={14} className="text-primary" /> Supervisor Review Status
                      </h6>
                      <div className="small">
                        <div className="d-flex justify-content-between mb-1">
                          <span className="text-secondary">Audit Status:</span>
                          <InspectionStatusBadge type="review" value={selectedRecord.review_status || 'pending'} />
                        </div>
                        {selectedRecord.supervisor_class && (
                          <div className="d-flex justify-content-between mb-1">
                            <span className="text-secondary">Supervisor Determination:</span>
                            <span className="fw-bold">{selectedRecord.supervisor_class}</span>
                          </div>
                        )}
                        {selectedRecord.supervisor_name && (
                          <div className="text-muted" style={{ fontSize: '0.74rem' }}>
                            Reviewed by: <strong>{selectedRecord.supervisor_name}</strong> on {formatDateTime(selectedRecord.reviewed_at)}
                          </div>
                        )}
                        {selectedRecord.review_comment && (
                          <div className="mt-2 p-2 bg-light rounded border fst-italic" style={{ fontSize: '0.78rem' }}>
                            "{selectedRecord.review_comment}"
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer bg-white py-2 px-4">
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => setSelectedRecord(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
