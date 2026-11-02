import React, { useState, useEffect } from 'react';
import { FileText, Upload, Plus, Filter, Search, CheckCircle2, AlertCircle, Eye, RefreshCw, Database, Trash2, AlertTriangle } from 'lucide-react';
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
  const [indexStatuses, setIndexStatuses] = useState({});
  const [indexingDocId, setIndexingDocId] = useState(null);
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
    description: '',
    file: null
  });

  // PDF Preview State
  // Delete Document Modal State
  const [showDeleteDocModal, setShowDeleteDocModal] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState(null);
  const [isDeletingDoc, setIsDeletingDoc] = useState(false);

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
      const docs = Array.isArray(docList) ? docList : [];
      setDocuments(docs);
      setMachines(Array.isArray(machList) ? machList : []);

      // Load ChromaDB indexing status for each document
      const statusMap = {};
      await Promise.allSettled(
        docs.map(async (d) => {
          try {
            const idx = await documentService.getIndexStatus(d.id);
            statusMap[d.id] = idx;
          } catch {
            statusMap[d.id] = { status: 'PENDING', chunk_count: 0 };
          }
        })
      );
      setIndexStatuses(statusMap);
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
    if (uploadForm.description) {
      formData.append('description', uploadForm.description.trim());
    }

    try {
      const result = await documentService.uploadDocument(formData, (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        }
      });

      // Synchronous PDF extraction completed, now automatically trigger indexing
      setFeedback({
        type: 'success',
        message: `Manual "${uploadForm.title}" uploaded and extracted successfully! Triggering vector indexing...`
      });
      setShowUploadModal(false);
      setUploadForm({
        machine_id: '',
        title: '',
        manual_type: MANUAL_TYPES[0],
        model_number: '',
        revision: 'Rev 1.0',
        description: '',
        file: null
      });
      setUploadProgress(0);

      // Trigger indexing
      try {
        await documentService.indexDocument(result.id);
        setFeedback({
          type: 'success',
          message: `Manual "${uploadForm.title}" successfully indexed into ChromaDB vector database and ready for querying!`
        });
      } catch (idxErr) {
        console.warn('Auto indexing notice:', idxErr);
      }

      await loadData();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Manual upload failed. Ensure the PDF is valid.')
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleTriggerIndex = async (docId, docTitle) => {
    setIndexingDocId(docId);
    setFeedback({ type: '', message: '' });
    try {
      const res = await documentService.indexDocument(docId);
      setFeedback({
        type: 'success',
        message: `Document "${docTitle}" indexed into ChromaDB! (${res.index?.chunk_count || res.chunk_count || 0} chunks)`
      });
      await loadData();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Indexing operation failed.')
      });
    } finally {
      setIndexingDocId(null);
    }
  };

  const handleConfirmDeleteDoc = async () => {
    if (!documentToDelete || isDeletingDoc) return;
    const targetDoc = documentToDelete;
    setIsDeletingDoc(true);
    setFeedback({ type: '', message: '' });
    try {
      await documentService.deleteDocument(targetDoc.id, true);
      if (pdfPreview.documentId === targetDoc.id) {
        setPdfPreview((prev) => ({ ...prev, isOpen: false, documentId: null }));
      }
      setShowDeleteDocModal(false);
      setDocumentToDelete(null);
      setFeedback({
        type: 'success',
        message: `Manual "${targetDoc.title}" and its vector index were permanently deleted.`
      });
      await loadData();
    } catch (err) {
      setShowDeleteDocModal(false);
      setDocumentToDelete(null);
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, `Failed to delete manual "${targetDoc.title}".`)
      });
    } finally {
      setIsDeletingDoc(false);
    }
  };

  const filteredDocs = (documents || []).filter((d) => {
    const q = search.toLowerCase();
    return (
      d.title?.toLowerCase().includes(q) ||
      d.machine_name?.toLowerCase().includes(q) ||
      d.machine_code?.toLowerCase().includes(q) ||
      d.original_filename?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="container-fluid p-0">
      {/* Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h4 className="fw-bold text-dark mb-1">Manuals & Technical Documentation</h4>
          <p className="text-muted small mb-0">
            Upload OEM technical manuals, schematics, and monitor ChromaDB RAG vector indexing pipeline.
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
                placeholder="Search manuals, titles, machines..."
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
                    {m.name} ({m.machine_code || 'CODE'})
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
        <div className="card card-industrial bg-white overflow-hidden shadow-sm">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0" style={{ fontSize: '0.88rem' }}>
              <thead className="table-light text-secondary text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '0.04em' }}>
                <tr>
                  <th className="ps-3">Manual Title</th>
                  <th>Machine Association</th>
                  <th>Pages & Size</th>
                  <th>PDF Extraction</th>
                  <th>ChromaDB Index</th>
                  <th className="text-end pe-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map((doc) => {
                  const idxStatus = indexStatuses[doc.id];
                  const isIndexed = idxStatus?.status === 'READY';
                  const isExtractionReady = doc.status === 'READY';

                  return (
                    <tr key={doc.id}>
                      <td className="ps-3">
                        <div className="d-flex align-items-center gap-2">
                          <FileText size={18} className="text-danger flex-shrink-0" />
                          <div>
                            <div className="fw-semibold text-dark small">{doc.title}</div>
                            <div className="text-muted font-monospace" style={{ fontSize: '0.7rem' }}>
                              {doc.original_filename || 'document.pdf'}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="small text-dark fw-medium">
                        <div>{doc.machine_name || 'Machine'}</div>
                        <span className="badge bg-light text-secondary border font-monospace" style={{ fontSize: '0.7rem' }}>
                          {doc.machine_code}
                        </span>
                      </td>
                      <td className="small text-muted">
                        <div>{doc.page_count ? `${doc.page_count} pages` : '—'}</div>
                        <span style={{ fontSize: '0.75rem' }}>{formatFileSize(doc.file_size)}</span>
                      </td>
                      <td>
                        <StatusBadge status={doc.status} />
                      </td>
                      <td>
                        {isIndexed ? (
                          <span className="badge bg-success bg-opacity-10 text-success border border-success small d-inline-flex align-items-center gap-1">
                            <CheckCircle2 size={12} /> Ready ({idxStatus.chunk_count} chunks)
                          </span>
                        ) : idxStatus?.status === 'FAILED' ? (
                          <span className="badge bg-danger bg-opacity-10 text-danger border border-danger small">
                            Indexing Failed
                          </span>
                        ) : (
                          <span className="badge bg-warning bg-opacity-10 text-dark border border-warning small">
                            Not Indexed
                          </span>
                        )}
                      </td>
                      <td className="text-end pe-3">
                        <div className="d-flex justify-content-end gap-1">
                          {isExtractionReady && (
                            <button
                              className="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1 py-0 px-2"
                              style={{ fontSize: '0.75rem' }}
                              onClick={() => handleTriggerIndex(doc.id, doc.title)}
                              disabled={indexingDocId === doc.id}
                              title="Index chunks into ChromaDB"
                            >
                              {indexingDocId === doc.id ? (
                                <>
                                  <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" style={{ width: '0.7rem', height: '0.7rem' }} />
                                  <span>Indexing...</span>
                                </>
                              ) : (
                                <>
                                  <Database size={12} />
                                  <span>{isIndexed ? 'Re-index' : 'Index'}</span>
                                </>
                              )}
                            </button>
                          )}
                          <button
                            className="btn btn-sm btn-outline-secondary d-inline-flex align-items-center gap-1 py-0 px-2"
                            style={{ fontSize: '0.75rem' }}
                            onClick={() =>
                              setPdfPreview({
                                isOpen: true,
                                documentId: doc.id,
                                documentTitle: doc.title,
                                revision: doc.revision || '1.0',
                                pageNumber: 1
                              })
                            }
                            title="Inspect PDF manual"
                          >
                            <Eye size={12} />
                            <span>Inspect</span>
                          </button>
                          <button
                            className="btn btn-sm btn-outline-danger d-inline-flex align-items-center gap-1 py-0 px-2"
                            style={{ fontSize: '0.75rem' }}
                            onClick={() => {
                              setDocumentToDelete(doc);
                              setShowDeleteDocModal(true);
                            }}
                            title="Delete manual"
                          >
                            <Trash2 size={12} />
                            <span>Delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
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
                      onChange={(e) => setUploadForm((prev) => ({ ...prev, machine_id: e.target.value }))}
                      required
                      disabled={isUploading}
                    >
                      <option value="">-- Choose Machine Association --</option>
                      {machines.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.machine_code || 'CODE'})
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

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Document Title *</label>
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      placeholder="e.g. Haas VMC Operations Manual"
                      value={uploadForm.title}
                      onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                      required
                      disabled={isUploading}
                    />
                  </div>

                  <div className="mb-0">
                    <label className="form-label small fw-semibold text-secondary">Description (Optional)</label>
                    <textarea
                      rows={2}
                      className="form-control form-control-sm"
                      placeholder="e.g. Factory maintenance protocols, lubrication intervals, spindle warmup"
                      value={uploadForm.description}
                      onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
                      disabled={isUploading}
                    />
                  </div>

                  {/* Upload Progress Bar */}
                  {isUploading && (
                    <div className="mt-3">
                      <div className="d-flex justify-content-between small text-muted mb-1">
                        <span>Uploading & extracting pages...</span>
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
                        <Upload size={14} /> Upload & Extract
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
    
      {/* Delete Document Confirmation Modal */}
      {showDeleteDocModal && documentToDelete && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1055 }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0 shadow">
              <div className="modal-header bg-danger text-white">
                <div className="d-flex align-items-center gap-2">
                  <AlertTriangle size={20} />
                  <h5 className="modal-title fw-bold">Delete Technical Manual</h5>
                </div>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => { if (!isDeletingDoc) { setShowDeleteDocModal(false); setDocumentToDelete(null); } }}
                  disabled={isDeletingDoc}
                />
              </div>
              <div className="modal-body p-4">
                <p className="mb-3 text-dark">
                  Are you sure you want to permanently delete <strong>{documentToDelete.title}</strong>?
                </p>

                <div className="card bg-light border p-3 mb-3 small">
                  <div className="d-flex justify-content-between mb-1">
                    <span className="text-muted">Filename:</span>
                    <strong className="font-monospace text-dark">{documentToDelete.original_filename || 'manual.pdf'}</strong>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span className="text-muted">Associated Machine:</span>
                    <span className="text-dark fw-medium">{documentToDelete.machine_name || 'Machine'} ({documentToDelete.machine_code || 'CODE'})</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span className="text-muted">Revision:</span>
                    <span className="badge bg-secondary">{documentToDelete.revision || 'Rev 1.0'}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span className="text-muted">Page Count:</span>
                    <span>{documentToDelete.page_count ? `${documentToDelete.page_count} pages` : 'N/A'}</span>
                  </div>
                  <div className="d-flex justify-content-between">
                    <span className="text-muted">Index Status:</span>
                    <span className="badge bg-primary">
                      {indexStatuses[documentToDelete.id]?.status || 'PENDING'}
                    </span>
                  </div>
                </div>

                <div className="alert alert-warning py-2 small d-flex align-items-start gap-2 mb-0">
                  <AlertTriangle size={16} className="text-warning flex-shrink-0 mt-1" />
                  <div>
                    <strong>Permanent Deletion Warning:</strong> Deleting this manual will permanently remove the private PDF file from disk, delete all extracted page text records, and purge all associated vector chunks and embeddings from PostgreSQL (pgvector). This action cannot be undone.
                  </div>
                </div>
              </div>
              <div className="modal-footer bg-light">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => { if (!isDeletingDoc) { setShowDeleteDocModal(false); setDocumentToDelete(null); } }}
                  disabled={isDeletingDoc}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-danger d-flex align-items-center gap-1"
                  onClick={handleConfirmDeleteDoc}
                  disabled={isDeletingDoc}
                >
                  {isDeletingDoc ? (
                    <>
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      <span>Deleting Manual & Vectors...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 size={14} />
                      <span>Permanently Delete</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
</div>
  );
}
