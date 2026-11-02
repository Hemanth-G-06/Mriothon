import React, { useState, useEffect } from 'react';
import { FileText, Upload, Plus, Filter, Search, CheckCircle2, AlertCircle, Eye, RefreshCw } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { machineService } from '../../services/machineService';
import StatusBadge from '../../components/common/StatusBadge';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import PdfViewerModal from '../../components/pdf/PdfViewerModal';
import { MANUAL_TYPES } from '../../utils/constants';
import { formatDateTime, formatFileSize } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedMachineFilter, setSelectedMachineFilter] = useState('');
  const [search, setSearch] = useState('');
  
  // Upload Modal State
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  // Upload Form Data
  const [uploadForm, setUploadForm] = useState({
    machine_id: '',
    title: '',
    manual_type: MANUAL_TYPES[0],
    model_number: '',
    revision: 'Rev 1.0',
    file: null
  });

  // PDF Preview State
  const [pdfPreview, setPdfPreview] = useState({
    isOpen: false,
    documentId: null,
    documentTitle: '',
    revision: '',
    pageNumber: 1
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [docList, machList] = await Promise.all([
        documentService.getDocuments(selectedMachineFilter || null),
        machineService.getMachines()
      ]);
      setDocuments(Array.isArray(docList) ? docList : []);
      setMachines(Array.isArray(machList) ? machList : []);
    } catch (err) {
      setFeedback({ type: 'danger', message: getErrorMessage(err, 'Failed to retrieve documents or equipment registry.') });
      setDocuments([]);
      setMachines([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedMachineFilter]);

  // Poll for document status updates if any document is in non-terminal state (Uploaded or Processing)
  useEffect(() => {
    const hasPending = documents.some((d) => {
      const s = d.status?.toLowerCase();
      return s === 'uploaded' || s === 'processing';
    });

    if (!hasPending) return;

    const timer = setInterval(async () => {
      try {
        const docList = await documentService.getDocuments(selectedMachineFilter || null);
        setDocuments(Array.isArray(docList) ? docList : []);
      } catch (e) {
        console.warn('Document status polling error:', e);
      }
    }, 4000);

    return () => clearInterval(timer);
  }, [documents, selectedMachineFilter]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        setFeedback({ type: 'danger', message: 'Only PDF format manuals (.pdf) are supported.' });
        return;
      }
      setUploadForm((prev) => ({
        ...prev,
        file: file,
        // Auto-fill title from filename if not manually typed
        title: prev.title || file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' ')
      }));
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadForm.file) {
      setFeedback({ type: 'danger', message: 'Please select a PDF manual file to upload.' });
      return;
    }
    if (!uploadForm.machine_id) {
      setFeedback({ type: 'danger', message: 'Please associate this manual with a machine.' });
      return;
    }
    if (!uploadForm.title.trim()) {
      setFeedback({ type: 'danger', message: 'Please provide a document title.' });
      return;
    }

    setIsUploading(true);
    setUploadProgress(15);
    setFeedback({ type: '', message: '' });

    const formData = new FormData();
    formData.append('file', uploadForm.file);
    formData.append('machine_id', uploadForm.machine_id);
    formData.append('title', uploadForm.title.trim());
    formData.append('manual_type', uploadForm.manual_type);
    formData.append('model_number', uploadForm.model_number || '');
    formData.append('revision', uploadForm.revision || 'Rev 1.0');

    try {
      const result = await documentService.uploadDocument(formData, (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        }
      });

      setFeedback({
        type: 'success',
        message: `Manual "${uploadForm.title}" uploaded! Document status: ${result.status || 'Uploaded'}. Vector indexing will proceed in the backend.`
      });
      setShowUploadModal(false);
      setUploadForm({
        machine_id: '',
        title: '',
        manual_type: MANUAL_TYPES[0],
        model_number: '',
        revision: 'Rev 1.0',
        file: null
      });
      setUploadProgress(0);
      await loadData();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Manual upload failed. Ensure the backend endpoint is accessible.')
      });
    } finally {
      setIsUploading(false);
    }
  };

  const filteredDocs = (documents || []).filter((d) => {
    const q = search.toLowerCase();
    return (
      d.title?.toLowerCase().includes(q) ||
      d.machine_name?.toLowerCase().includes(q) ||
      d.model_number?.toLowerCase().includes(q) ||
      d.manual_type?.toLowerCase().includes(q) ||
      d.revision?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="container-fluid p-0">
      {/* Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h4 className="fw-bold text-dark mb-1">Manuals & Technical Documentation</h4>
          <p className="text-muted small mb-0">
            Upload OEM technical manuals, schematics, and view RAG indexing pipeline status.
          </p>
        </div>
        <button
          onClick={() => {
            setShowUploadModal(true);
            setFeedback({ type: '', message: '' });
          }}
          className="btn btn-primary-industrial btn-sm d-flex align-items-center gap-1"
        >
          <Upload size={16} /> Upload PDF Manual
        </button>
      </div>

      {/* Global Feedback Alert */}
      {feedback.message && !showUploadModal && (
        <div className={`alert alert-${feedback.type} alert-dismissible fade show py-2 small mb-3`} role="alert">
          <div className="d-flex align-items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{feedback.message}</span>
          </div>
          <button type="button" className="btn-close py-2" onClick={() => setFeedback({ type: '', message: '' })} />
        </div>
      )}

      {/* Filters Bar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-2 align-items-center">
          <div className="col-12 col-md-5 col-lg-4">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                className="form-control border-start-0"
                placeholder="Search manuals, titles, revisions..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="col-12 col-md-4 col-lg-3">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light">
                <Filter size={13} className="text-muted" />
              </span>
              <select
                className="form-select"
                value={selectedMachineFilter}
                onChange={(e) => setSelectedMachineFilter(e.target.value)}
              >
                <option value="">All Machines</option>
                {machines.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="col-12 col-md-3 col-lg-5 text-md-end text-muted small">
            Displaying <strong>{filteredDocs.length}</strong> of {documents.length} manuals
          </div>
        </div>
      </div>

      {/* Documents Table */}
      {loading ? (
        <LoadingSpinner text="Retrieving technical documentation..." size="lg" />
      ) : filteredDocs.length === 0 ? (
        <EmptyState
          title="No Manuals Found"
          description={search || selectedMachineFilter ? 'No documents match the chosen filters.' : 'No PDF manuals have been uploaded yet.'}
          icon={FileText}
          actionButton={
            <button
              onClick={() => setShowUploadModal(true)}
              className="btn btn-sm btn-primary-industrial mt-2"
            >
              Upload First Manual
            </button>
          }
        />
      ) : (
        <div className="card card-industrial bg-white overflow-hidden">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th className="small text-secondary fw-semibold">Manual Title</th>
                  <th className="small text-secondary fw-semibold">Target Machine</th>
                  <th className="small text-secondary fw-semibold">Type & Rev</th>
                  <th className="small text-secondary fw-semibold">Size</th>
                  <th className="small text-secondary fw-semibold text-center">RAG Index Status</th>
                  <th className="small text-secondary fw-semibold text-end">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <div className="d-flex align-items-center gap-2">
                        <FileText size={18} className="text-danger flex-shrink-0" />
                        <div>
                          <div className="fw-semibold text-dark small">{doc.title}</div>
                          <div className="text-muted font-monospace" style={{ fontSize: '0.7rem' }}>
                            {doc.file_name || 'document.pdf'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="small text-dark fw-medium">
                      {doc.machine_name || `Machine #${doc.machine_id}`}
                    </td>
                    <td className="small">
                      <div className="text-muted">{doc.manual_type}</div>
                      <span className="badge bg-light text-secondary border" style={{ fontSize: '0.68rem' }}>
                        {doc.revision || 'Rev 1.0'}
                      </span>
                    </td>
                    <td className="small text-muted">{formatFileSize(doc.file_size)}</td>
                    <td className="text-center">
                      <StatusBadge status={doc.status} />
                    </td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-outline-secondary d-inline-flex align-items-center gap-1"
                        style={{ fontSize: '0.78rem' }}
                        onClick={() =>
                          setPdfPreview({
                            isOpen: true,
                            documentId: doc.id,
                            documentTitle: doc.title,
                            revision: doc.revision,
                            pageNumber: 1
                          })
                        }
                        title="Preview Manual"
                      >
                        <Eye size={13} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Upload Manual Modal */}
      {showUploadModal && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered modal-lg">
            <div className="modal-content border-0 shadow">
              <div className="modal-header">
                <h5 className="modal-title fw-bold d-flex align-items-center gap-2">
                  <Upload size={18} className="text-primary" /> Upload Technical Manual (PDF)
                </h5>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => !isUploading && setShowUploadModal(false)}
                  disabled={isUploading}
                />
              </div>

              <form onSubmit={handleUploadSubmit}>
                <div className="modal-body p-4">
                  {feedback.message && (
                    <div className="alert alert-danger py-2 small mb-3">{feedback.message}</div>
                  )}

                  {/* Target Machine Selection */}
                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Target Equipment / Machine *</label>
                    <select
                      className="form-select form-select-sm"
                      value={uploadForm.machine_id}
                      onChange={(e) => {
                        const mId = e.target.value;
                        const matched = machines.find((m) => String(m.id) === String(mId));
                        setUploadForm((prev) => ({
                          ...prev,
                          machine_id: mId,
                          model_number: matched ? matched.model_number : prev.model_number
                        }));
                      }}
                      required
                      disabled={isUploading}
                    >
                      <option value="">-- Choose Machine Association --</option>
                      {machines.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.model_number || 'Standard'})
                        </option>
                      ))}
                    </select>
                    <div className="form-text small" style={{ fontSize: '0.72rem' }}>
                      Answers generated by engineers are strictly restricted to this machine's associated manuals.
                    </div>
                  </div>

                  {/* File Upload Drop Area */}
                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">PDF File Selection *</label>
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      className="form-control form-control-sm"
                      onChange={handleFileChange}
                      required
                      disabled={isUploading}
                    />
                    {uploadForm.file && (
                      <div className="mt-1 text-success small d-flex align-items-center gap-1">
                        <CheckCircle2 size={13} /> Selected: {uploadForm.file.name} ({formatFileSize(uploadForm.file.size)})
                      </div>
                    )}
                  </div>

                  <div className="row g-2 mb-3">
                    <div className="col-12 col-md-8">
                      <label className="form-label small fw-semibold text-secondary">Document Title *</label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        placeholder="e.g. HP-200 Operations Manual"
                        value={uploadForm.title}
                        onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                        required
                        disabled={isUploading}
                      />
                    </div>
                    <div className="col-12 col-md-4">
                      <label className="form-label small fw-semibold text-secondary">Revision</label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        placeholder="e.g. Rev 2.4"
                        value={uploadForm.revision}
                        onChange={(e) => setUploadForm({ ...uploadForm, revision: e.target.value })}
                        disabled={isUploading}
                      />
                    </div>
                  </div>

                  <div className="row g-2 mb-3">
                    <div className="col-12 col-md-6">
                      <label className="form-label small fw-semibold text-secondary">Manual Type</label>
                      <select
                        className="form-select form-select-sm"
                        value={uploadForm.manual_type}
                        onChange={(e) => setUploadForm({ ...uploadForm, manual_type: e.target.value })}
                        disabled={isUploading}
                      >
                        {MANUAL_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-12 col-md-6">
                      <label className="form-label small fw-semibold text-secondary">Applicable Model Number</label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        placeholder="e.g. HP-200-V4"
                        value={uploadForm.model_number}
                        onChange={(e) => setUploadForm({ ...uploadForm, model_number: e.target.value })}
                        disabled={isUploading}
                      />
                    </div>
                  </div>

                  {/* Upload Progress Bar */}
                  {isUploading && (
                    <div className="mt-3">
                      <div className="d-flex justify-content-between small text-muted mb-1">
                        <span>Uploading binary payload...</span>
                        <span>{uploadProgress}%</span>
                      </div>
                      <div className="progress" style={{ height: '8px' }}>
                        <div
                          className="progress-bar progress-bar-striped progress-bar-animated bg-primary"
                          role="progressbar"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="modal-footer bg-light py-2 px-4">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => setShowUploadModal(false)}
                    disabled={isUploading}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-sm btn-primary-industrial d-flex align-items-center gap-1"
                    disabled={isUploading}
                  >
                    {isUploading ? (
                      <>
                        <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                        <span>Uploading...</span>
                      </>
                    ) : (
                      <>
                        <Upload size={14} /> Upload & Dispatch to Indexer
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* PDF Viewer Modal */}
      <PdfViewerModal
        isOpen={pdfPreview.isOpen}
        onClose={() => setPdfPreview({ ...pdfPreview, isOpen: false })}
        documentId={pdfPreview.documentId}
        documentTitle={pdfPreview.documentTitle}
        revision={pdfPreview.revision}
        pageNumber={pdfPreview.pageNumber}
      />
    </div>
  );
}
