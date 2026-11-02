import React, { useState, useEffect } from 'react';
import {
  Scan,
  Package,
  AlertCircle,
  CheckCircle2,
  Cpu,
  Layers,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  Sparkles
} from 'lucide-react';
import { inspectionService } from '../../services/inspectionService';
import ImageUploader from '../../components/inspection/ImageUploader';
import InspectionResultCard from '../../components/inspection/InspectionResultCard';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { getErrorMessage } from '../../utils/errorHandler';

/**
 * Single Image Quality Inspection Page
 * Allows engineers to submit an individual product plate image for AI computer vision inspection.
 */
export default function QualityInspectionPage() {
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('P-PLATE01');
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileMetadata, setFileMetadata] = useState(null);
  const [isLoadingProducts, setIsLoadingProducts] = useState(true);
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectionResult, setInspectionResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Load registered products
  useEffect(() => {
    const loadProducts = async () => {
      setIsLoadingProducts(true);
      try {
        const list = await inspectionService.getProducts();
        setProducts(list);
        if (list.length > 0 && !list.some((p) => p.id === selectedProductId)) {
          setSelectedProductId(list[0].id);
        }
      } catch (err) {
        console.warn('Failed to load products:', err);
      } finally {
        setIsLoadingProducts(false);
      }
    };
    loadProducts();
  }, []);

  const handleImageChange = (file, meta) => {
    setSelectedFile(file);
    setFileMetadata(meta);
    setErrorMessage(null);
    setInspectionResult(null);
  };

  const handleInspect = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select or drag-and-drop a valid plate image before starting inspection.');
      return;
    }
    if (!selectedProductId) {
      setErrorMessage('Please select a target product.');
      return;
    }

    setIsInspecting(true);
    setErrorMessage(null);
    setInspectionResult(null);

    const formData = new FormData();
    formData.append('product_id', selectedProductId);
    formData.append('file', selectedFile);

    try {
      const response = await inspectionService.createSingleInspection(formData);
      // Attach local object preview URL if backend did not supply a full image_url
      if (!response.image_url && fileMetadata?.previewUrl) {
        response.previewUrl = fileMetadata.previewUrl;
      }
      setInspectionResult(response);
    } catch (err) {
      console.error('Inspection failed:', err);
      const backendError = getErrorMessage(
        err,
        'Backend inspection endpoint (/api/inspections/single/) did not respond. Please ensure the Django AI inspection service is running.'
      );
      setErrorMessage(backendError);
    } finally {
      setIsInspecting(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setFileMetadata(null);
    setInspectionResult(null);
    setErrorMessage(null);
  };

  const selectedProduct = products.find((p) => p.id === selectedProductId) || {
    id: 'P-PLATE01',
    name: 'Industrial Metal Base Plate',
    model_version: 'BIT-PLATE-CV-1.0'
  };

  return (
    <div className="container-fluid p-0">
      {/* Page Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <div className="d-flex align-items-center gap-2 mb-1">
            <h4 className="fw-bold text-dark mb-0">Visual Quality Inspection</h4>
            <span className="badge bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 d-flex align-items-center gap-1 small">
              <Scan size={12} /> Single Image Mode
            </span>
          </div>
          <p className="text-muted small mb-0">
            Real-time computer vision inference to detect surface defects and structural anomalies in manufactured components.
          </p>
        </div>
      </div>

      {/* Target Product Selection Bar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-3 align-items-center">
          <div className="col-12 col-md-5 col-lg-4">
            <label className="form-label small fw-semibold text-secondary mb-1 d-flex align-items-center gap-1">
              <Package size={14} className="text-primary" /> Target Inspection Product
            </label>
            <select
              className="form-select form-select-sm"
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              disabled={isInspecting || isLoadingProducts}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="col-12 col-md-7 col-lg-8 border-md-start ps-md-4">
            <div className="d-flex flex-wrap align-items-center gap-3 small text-muted">
              <div>
                <span className="text-secondary">Classifier Model:</span>{' '}
                <strong className="text-dark font-monospace">{selectedProduct.model_version || 'BIT-PLATE-CV-1.0'}</strong>
              </div>
              <span>•</span>
              <div>
                <span className="text-secondary">Classes:</span>{' '}
                <strong className="text-success">Normal</strong> / <strong className="text-danger">Defective</strong>
              </div>
              <span>•</span>
              <div>
                <span className="text-secondary">Specs:</span>{' '}
                <span>JPEG/PNG &bull; 64×64 to 4096×4096 px &bull; Max 5 MiB</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="alert alert-danger py-3 small d-flex align-items-start justify-content-between mb-4" role="alert">
          <div className="d-flex align-items-start gap-2">
            <AlertCircle size={18} className="text-danger flex-shrink-0 mt-1" />
            <div>
              <div className="fw-bold mb-1">Inspection Request Error</div>
              <div>{errorMessage}</div>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-link text-danger p-0 ms-3"
            onClick={() => setErrorMessage(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Inspection Area */}
      {!inspectionResult ? (
        <div className="row g-4">
          <div className="col-12 col-lg-8">
            <div className="card card-industrial p-4 bg-white mb-3">
              <h6 className="fw-bold text-dark mb-3 d-flex align-items-center gap-2">
                <Scan size={18} className="text-primary" /> Image Upload & Drag-and-Drop
              </h6>

              <ImageUploader
                multiple={false}
                value={selectedFile}
                onChange={handleImageChange}
                disabled={isInspecting}
              />

              <div className="d-flex justify-content-between align-items-center mt-4 pt-3 border-top">
                <span className="text-muted small">
                  {selectedFile ? 'Image ready for model inference' : 'Select an image to enable inspection'}
                </span>

                <button
                  type="button"
                  className="btn btn-primary-industrial btn-sm px-4 d-flex align-items-center gap-2"
                  onClick={handleInspect}
                  disabled={!selectedFile || isInspecting}
                >
                  {isInspecting ? (
                    <>
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      <span>Processing Image...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      <span>Inspect Image</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Right: Challenge Instructions & Guidance Card */}
          <div className="col-12 col-lg-4">
            <div className="card card-industrial p-3 bg-white h-100">
              <h6 className="fw-bold text-dark mb-2 d-flex align-items-center gap-2">
                <ShieldCheck size={16} className="text-primary" /> Quality Criteria Guide
              </h6>
              <p className="text-muted small mb-3">
                The visual quality inspection system uses the verified <strong>BIT-PLATE-CV-1.0</strong> architecture to evaluate surface integrity.
              </p>

              <div className="d-flex flex-column gap-2 small">
                <div className="p-2 rounded bg-light border">
                  <div className="fw-semibold text-success mb-1 d-flex align-items-center gap-1">
                    <CheckCircle2 size={13} /> Class: Normal
                  </div>
                  <div className="text-muted" style={{ fontSize: '0.74rem' }}>
                    Component meets all structural specifications with smooth milling lines and no surface cracks or micro-fractures.
                  </div>
                </div>

                <div className="p-2 rounded bg-light border">
                  <div className="fw-semibold text-danger mb-1 d-flex align-items-center gap-1">
                    <AlertCircle size={13} /> Class: Defective
                  </div>
                  <div className="text-muted" style={{ fontSize: '0.74rem' }}>
                    Flagged for irregularities, deep scratches, burrs, pitting, voids, or dimensional warping. Escalated for supervisor review.
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-3 border-top text-muted small" style={{ fontSize: '0.72rem' }}>
                Inspection decisions are logged to the persistent inspection history for supervisor audit.
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Inspection Result Card */
        <InspectionResultCard result={inspectionResult} onReset={handleReset} />
      )}
    </div>
  );
}
