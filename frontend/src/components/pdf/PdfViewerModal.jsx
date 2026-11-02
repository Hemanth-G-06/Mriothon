import React, { useState, useEffect } from 'react';
import { X, ExternalLink, FileText, ChevronLeft, ChevronRight, AlertCircle, RefreshCw } from 'lucide-react';
import { documentService } from '../../services/documentService';
import LoadingSpinner from '../common/LoadingSpinner';

export default function PdfViewerModal({
  isOpen,
  onClose,
  documentId,
  documentTitle = 'Technical Manual',
  revision = 'Rev 1.0',
  pageNumber = 1,
  directPdfUrl = null
}) {
  const [currentPage, setCurrentPage] = useState(pageNumber);
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (pageNumber) {
      setCurrentPage(Math.max(1, Number(pageNumber) || 1));
    }
  }, [pageNumber]);

  useEffect(() => {
    let activeUrl = null;

    if (isOpen) {
      setError(null);
      if (directPdfUrl) {
        setPdfBlobUrl(directPdfUrl);
      } else if (documentId) {
        setLoading(true);
        documentService
          .getDocumentPdfUrl(documentId)
          .then((url) => {
            activeUrl = url;
            setPdfBlobUrl(url);
          })
          .catch((err) => {
            console.error('Failed to load PDF binary:', err);
            const msg = !err.response
              ? 'Unable to connect to the server. Please check your connection and try again.'
              : err.response.status === 403
              ? 'Access denied. You do not have permission to view this technical manual.'
              : err.response.status === 404
              ? 'The requested technical manual PDF was not found on the server.'
              : 'Unable to fetch protected PDF stream. Please try again.';
            setError(msg);
          })
          .finally(() => {
            setLoading(false);
          });
      } else {
        setError('Citation metadata is missing document identifier. Unable to open PDF manual.');
      }
    }

    return () => {
      // Clean up object URL if created
      if (activeUrl && activeUrl.startsWith('blob:')) {
        URL.revokeObjectURL(activeUrl);
      }
    };
  }, [isOpen, documentId, directPdfUrl]);

  if (!isOpen) return null;

  const targetViewerUrl = pdfBlobUrl
    ? `${pdfBlobUrl}#page=${currentPage}&view=FitH`
    : null;

  return (
    <div
      className="modal fade show d-block"
      tabIndex="-1"
      style={{ backgroundColor: 'rgba(15, 23, 42, 0.75)', zIndex: 1050 }}
    >
      <div className="modal-dialog modal-xl modal-dialog-centered" style={{ height: '90vh' }}>
        <div className="modal-content h-100 d-flex flex-column border-0 shadow-lg">
          {/* Header */}
          <div className="modal-header bg-dark text-white py-2 px-3 align-items-center">
            <div className="d-flex align-items-center gap-2 overflow-hidden me-3">
              <FileText size={18} className="text-primary flex-shrink-0" />
              <div className="text-truncate">
                <span className="fw-semibold small">{documentTitle}</span>
                <span className="badge bg-secondary ms-2 small">{revision}</span>
              </div>
            </div>

            {/* Page Jump and Actions */}
            <div className="d-flex align-items-center gap-2 flex-shrink-0">
              <div className="input-group input-group-sm" style={{ width: '130px' }}>
                <button
                  className="btn btn-outline-light btn-sm"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  title="Previous Page"
                >
                  <ChevronLeft size={14} />
                </button>
                <span className="input-group-text bg-secondary border-0 text-white px-2 small">
                  Page {currentPage}
                </span>
                <button
                  className="btn btn-outline-light btn-sm"
                  onClick={() => setCurrentPage((p) => p + 1)}
                  title="Next Page"
                >
                  <ChevronRight size={14} />
                </button>
              </div>

              {pdfBlobUrl && (
                <a
                  href={targetViewerUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-sm btn-outline-light d-flex align-items-center gap-1"
                  title="Open in external browser tab"
                >
                  <ExternalLink size={14} />
                  <span className="d-none d-md-inline">Popout</span>
                </a>
              )}

              <button
                type="button"
                className="btn-close btn-close-white ms-2"
                aria-label="Close"
                onClick={onClose}
              />
            </div>
          </div>

          {/* Modal Body / Viewer */}
          <div className="modal-body p-0 flex-grow-1 bg-light position-relative d-flex flex-column">
            {loading && (
              <div className="h-100 d-flex align-items-center justify-content-center">
                <LoadingSpinner text="Loading manual PDF at cited page..." size="lg" />
              </div>
            )}

            {error && (
              <div className="p-4 text-center m-auto max-w-md">
                <AlertCircle size={40} className="text-danger mb-2" />
                <h6 className="fw-bold text-dark">PDF Manual Unavailable</h6>
                <p className="text-muted small mb-3">{error}</p>
                <div className="d-flex justify-content-center gap-2">
                  <button
                    className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                    onClick={() => {
                      setError(null);
                      setLoading(true);
                      documentService.getDocumentPdfUrl(documentId).then(setPdfBlobUrl).finally(() => setLoading(false));
                    }}
                  >
                    <RefreshCw size={14} /> Retry Load
                  </button>
                  <button className="btn btn-sm btn-secondary" onClick={onClose}>
                    Close
                  </button>
                </div>
              </div>
            )}

            {!loading && !error && targetViewerUrl && (
              <iframe
                key={`${pdfBlobUrl}-page-${currentPage}`}
                src={targetViewerUrl}
                title={documentTitle}
                className="w-100 h-100 border-0 flex-grow-1"
              />
            )}

            {!loading && !error && !targetViewerUrl && (
              <div className="p-4 text-center m-auto">
                <FileText size={48} className="text-muted mb-2" />
                <h6 className="fw-semibold">Document Citation Preview</h6>
                <p className="text-muted small mb-1">
                  Target: <strong>{documentTitle}</strong> ({revision})
                </p>
                <p className="text-muted small">
                  Cited at Page <strong>{currentPage}</strong>.
                </p>
                <div className="alert alert-info py-2 small d-inline-block text-start mt-2">
                  When running with Django backend, the protected PDF binary stream will render here
                  automatically focused on page {currentPage}.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
