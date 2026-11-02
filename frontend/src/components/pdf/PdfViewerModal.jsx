import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  ExternalLink,
  FileText,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { documentService } from '../../services/documentService';
import LoadingSpinner from '../common/LoadingSpinner';

// Configure PDF.js worker with bundled asset from Vite
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

export default function PdfViewerModal({
  isOpen,
  onClose,
  documentId,
  documentTitle = 'Technical Manual',
  revision = 'Rev 1.0',
  pageNumber = 1,
  directPdfUrl = null
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState('1');
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(1.0);
  const [fitMode, setFitMode] = useState('custom'); // 'width' | 'page' | 'custom'
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [renderingPage, setRenderingPage] = useState(false);
  const [error, setError] = useState(null);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [pdfDataBuffer, setPdfDataBuffer] = useState(null);

  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const renderTaskRef = useRef(null);
  const loadingTaskRef = useRef(null);
  const activeBlobUrlRef = useRef(null);

  // Sync initial page number prop
  useEffect(() => {
    if (pageNumber) {
      const pageNum = Math.max(1, Number(pageNumber) || 1);
      setCurrentPage(pageNum);
      setPageInput(String(pageNum));
    }
  }, [pageNumber, documentId, isOpen]);

  // Load PDF Binary when Modal Opens or Document Changes
  useEffect(() => {
    if (!isOpen) {
      // Clean up on close
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }
      if (loadingTaskRef.current) {
        loadingTaskRef.current.destroy();
        loadingTaskRef.current = null;
      }
      if (activeBlobUrlRef.current) {
        URL.revokeObjectURL(activeBlobUrlRef.current);
        activeBlobUrlRef.current = null;
      }
      setPdfDoc(null);
      setPdfDataBuffer(null);
      setNumPages(0);
      setError(null);
      return;
    }

    let isCancelled = false;
    setError(null);
    setLoadingDoc(true);
    setPdfDoc(null);
    setPdfDataBuffer(null);

    const loadPdfData = async () => {
      try {
        let arrayBuffer;
        if (directPdfUrl) {
          const res = await fetch(directPdfUrl);
          if (!res.ok) throw new Error(`HTTP error ${res.status}`);
          arrayBuffer = await res.arrayBuffer();
        } else if (documentId) {
          arrayBuffer = await documentService.getDocumentPdfBinary(documentId);
        } else {
          throw new Error('Citation metadata is missing document identifier.');
        }

        if (isCancelled) return;
        setPdfDataBuffer(arrayBuffer);

        const loadingTask = pdfjsLib.getDocument({
          data: new Uint8Array(arrayBuffer)
        });
        loadingTaskRef.current = loadingTask;

        const doc = await loadingTask.promise;
        if (isCancelled) return;

        setPdfDoc(doc);
        setNumPages(doc.numPages);

        const targetPage = Math.min(
          Math.max(1, Number(pageNumber) || 1),
          doc.numPages || 1
        );
        setCurrentPage(targetPage);
        setPageInput(String(targetPage));
      } catch (err) {
        if (isCancelled) return;
        console.error('Failed to load PDF document:', err);
        const status = err.response?.status;
        let msg = 'Unable to fetch protected PDF stream. Please try again.';
        if (status === 401) {
          msg = 'Authentication session expired. Please log in again to view this manual.';
        } else if (status === 403) {
          msg = 'Access denied. You do not have permission to view this technical manual.';
        } else if (status === 404) {
          msg = 'The requested technical manual PDF was not found on the server.';
        } else if (!err.response && err.message) {
          msg = err.message;
        }
        setError(msg);
      } finally {
        if (!isCancelled) {
          setLoadingDoc(false);
        }
      }
    };

    loadPdfData();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }
    };
  }, [isOpen, documentId, directPdfUrl]);

  // Render Page to Canvas
  const renderCurrentPage = useCallback(async () => {
    if (!pdfDoc || !canvasRef.current || currentPage < 1) return;

    try {
      setRenderingPage(true);
      const page = await pdfDoc.getPage(currentPage);

      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }

      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');

      const unscaledViewport = page.getViewport({ scale: 1.0 });
      let effectiveScale = scale;

      if (fitMode === 'width' && containerRef.current) {
        const containerWidth = containerRef.current.clientWidth - 48;
        if (containerWidth > 100) {
          effectiveScale = Math.max(0.4, Math.min(3.0, containerWidth / unscaledViewport.width));
        }
      } else if (fitMode === 'page' && containerRef.current) {
        const containerWidth = containerRef.current.clientWidth - 48;
        const containerHeight = containerRef.current.clientHeight - 48;
        if (containerWidth > 100 && containerHeight > 100) {
          const scaleX = containerWidth / unscaledViewport.width;
          const scaleY = containerHeight / unscaledViewport.height;
          effectiveScale = Math.max(0.4, Math.min(3.0, Math.min(scaleX, scaleY)));
        }
      }

      const viewport = page.getViewport({ scale: effectiveScale });

      // High DPI display support
      const outputScale = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      ctx.setTransform(outputScale, 0, 0, outputScale, 0, 0);

      const renderContext = {
        canvasContext: ctx,
        viewport: viewport
      };

      const renderTask = page.render(renderContext);
      renderTaskRef.current = renderTask;

      await renderTask.promise;
      renderTaskRef.current = null;
    } catch (err) {
      if (err?.name !== 'RenderingCancelledException') {
        console.error('PDF Page render error:', err);
      }
    } finally {
      setRenderingPage(false);
    }
  }, [pdfDoc, currentPage, scale, fitMode]);

  useEffect(() => {
    renderCurrentPage();
  }, [renderCurrentPage]);

  // Page Jump Input Handler
  const handlePageInputChange = (e) => {
    setPageInput(e.target.value);
  };

  const handlePageInputCommit = () => {
    const pageNum = parseInt(pageInput, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= numPages) {
      setCurrentPage(pageNum);
    } else {
      setPageInput(String(currentPage));
    }
  };

  const handlePageInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      handlePageInputCommit();
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      const prev = currentPage - 1;
      setCurrentPage(prev);
      setPageInput(String(prev));
    }
  };

  const handleNextPage = () => {
    if (currentPage < numPages) {
      const next = currentPage + 1;
      setCurrentPage(next);
      setPageInput(String(next));
    }
  };

  // Zoom Handlers
  const handleZoomIn = () => {
    setFitMode('custom');
    setScale((prev) => Math.min(3.0, +(prev + 0.25).toFixed(2)));
  };

  const handleZoomOut = () => {
    setFitMode('custom');
    setScale((prev) => Math.max(0.5, +(prev - 0.25).toFixed(2)));
  };

  const handleFitWidth = () => {
    setFitMode('width');
  };

  const handleResetZoom = () => {
    setFitMode('custom');
    setScale(1.0);
  };

  // Open in New Tab (Popout)
  const handlePopout = () => {
    if (pdfDataBuffer) {
      if (activeBlobUrlRef.current) {
        URL.revokeObjectURL(activeBlobUrlRef.current);
      }
      const blob = new Blob([pdfDataBuffer], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      activeBlobUrlRef.current = url;
      window.open(`${url}#page=${currentPage}`, '_blank');
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal fade show d-block"
      tabIndex="-1"
      style={{ backgroundColor: 'rgba(15, 23, 42, 0.8)', zIndex: 1060 }}
    >
      <div className="modal-dialog modal-xl modal-dialog-centered" style={{ height: '94vh', maxWidth: '96vw' }}>
        <div className="modal-content h-100 d-flex flex-column border-0 shadow-2xl bg-dark text-white rounded-3 overflow-hidden">
          {/* Header & Controls Toolbar */}
          <div className="modal-header bg-dark border-secondary border-opacity-50 py-2 px-3 align-items-center d-flex flex-wrap gap-2 justify-content-between">
            {/* Document Title & Revision */}
            <div className="d-flex align-items-center gap-2 overflow-hidden me-auto" style={{ minWidth: '220px' }}>
              <FileText size={18} className="text-primary flex-shrink-0" />
              <div className="text-truncate">
                <span className="fw-semibold small text-white text-truncate d-inline-block" style={{ maxWidth: '300px' }} title={documentTitle}>
                  {documentTitle}
                </span>
                <span className="badge bg-secondary ms-2 small">{revision}</span>
              </div>
            </div>

            {/* Pagination Controls */}
            {numPages > 0 && (
              <div className="d-flex align-items-center gap-1 bg-secondary bg-opacity-25 rounded px-2 py-1">
                <button
                  className="btn btn-sm btn-outline-light border-0 p-1"
                  onClick={handlePrevPage}
                  disabled={currentPage <= 1 || loadingDoc}
                  title="Previous Page"
                >
                  <ChevronLeft size={16} />
                </button>
                <div className="d-flex align-items-center gap-1 small text-white px-1">
                  <span>Page</span>
                  <input
                    type="text"
                    value={pageInput}
                    onChange={handlePageInputChange}
                    onBlur={handlePageInputCommit}
                    onKeyDown={handlePageInputKeyDown}
                    disabled={loadingDoc}
                    className="form-control form-control-sm text-center bg-dark text-white border-secondary px-1 py-0"
                    style={{ width: '48px', height: '26px', fontSize: '0.82rem' }}
                  />
                  <span>of {numPages}</span>
                </div>
                <button
                  className="btn btn-sm btn-outline-light border-0 p-1"
                  onClick={handleNextPage}
                  disabled={currentPage >= numPages || loadingDoc}
                  title="Next Page"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            )}

            {/* Zoom Controls */}
            {numPages > 0 && (
              <div className="d-flex align-items-center gap-1 bg-secondary bg-opacity-25 rounded px-2 py-1">
                <button
                  className="btn btn-sm btn-outline-light border-0 p-1"
                  onClick={handleZoomOut}
                  disabled={scale <= 0.5 || loadingDoc}
                  title="Zoom Out (Ctrl -)"
                >
                  <ZoomOut size={15} />
                </button>
                <span className="small text-white-50 px-1 font-monospace" style={{ minWidth: '42px', textAlign: 'center' }}>
                  {fitMode === 'width' ? 'Fit W' : fitMode === 'page' ? 'Fit H' : `${Math.round(scale * 100)}%`}
                </span>
                <button
                  className="btn btn-sm btn-outline-light border-0 p-1"
                  onClick={handleZoomIn}
                  disabled={scale >= 3.0 || loadingDoc}
                  title="Zoom In (Ctrl +)"
                >
                  <ZoomIn size={15} />
                </button>
                <button
                  className="btn btn-sm btn-outline-light border-0 p-1 ms-1"
                  onClick={handleFitWidth}
                  disabled={loadingDoc}
                  title="Fit to Width"
                >
                  <Maximize2 size={14} />
                </button>
                <button
                  className="btn btn-sm btn-outline-light border-0 p-1"
                  onClick={handleResetZoom}
                  disabled={loadingDoc}
                  title="Reset Zoom (100%)"
                >
                  <RotateCcw size={14} />
                </button>
              </div>
            )}

            {/* Action Buttons: Popout & Close */}
            <div className="d-flex align-items-center gap-2">
              {pdfDataBuffer && (
                <button
                  className="btn btn-sm btn-outline-light d-flex align-items-center gap-1 py-1 px-2"
                  onClick={handlePopout}
                  title="Open PDF in new browser tab"
                >
                  <ExternalLink size={14} />
                  <span className="d-none d-md-inline small">Popout</span>
                </button>
              )}
              <button
                type="button"
                className="btn-close btn-close-white"
                aria-label="Close"
                onClick={onClose}
              />
            </div>
          </div>

          {/* Modal Body / PDF Rendering Area */}
          <div
            ref={containerRef}
            className="modal-body p-0 flex-grow-1 position-relative d-flex justify-content-center align-items-center overflow-auto"
            style={{ backgroundColor: '#1e293b' }}
          >
            {/* Document Loading State */}
            {loadingDoc && (
              <div className="d-flex flex-column align-items-center justify-content-center p-4">
                <LoadingSpinner text="Retrieving protected PDF manual..." size="lg" />
              </div>
            )}

            {/* Error State */}
            {error && !loadingDoc && (
              <div className="p-4 text-center m-auto bg-dark border border-danger rounded-3" style={{ maxWidth: '440px' }}>
                <AlertCircle size={44} className="text-danger mb-2" />
                <h6 className="fw-bold text-white mb-2">Technical Manual Unavailable</h6>
                <p className="text-white-50 small mb-3">{error}</p>
                <div className="d-flex justify-content-center gap-2">
                  <button
                    className="btn btn-sm btn-primary d-flex align-items-center gap-1"
                    onClick={() => {
                      setError(null);
                      setLoadingDoc(true);
                      documentService
                        .getDocumentPdfBinary(documentId)
                        .then((buf) => {
                          setPdfDataBuffer(buf);
                          return pdfjsLib.getDocument({ data: new Uint8Array(buf) }).promise;
                        })
                        .then((doc) => {
                          setPdfDoc(doc);
                          setNumPages(doc.numPages);
                          setCurrentPage(1);
                        })
                        .catch((e) => setError(e.message || 'Retry failed.'))
                        .finally(() => setLoadingDoc(false));
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

            {/* Active Canvas Display */}
            {!loadingDoc && !error && (
              <div className="d-flex flex-column align-items-center my-3 mx-auto shadow-lg position-relative">
                {renderingPage && (
                  <div
                    className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
                    style={{ backgroundColor: 'rgba(15, 23, 42, 0.4)', zIndex: 10 }}
                  >
                    <div className="spinner-border text-primary spinner-border-sm" role="status">
                      <span className="visually-hidden">Rendering page...</span>
                    </div>
                  </div>
                )}
                <canvas
                  ref={canvasRef}
                  className="bg-white rounded shadow-sm border border-secondary"
                  style={{ display: numPages > 0 ? 'block' : 'none' }}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
