import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Package,
  Plus,
  Search,
  CheckCircle2,
  AlertCircle,
  Eye,
  Cpu,
  Layers,
  FileCheck,
  ShieldCheck,
  Tag
} from 'lucide-react';
import { inspectionService, DEFAULT_PRODUCTS } from '../../services/inspectionService';
import ProductInspectionGallery from '../../components/inspection/ProductInspectionGallery';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

/**
 * Admin Products Page
 * Manage registered product catalog for Visual Quality Inspection.
 * Required product: P-PLATE01 (Model: BIT-PLATE-CV-1.0)
 */
export default function ProductsPage() {
  const { productId } = useParams();
  const navigate = useNavigate();

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  // Form State
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    model_version: 'BIT-PLATE-CV-1.0',
    category: 'Milled Components',
    description: ''
  });

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const list = await inspectionService.getProducts();
      setProducts(Array.isArray(list) ? list : []);
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to retrieve registered products.')
      });
      setProducts(DEFAULT_PRODUCTS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  // Sync selected product with URL parameter if present
  useEffect(() => {
    if (productId && products.length > 0) {
      const found = products.find((p) => p.id?.toUpperCase() === productId.toUpperCase());
      if (found) {
        setSelectedProduct(found);
      } else {
        inspectionService
          .getProductById(productId)
          .then((p) => setSelectedProduct(p))
          .catch(() => {
            setSelectedProduct({ id: productId, name: productId, model_version: 'BIT-PLATE-CV-1.0' });
          });
      }
    }
  }, [productId, products]);

  const handleSelectProductForDetail = (prod) => {
    setSelectedProduct(prod);
    navigate(`/admin/products/${prod.id}`);
  };

  const handleBackFromDetail = () => {
    setSelectedProduct(null);
    navigate('/admin/products');
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleOpenModal = () => {
    setFormData({
      id: '',
      name: '',
      model_version: 'BIT-PLATE-CV-1.0',
      category: 'Milled Components',
      description: ''
    });
    setShowModal(true);
    setFeedback({ type: '', message: '' });
  };

  const handleQuickRegisterPlate01 = async () => {
    setIsSubmitting(true);
    try {
      const pPlate = DEFAULT_PRODUCTS[0];
      await inspectionService.createProduct(pPlate);
      setFeedback({
        type: 'success',
        message: 'Product "P-PLATE01" (BIT-PLATE-CV-1.0) successfully registered in catalog!'
      });
      await fetchProducts();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to register product P-PLATE01.')
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.id.trim() || !formData.name.trim()) {
      setFeedback({ type: 'danger', message: 'Product ID and Product Name are required.' });
      return;
    }

    setIsSubmitting(true);
    setFeedback({ type: '', message: '' });

    try {
      await inspectionService.createProduct(formData);
      setFeedback({
        type: 'success',
        message: `Product "${formData.id.toUpperCase()}" successfully registered!`
      });
      setShowModal(false);
      await fetchProducts();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Error registering product.')
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredProducts = (products || []).filter(
    (p) =>
      p.id?.toLowerCase().includes(search.toLowerCase()) ||
      p.name?.toLowerCase().includes(search.toLowerCase()) ||
      p.category?.toLowerCase().includes(search.toLowerCase()) ||
      p.model_version?.toLowerCase().includes(search.toLowerCase())
  );

  const hasPlate01 = products.some((p) => p.id === 'P-PLATE01');

  // If a product is selected, render the full Product Details & Engineer Image Gallery View
  if (selectedProduct) {
    return (
      <div className="container-fluid p-0">
        <ProductInspectionGallery
          product={selectedProduct}
          onBack={handleBackFromDetail}
        />
      </div>
    );
  }

  return (
    <div className="container-fluid p-0">
      {/* Page Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h4 className="fw-bold text-dark mb-1">Product Registry</h4>
          <p className="text-muted small mb-0">
            Register and manage manufactured product identifiers inspected by AI Computer Vision models.
          </p>
        </div>
        <div className="d-flex flex-wrap gap-2">
          {!hasPlate01 && (
            <button
              onClick={handleQuickRegisterPlate01}
              className="btn btn-outline-primary btn-sm d-flex align-items-center gap-1"
              disabled={isSubmitting}
            >
              <Package size={15} /> Quick Register P-PLATE01
            </button>
          )}
          <button
            onClick={handleOpenModal}
            className="btn btn-primary-industrial btn-sm d-flex align-items-center gap-1"
          >
            <Plus size={16} /> Register New Product
          </button>
        </div>
      </div>

      {/* Global Feedback message */}
      {feedback.message && !showModal && (
        <div className={`alert alert-${feedback.type} alert-dismissible fade show py-2 small mb-3`} role="alert">
          <div className="d-flex align-items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{feedback.message}</span>
          </div>
          <button type="button" className="btn-close py-2" onClick={() => setFeedback({ type: '', message: '' })} />
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-2 align-items-center">
          <div className="col-12 col-md-6 col-lg-4">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                className="form-control border-start-0"
                placeholder="Search by Product ID, Name, Model..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="col-12 col-md-6 col-lg-8 text-md-end text-muted small">
            Displaying <strong>{filteredProducts.length}</strong> of {products.length} registered products
          </div>
        </div>
      </div>

      {/* Products Grid */}
      {loading ? (
        <LoadingSpinner text="Retrieving product catalog..." size="lg" />
      ) : filteredProducts.length === 0 ? (
        <EmptyState
          title="No Products Found"
          description={search ? `No product matched "${search}".` : 'No products registered yet.'}
          icon={Package}
          actionButton={
            <button onClick={handleQuickRegisterPlate01} className="btn btn-sm btn-primary-industrial mt-2">
              Register P-PLATE01
            </button>
          }
        />
      ) : (
        <div className="row g-3">
          {filteredProducts.map((prod) => (
            <div key={prod.id} className="col-12 col-md-6 col-xl-4">
              <div className="card card-industrial h-100 p-3 bg-white d-flex flex-column">
                <div className="d-flex align-items-start justify-content-between mb-2">
                  <div className="p-2 rounded bg-primary bg-opacity-10 text-primary">
                    <Package size={20} />
                  </div>
                  <span className="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 small">
                    {prod.status || 'Active'}
                  </span>
                </div>

                <div className="d-flex align-items-baseline gap-2 mb-1">
                  <span className="font-monospace fw-bold text-primary fs-6">{prod.id}</span>
                  {prod.id === 'P-PLATE01' && (
                    <span className="badge bg-warning bg-opacity-25 text-warning-emphasis" style={{ fontSize: '0.65rem' }}>
                      Challenge Target
                    </span>
                  )}
                </div>
                <h6 className="fw-bold text-dark mb-1">{prod.name}</h6>

                <div className="d-flex flex-column gap-1 my-2 py-2 border-top border-bottom small text-muted">
                  <div className="d-flex align-items-center gap-2">
                    <Cpu size={13} className="text-secondary" />
                    <span>CV Model: <strong className="text-dark font-monospace">{prod.model_version || 'BIT-PLATE-CV-1.0'}</strong></span>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <Tag size={13} className="text-secondary" />
                    <span>Category: <strong className="text-dark">{prod.category || 'Milled Parts'}</strong></span>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <Layers size={13} className="text-secondary" />
                    <span>Dimensions: <span className="font-monospace">{prod.min_dimensions || '64x64'} to {prod.max_dimensions || '4096x4096'}</span></span>
                  </div>
                </div>

                <p className="text-muted small flex-grow-1 mb-3" style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
                  {prod.description || 'No detailed specifications entered.'}
                </p>

                <div className="pt-2 border-top d-flex justify-content-between align-items-center text-muted" style={{ fontSize: '0.72rem' }}>
                  <span>{formatDateTime(prod.created_at)}</span>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary py-0 px-2 d-flex align-items-center gap-1"
                    style={{ fontSize: '0.75rem' }}
                    onClick={() => handleSelectProductForDetail(prod)}
                  >
                    <Eye size={12} /> View Details
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Register Product Modal */}
      {showModal && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0 shadow">
              <div className="modal-header">
                <h5 className="modal-title fw-bold">Register Inspection Product</h5>
                <button type="button" className="btn-close" onClick={() => !isSubmitting && setShowModal(false)} />
              </div>
              <form onSubmit={handleSubmit}>
                <div className="modal-body p-4">
                  {feedback.message && (
                    <div className="alert alert-danger py-2 small mb-3">{feedback.message}</div>
                  )}

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Product ID *</label>
                    <input
                      type="text"
                      name="id"
                      className="form-control form-control-sm font-monospace text-uppercase"
                      placeholder="e.g. P-PLATE01"
                      value={formData.id}
                      onChange={handleInputChange}
                      required
                      disabled={isSubmitting}
                    />
                    <div className="form-text" style={{ fontSize: '0.72rem' }}>
                      Unique product code (Challenge requirement: <strong>P-PLATE01</strong>)
                    </div>
                  </div>

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Product Name *</label>
                    <input
                      type="text"
                      name="name"
                      className="form-control form-control-sm"
                      placeholder="e.g. Industrial Metal Base Plate"
                      value={formData.name}
                      onChange={handleInputChange}
                      required
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="row g-2 mb-3">
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">CV Model Version</label>
                      <input
                        type="text"
                        name="model_version"
                        className="form-control form-control-sm font-monospace"
                        placeholder="e.g. BIT-PLATE-CV-1.0"
                        value={formData.model_version}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">Category</label>
                      <input
                        type="text"
                        name="category"
                        className="form-control form-control-sm"
                        placeholder="e.g. Milled Components"
                        value={formData.category}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  <div className="mb-0">
                    <label className="form-label small fw-semibold text-secondary">Description & Quality Specifications</label>
                    <textarea
                      name="description"
                      rows={3}
                      className="form-control form-control-sm"
                      placeholder="e.g. Surface defect inspection for hairline cracks, porosities, and edge burrs..."
                      value={formData.description}
                      onChange={handleInputChange}
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                <div className="modal-footer bg-light py-2 px-4">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => setShowModal(false)}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-sm btn-primary-industrial d-flex align-items-center gap-1"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                        <span>Registering...</span>
                      </>
                    ) : (
                      <>
                        <Plus size={15} /> Save Product
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
