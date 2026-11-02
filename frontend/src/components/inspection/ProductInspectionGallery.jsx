import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Package,
  Layers,
  Search,
  Filter,
  CheckCircle2,
  AlertOctagon,
  Clock,
  ShieldCheck,
  User,
  Calendar,
  Eye,
  RefreshCw,
  AlertCircle,
  Cpu,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Edit3
} from 'lucide-react';
import { inspectionService } from '../../services/inspectionService';
import InspectionStatusBadge from './InspectionStatusBadge';
import LoadingSpinner from '../common/LoadingSpinner';
import EmptyState from '../common/EmptyState';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

/**
 * ProductInspectionGallery Component
 *
 * Displays detailed specifications of a registered product along with the
 * complete gallery of actual Engineer-uploaded inspection images, AI inference
 * outcomes, and supervisor calibration records.
 *
 * Props:
 * - product: Object { id, name, model_version, category, description, created_at, ... }
 * - onBack: () => void
 */
export default function ProductInspectionGallery({ product, onBack }) {
  const [allInspections, setAllInspections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  // Search & Filter state
  const [search, setSearch] = useState('');
  const [classFilter, setClassFilter] = useState('all'); // 'all', 'Normal', 'Defective'
  const [reviewFilter, setReviewFilter] = useState('all'); // 'all', 'pending', 'reviewed'

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 9;

  // Selected inspection for large preview modal
  const [activeModalInspection, setActiveModalInspection] = useState(null);

  const productId = product?.id || 'P-PLATE01';

  const fetchProductInspections = async () => {
    if (!productId) return;
    setLoading(true);
    setErrorMessage(null);

    try {
      // Query backend for inspections belonging to this specific product
      const response = await inspectionService.getInspectionsByProduct(productId);
      const list = response?.results || (Array.isArray(response) ? response : []);

      // Authoritatively ensure all records match this product
      const productScoped = list.filter(
        (item) => !item.product_id || String(item.product_id).toUpperCase() === String(productId).toUpperCase()
      );

      setAllInspections(productScoped);
    } catch (err) {
      console.warn('Failed to load inspections for product:', err);
      setErrorMessage(
        getErrorMessage(
          err,
          `Unable to retrieve inspection gallery from backend endpoint (/api/inspections/?product_id=${productId}). Verify the Django inspection service is running.`
        )
      );
      setAllInspections([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProductInspections();
  }, [productId]);

  // Compute live statistics directly from actual inspection records
  const totalCount = allInspections.length;
  const normalCount = allInspections.filter(
    (i) => (i.predicted_class || i.prediction || '').toLowerCase() === 'normal'
  ).length;
  const defectiveCount = allInspections.filter(
    (i) => (i.predicted_class || i.prediction || '').toLowerCase() === 'defective'
  ).length;
  const pendingCount = allInspections.filter((i) => {
    const rev = (i.review_status || '').toLowerCase();
    const proc = (i.status || '').toLowerCase();
    return rev === 'pending' || proc === 'processing' || proc === 'queued';
  }).length;
  const reviewedCount = allInspections.filter((i) => {
    const rev = (i.review_status || '').toLowerCase();
    return rev === 'confirmed' || rev === 'corrected';
  }).length;

  // Format confidence percentage
  const formatConfidence = (val) => {
    if (val === undefined || val === null) return 'N/A';
    const num = Number(val);
    if (isNaN(num)) return String(val);
    if (num <= 1) return `${(num * 100).toFixed(1)}%`;
    return `${num.toFixed(1)}%`;
  };

  // Client-side filtering
  const filteredInspections = allInspections.filter((item) => {
    // 1. Search by ID or Engineer name
    if (search.trim()) {
      const q = search.toLowerCase();
      const matchId = String(item.id || '').toLowerCase().includes(q);
      const matchEngineer = String(item.engineer_name || item.engineer || '').toLowerCase().includes(q);
      if (!matchId && !matchEngineer) return false;
    }

    // 2. Class filter (Normal / Defective)
    if (classFilter !== 'all') {
      const itemClass = (item.predicted_class || item.prediction || '').toLowerCase();
      if (itemClass !== classFilter.toLowerCase()) return false;
    }

    // 3. Review filter
    if (reviewFilter === 'pending') {
      const rev = (item.review_status || 'pending').toLowerCase();
      if (rev !== 'pending') return false;
    } else if (reviewFilter === 'reviewed') {
      const rev = (item.review_status || '').toLowerCase();
      if (rev !== 'confirmed' && rev !== 'corrected') return false;
    }

    return true;
  });

  // Pagination calculation
  const totalPages = Math.ceil(filteredInspections.length / ITEMS_PER_PAGE) || 1;
  const paginatedInspections = filteredInspections.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  const handleResetFilters = () => {
    setSearch('');
    setClassFilter('all');
    setReviewFilter('all');
    setCurrentPage(1);
  };

  return (
    <div className="w-100">
      {/* Top Navigation & Breadcrumb */}
      <div className="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center mb-4 gap-3">
        <div className="d-flex align-items-center gap-2">
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm d-flex align-items-center gap-1"
            onClick={onBack}
          >
            <ArrowLeft size={15} /> Back to Product Catalog
          </button>
          <span className="text-muted small">|</span>
          <span className="text-secondary small">Product Registry &bull; Details & Inspection Gallery</span>
        </div>

        <button
          type="button"
          className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
          onClick={fetchProductInspections}
          disabled={loading}
        >
          <RefreshCw size={13} className={loading ? 'spinner-border spinner-border-sm' : ''} />
          <span>Refresh Inspections</span>
        </button>
      </div>

      {/* Product Overview Header Card */}
      <div className="card card-industrial p-4 bg-white mb-4">
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-start gap-3 pb-3 mb-3 border-bottom">
          <div>
            <div className="d-flex align-items-center gap-2 mb-1">
              <span className="badge bg-primary font-monospace fs-6 px-2 py-1">
                {product.id}
              </span>
              <span className="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 small">
                {product.status || 'Active Catalog'}
              </span>
            </div>
            <h4 className="fw-bold text-dark mb-1">{product.name}</h4>
            <p className="text-muted small mb-0">
              {product.description || 'Precision manufactured industrial component evaluated by computer vision models.'}
            </p>
          </div>

          <div className="p-2 rounded bg-light border text-muted small text-md-end" style={{ fontSize: '0.75rem' }}>
            <div>Registered: <strong className="text-dark">{formatDateTime(product.created_at)}</strong></div>
            <div>AI Model: <strong className="text-dark font-monospace">{product.model_version || 'BIT-PLATE-CV-1.0'}</strong></div>
            <div>Category: <strong className="text-dark">{product.category || 'Milled Components'}</strong></div>
          </div>
        </div>

        {/* Live KPI Cards calculated from actual backend inspection records */}
        <div className="row g-2 text-center">
          <div className="col-6 col-sm-4 col-xl">
            <div className="p-2 rounded bg-light border h-100">
              <div className="text-muted small" style={{ fontSize: '0.7rem' }}>TOTAL INSPECTIONS</div>
              <div className="fw-bold text-dark fs-5">{totalCount}</div>
            </div>
          </div>

          <div className="col-6 col-sm-4 col-xl">
            <div className="p-2 rounded bg-success bg-opacity-10 border border-success border-opacity-25 text-success h-100">
              <div className="small" style={{ fontSize: '0.7rem' }}>NORMAL PREDICTIONS</div>
              <div className="fw-bold fs-5">{normalCount}</div>
            </div>
          </div>

          <div className="col-6 col-sm-4 col-xl">
            <div className="p-2 rounded bg-danger bg-opacity-10 border border-danger border-opacity-25 text-danger h-100">
              <div className="small" style={{ fontSize: '0.7rem' }}>DEFECTIVE PREDICTIONS</div>
              <div className="fw-bold fs-5">{defectiveCount}</div>
            </div>
          </div>

          <div className="col-6 col-sm-6 col-xl">
            <div className="p-2 rounded bg-warning bg-opacity-10 border border-warning border-opacity-25 text-warning-emphasis h-100">
              <div className="small" style={{ fontSize: '0.7rem' }}>PENDING REVIEW</div>
              <div className="fw-bold fs-5">{pendingCount}</div>
            </div>
          </div>

          <div className="col-6 col-sm-6 col-xl">
            <div className="p-2 rounded bg-info bg-opacity-10 border border-info border-opacity-25 text-info h-100">
              <div className="small" style={{ fontSize: '0.7rem' }}>REVIEWED AUDITS</div>
              <div className="fw-bold fs-5">{reviewedCount}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Backend API Error Notification */}
      {errorMessage && (
        <div className="alert alert-warning py-3 small d-flex align-items-start justify-content-between mb-4">
          <div className="d-flex align-items-start gap-2">
            <AlertCircle size={18} className="text-warning flex-shrink-0 mt-1" />
            <div>
              <div className="fw-bold mb-1">Inspection Stream Notice</div>
              <div>{errorMessage}</div>
            </div>
          </div>
          <button className="btn btn-sm btn-link text-dark p-0 ms-2" onClick={() => setErrorMessage(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Gallery Filter & Search Toolbar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-2 align-items-center">
          {/* Keyword Search */}
          <div className="col-12 col-md-4">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                className="form-control border-start-0"
                placeholder="Search by Inspection ID or Engineer name..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setCurrentPage(1);
                }}
              />
            </div>
          </div>

          {/* Class Filter */}
          <div className="col-6 col-md-3">
            <select
              className="form-select form-select-sm"
              value={classFilter}
              onChange={(e) => {
                setClassFilter(e.target.value);
                setCurrentPage(1);
              }}
            >
              <option value="all">All AI Predictions</option>
              <option value="Normal">Normal Only</option>
              <option value="Defective">Defective Only</option>
            </select>
          </div>

          {/* Review Filter */}
          <div className="col-6 col-md-3">
            <select
              className="form-select form-select-sm"
              value={reviewFilter}
              onChange={(e) => {
                setReviewFilter(e.target.value);
                setCurrentPage(1);
              }}
            >
              <option value="all">All Review States</option>
              <option value="pending">Pending Review Only</option>
              <option value="reviewed">Reviewed Audits Only</option>
            </select>
          </div>

          {/* Reset Filters */}
          <div className="col-12 col-md-2 text-md-end">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary w-100"
              onClick={handleResetFilters}
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* Counter readout */}
        <div className="text-muted small mt-2 pt-2 border-top d-flex justify-content-between" style={{ fontSize: '0.75rem' }}>
          <span>
            Displaying <strong>{filteredInspections.length}</strong> of {totalCount} total inspections for <strong>{productId}</strong>
          </span>
          {filteredInspections.length > 0 && (
            <span>Page {currentPage} of {totalPages}</span>
          )}
        </div>
      </div>

      {/* Engineer Inspection Image Gallery Grid */}
      {loading ? (
        <LoadingSpinner text={`Retrieving uploaded inspection images for ${productId}...`} size="lg" />
      ) : allInspections.length === 0 ? (
        <EmptyState
          title={`No Inspections Recorded for ${productId}`}
          description={`No visual quality plate inspection images have been uploaded by engineers for product ${productId} yet. When inspections are submitted, their uploaded images and model classifications will appear here in real time.`}
          icon={Layers}
        />
      ) : filteredInspections.length === 0 ? (
        <EmptyState
          title="No Images Match Criteria"
          description="No engineer inspection images matched the selected search or filter options."
          icon={Filter}
          actionButton={
            <button className="btn btn-sm btn-outline-primary mt-2" onClick={handleResetFilters}>
              Clear Filters
            </button>
          }
        />
      ) : (
        <>
          <div className="row g-3 mb-4">
            {paginatedInspections.map((item) => {
              const predictedClass = item.predicted_class || item.prediction || 'Normal';
              const isNormal = predictedClass.toLowerCase() === 'normal';
              const isDefective = predictedClass.toLowerCase() === 'defective';
              const isCorrected = (item.review_status || '').toLowerCase() === 'corrected';
              const isConfirmed = (item.review_status || '').toLowerCase() === 'confirmed';

              return (
                <div key={item.id} className="col-12 col-sm-6 col-lg-4">
                  <div
                    className={`card card-industrial h-100 bg-white p-3 d-flex flex-column transition-all hover-shadow ${
                      isNormal
                        ? 'border-success border-opacity-25'
                        : isDefective
                        ? 'border-danger border-opacity-25'
                        : ''
                    }`}
                  >
                    {/* Header: Inspection ID & Processing Badge */}
                    <div className="d-flex align-items-center justify-content-between mb-2">
                      <span className="badge bg-light text-dark border font-monospace" style={{ fontSize: '0.72rem' }}>
                        ID: #{item.id}
                      </span>
                      <InspectionStatusBadge type="processing" value={item.status || 'Completed'} />
                    </div>

                    {/* Actual Uploaded Image Thumbnail (Clickable) */}
                    <div
                      onClick={() => setActiveModalInspection(item)}
                      className="rounded bg-dark d-flex align-items-center justify-content-center overflow-hidden mb-3 border cursor-pointer position-relative group"
                      style={{ height: '180px', cursor: 'pointer' }}
                      title="Click to view full inspection details"
                    >
                      {item.image_url || item.thumbnail_url ? (
                        <img
                          src={item.image_url || item.thumbnail_url}
                          alt={`Inspection #${item.id}`}
                          style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                        />
                      ) : (
                        <div className="text-secondary small d-flex flex-column align-items-center gap-1">
                          <Layers size={28} />
                          <span>No Preview Stream</span>
                        </div>
                      )}

                      <div
                        className="position-absolute bottom-0 end-0 m-1 p-1 rounded bg-black bg-opacity-75 text-white small d-flex align-items-center gap-1"
                        style={{ fontSize: '0.68rem' }}
                      >
                        <Eye size={11} /> Zoom
                      </div>
                    </div>

                    {/* Prediction & Confidence Block */}
                    <div className="p-2 rounded bg-light border mb-2 small">
                      <div className="d-flex justify-content-between align-items-center mb-1">
                        <span className="text-secondary fw-semibold" style={{ fontSize: '0.72rem' }}>
                          AI PREDICTION:
                        </span>
                        <InspectionStatusBadge type="class" value={predictedClass} />
                      </div>

                      <div className="d-flex justify-content-between align-items-center">
                        <span className="text-secondary fw-semibold" style={{ fontSize: '0.72rem' }}>
                          CONFIDENCE:
                        </span>
                        <span className="fw-bold font-monospace text-dark">
                          {formatConfidence(item.confidence)}
                        </span>
                      </div>

                      {/* Display Supervisor Calibration Separately if Audited */}
                      {isCorrected && (
                        <div className="mt-2 pt-2 border-top">
                          <div className="d-flex justify-content-between align-items-center">
                            <span className="text-danger fw-semibold d-flex align-items-center gap-1" style={{ fontSize: '0.7rem' }}>
                              <Edit3 size={11} /> Supervisor Override:
                            </span>
                            <InspectionStatusBadge type="class" value={item.supervisor_class || 'Corrected'} />
                          </div>
                        </div>
                      )}

                      {isConfirmed && (
                        <div className="mt-1 pt-1 border-top text-success small d-flex align-items-center gap-1" style={{ fontSize: '0.68rem' }}>
                          <ShieldCheck size={11} /> Supervisor Confirmed Original AI
                        </div>
                      )}
                    </div>

                    {/* Metadata: Engineer and Timestamp */}
                    <div className="mt-auto pt-2 border-top text-muted small d-flex flex-column gap-1" style={{ fontSize: '0.72rem' }}>
                      <div className="d-flex align-items-center justify-content-between">
                        <span className="d-flex align-items-center gap-1 text-dark fw-medium">
                          <User size={12} className="text-secondary" />
                          <span>{item.engineer_name || item.engineer || 'Plant Engineer'}</span>
                        </span>
                        <InspectionStatusBadge type="review" value={item.review_status || 'pending'} />
                      </div>

                      <div className="d-flex align-items-center justify-content-between text-secondary">
                        <span className="d-flex align-items-center gap-1">
                          <Calendar size={11} />
                          <span>{formatDateTime(item.created_at)}</span>
                        </span>
                        <button
                          type="button"
                          className="btn btn-link p-0 text-primary small text-decoration-none"
                          style={{ fontSize: '0.72rem' }}
                          onClick={() => setActiveModalInspection(item)}
                        >
                          View Full Details &rarr;
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination Bar */}
          {totalPages > 1 && (
            <div className="d-flex justify-content-between align-items-center p-3 bg-white border rounded">
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
              >
                <ChevronLeft size={14} /> Previous
              </button>

              <span className="small text-muted">
                Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
              </span>

              <button
                type="button"
                className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          )}
        </>
      )}

      {/* Full-Sized Inspection Detail Modal */}
      {activeModalInspection && (
        <div
          className="modal fade show d-block"
          tabIndex="-1"
          style={{ backgroundColor: 'rgba(15, 23, 42, 0.75)', zIndex: 1060 }}
        >
          <div className="modal-dialog modal-lg modal-dialog-centered">
            <div className="modal-content border-0 shadow-lg">
              <div className="modal-header bg-white border-bottom py-3">
                <div className="d-flex align-items-center gap-2">
                  <InspectionStatusBadge
                    type="class"
                    value={activeModalInspection.predicted_class || activeModalInspection.prediction}
                  />
                  <span className="badge bg-light text-secondary border font-monospace">
                    ID: #{activeModalInspection.id}
                  </span>
                  <span className="badge bg-primary font-monospace">
                    {productId}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => setActiveModalInspection(null)}
                  aria-label="Close"
                />
              </div>

              <div className="modal-body p-4 bg-light">
                <div className="row g-3">
                  {/* High Resolution Image View */}
                  <div className="col-12 col-md-6 text-center">
                    <div className="border rounded bg-dark p-1 overflow-hidden h-100 d-flex align-items-center justify-content-center">
                      {activeModalInspection.image_url || activeModalInspection.thumbnail_url ? (
                        <img
                          src={activeModalInspection.image_url || activeModalInspection.thumbnail_url}
                          alt={`Inspection #${activeModalInspection.id}`}
                          className="img-fluid rounded"
                          style={{ maxHeight: '340px', width: '100%', objectFit: 'contain' }}
                        />
                      ) : (
                        <div className="p-5 text-muted small">No Image Preview Available</div>
                      )}
                    </div>
                  </div>

                  {/* Telemetry & Calibration Details */}
                  <div className="col-12 col-md-6">
                    <div className="card card-industrial p-3 bg-white mb-3">
                      <h6 className="fw-bold text-dark mb-2 pb-2 border-bottom small text-uppercase">
                        Inference Telemetry
                      </h6>
                      <div className="row g-2 small">
                        <div className="col-6">
                          <span className="text-secondary">Original AI Prediction:</span>
                          <div className="mt-1">
                            <InspectionStatusBadge
                              type="class"
                              value={activeModalInspection.predicted_class || activeModalInspection.prediction}
                            />
                          </div>
                        </div>

                        <div className="col-6">
                          <span className="text-secondary">AI Confidence:</span>
                          <div className="fw-bold font-monospace text-dark fs-6">
                            {formatConfidence(activeModalInspection.confidence)}
                          </div>
                        </div>

                        <div className="col-6">
                          <span className="text-secondary">Target Product ID:</span>
                          <div className="fw-bold font-monospace text-primary">{productId}</div>
                        </div>

                        <div className="col-6">
                          <span className="text-secondary">AI Model Identifier:</span>
                          <div className="fw-bold font-monospace text-dark">
                            {activeModalInspection.model_version || product.model_version || 'BIT-PLATE-CV-1.0'}
                          </div>
                        </div>

                        <div className="col-6">
                          <span className="text-secondary">Submitting Engineer:</span>
                          <div className="fw-medium text-dark">
                            {activeModalInspection.engineer_name || activeModalInspection.engineer || 'Plant Engineer'}
                          </div>
                        </div>

                        <div className="col-6">
                          <span className="text-secondary">Upload Timestamp:</span>
                          <div className="text-muted" style={{ fontSize: '0.74rem' }}>
                            {formatDateTime(activeModalInspection.created_at)}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Supervisor Review Information */}
                    <div className="card card-industrial p-3 bg-white">
                      <h6 className="fw-bold text-dark mb-2 pb-2 border-bottom small text-uppercase d-flex align-items-center gap-1">
                        <ShieldCheck size={14} className="text-primary" /> Supervisor Calibration Audit
                      </h6>
                      <div className="small">
                        <div className="d-flex justify-content-between mb-2">
                          <span className="text-secondary">Audit Status:</span>
                          <InspectionStatusBadge
                            type="review"
                            value={activeModalInspection.review_status || 'pending'}
                          />
                        </div>

                        {activeModalInspection.supervisor_class && (
                          <div className="d-flex justify-content-between mb-2 p-2 rounded bg-light border">
                            <span className="text-secondary">Supervisor Determination:</span>
                            <InspectionStatusBadge type="class" value={activeModalInspection.supervisor_class} />
                          </div>
                        )}

                        {activeModalInspection.supervisor_name && (
                          <div className="text-muted mb-1" style={{ fontSize: '0.72rem' }}>
                            Audited by <strong>{activeModalInspection.supervisor_name}</strong> on {formatDateTime(activeModalInspection.reviewed_at)}
                          </div>
                        )}

                        {activeModalInspection.review_comment && (
                          <div className="p-2 bg-light rounded border fst-italic text-secondary mt-1" style={{ fontSize: '0.74rem' }}>
                            "{activeModalInspection.review_comment}"
                          </div>
                        )}

                        {!activeModalInspection.review_status || activeModalInspection.review_status === 'pending' ? (
                          <div className="text-muted small" style={{ fontSize: '0.74rem' }}>
                            Pending supervisor audit confirmation.
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer bg-white py-2 px-4">
                <button
                  type="button"
                  className="btn btn-sm btn-secondary"
                  onClick={() => setActiveModalInspection(null)}
                >
                  Close Preview
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
