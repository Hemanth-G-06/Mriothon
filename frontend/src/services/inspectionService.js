/**
 * Visual Quality Inspection API Service
 *
 * Centralized service for Module B: AI Visual Quality Inspection.
 *
 * FRONTEND API CONTRACT SPECIFICATION:
 * -----------------------------------------------------------------------------------------
 * 1. Products Management:
 *    - GET  /products/              -> List registered products
 *    - POST /products/              -> Register new product { id, name, description, model_version }
 *    - GET  /products/:id/          -> Retrieve specific product
 *
 * 2. Single Image Inspection:
 *    - POST /inspections/single/ (or /inspections/)
 *      Payload: multipart/form-data
 *        - product_id: string (e.g. "P-PLATE01")
 *        - file: File (JPEG/PNG, max 5 MiB, 64x64 to 4096x4096)
 *      Response Schema:
 *        {
 *          id: string | number,
 *          product_id: string,
 *          image_url: string,
 *          predicted_class: "Normal" | "Defective",
 *          confidence: number,           // e.g. 0.984 or 98.4
 *          defect_probability: number,   // e.g. 0.016 or 1.6
 *          model_version: string,        // e.g. "BIT-PLATE-CV-1.0"
 *          status: "Completed" | "Processing" | "Failed",
 *          created_at: string (ISO),
 *          review_status: "pending" | "confirmed" | "corrected"
 *        }
 *
 * 3. Batch Image Inspection:
 *    - POST /inspections/batch/
 *      Payload: multipart/form-data
 *        - product_id: string
 *        - files: File[] (1 to 10 images)
 *      Response Schema:
 *        {
 *          batch_id: string,
 *          total: number,
 *          items: Array<{
 *            id: string | number,
 *            file_name: string,
 *            status: "Queued" | "Processing" | "Completed" | "Failed",
 *            predicted_class?: "Normal" | "Defective",
 *            confidence?: number,
 *            image_url?: string,
 *            error?: string
 *          }>
 *        }
 *    - GET /inspections/batch/:batchId/
 *      Response Schema: Updated batch object with progress status
 *
 * 4. Inspection History (Engineer scoped):
 *    - GET /inspections/
 *      Query Params: ?search=...&predicted_class=...&status=...&review_status=...&date=...&page=...
 *      Response: Array<Inspection> or { results: Array<Inspection>, count: number }
 *    - GET /inspections/:id/
 *      Response: Detailed inspection record
 *
 * 5. Supervisor Inspection Review:
 *    - GET /supervisor/inspections/ or /inspections/?review_status=pending
 *      Query Params: ?status=...&predicted_class=...&date=...
 *    - POST /inspections/:id/review/ (or /supervisor/inspections/:id/review/)
 *      Payload:
 *        {
 *          action: "confirm" | "correct",
 *          corrected_class?: "Normal" | "Defective",
 *          comment?: string
 *        }
 *      Response Schema:
 *        Updated inspection record with supervisor audit details:
 *        {
 *          ...inspection,
 *          review_status: "confirmed" | "corrected",
 *          supervisor_class: "Normal" | "Defective",
 *          supervisor_name: string,
 *          reviewed_at: string,
 *          review_comment: string
 *        }
 * -----------------------------------------------------------------------------------------
 */

import apiClient from './api';

// Challenge-mandated product default definition
export const DEFAULT_PRODUCTS = [
  {
    id: 'P-PLATE01',
    name: 'Industrial Metal Base Plate',
    model_version: 'BIT-PLATE-CV-1.0',
    description: 'Precision milled metallic mounting plate inspected for surface cracks, porosities, warping, and machining defects.',
    category: 'Milled Components',
    min_dimensions: '64 × 64 px',
    max_dimensions: '4096 × 4096 px',
    max_file_size: '5 MiB',
    allowed_formats: 'JPEG, PNG',
    status: 'Active',
    created_at: '2026-01-15T08:00:00.000Z'
  }
];

// Local storage key for persistent custom products cache
const PRODUCTS_STORAGE_KEY = 'mriothon_registered_products';

function getLocalProducts() {
  try {
    const raw = localStorage.getItem(PRODUCTS_STORAGE_KEY);
    if (!raw) {
      localStorage.setItem(PRODUCTS_STORAGE_KEY, JSON.stringify(DEFAULT_PRODUCTS));
      return DEFAULT_PRODUCTS;
    }
    const parsed = JSON.parse(raw);
    // Ensure P-PLATE01 is always present
    if (!parsed.some((p) => p.id === 'P-PLATE01')) {
      parsed.unshift(DEFAULT_PRODUCTS[0]);
    }
    return parsed;
  } catch {
    return DEFAULT_PRODUCTS;
  }
}

function saveLocalProduct(newProduct) {
  try {
    const current = getLocalProducts();
    const existingIndex = current.findIndex((p) => p.id === newProduct.id);
    let updated;
    if (existingIndex >= 0) {
      updated = [...current];
      updated[existingIndex] = { ...updated[existingIndex], ...newProduct };
    } else {
      updated = [newProduct, ...current];
    }
    localStorage.setItem(PRODUCTS_STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (err) {
    console.error('Failed to cache product locally:', err);
    return getLocalProducts();
  }
}

export const inspectionService = {
  // ==========================================
  // 1. PRODUCT REGISTRATION & CATALOG
  // ==========================================

  /**
   * Fetch all registered inspection products.
   * Calls /products/ API, and merges with local registered products.
   */
  async getProducts() {
    try {
      const response = await apiClient.get('/products/');
      const data = response.data;
      const apiList = Array.isArray(data) ? data : (data?.results || []);
      if (apiList.length > 0) {
        // Ensure P-PLATE01 is represented
        if (!apiList.some((p) => p.id === 'P-PLATE01')) {
          return [...DEFAULT_PRODUCTS, ...apiList];
        }
        return apiList;
      }
      return getLocalProducts();
    } catch (err) {
      // Backend /products/ might not be implemented yet or network issue
      console.warn('[inspectionService] Backend /products/ unavailable, using cached product catalog:', err?.message);
      return getLocalProducts();
    }
  },

  /**
   * Fetch a single product by ID
   * @param {string} productId
   */
  async getProductById(productId) {
    try {
      const response = await apiClient.get(`/products/${productId}/`);
      return response.data;
    } catch (err) {
      const local = getLocalProducts().find((p) => p.id === productId);
      if (local) return local;
      throw err;
    }
  },

  /**
   * Register a new product
   * @param {Object} productData - { id, name, description, model_version, category }
   */
  async createProduct(productData) {
    // Standardize product ID to uppercase
    const standardized = {
      ...productData,
      id: productData.id ? productData.id.trim().toUpperCase() : `P-${Date.now()}`,
      model_version: productData.model_version || 'BIT-PLATE-CV-1.0',
      status: 'Active',
      created_at: new Date().toISOString()
    };

    try {
      const response = await apiClient.post('/products/', standardized);
      saveLocalProduct(response.data || standardized);
      return response.data || standardized;
    } catch (err) {
      console.warn('[inspectionService] Backend /products/ POST failed, saving to local catalog:', err?.message);
      saveLocalProduct(standardized);
      return standardized;
    }
  },

  // ==========================================
  // 2. SINGLE IMAGE INSPECTION
  // ==========================================

  /**
   * Submit single image for AI inspection
   * @param {FormData} formData - Contains 'file' (image) and 'product_id'
   */
  async createSingleInspection(formData) {
    // Attempt standard single inspection endpoint, then fallback to base /inspections/
    try {
      const response = await apiClient.post('/inspections/single/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      return response.data;
    } catch (err) {
      if (err.response?.status === 404) {
        // Retry at alternative standard path /inspections/
        const retryRes = await apiClient.post('/inspections/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
        return retryRes.data;
      }
      throw err;
    }
  },

  // ==========================================
  // 3. BATCH IMAGE INSPECTION
  // ==========================================

  /**
   * Submit a batch of 1-10 images for AI inspection
   * @param {FormData} formData - Contains multiple 'files' (or 'images') and 'product_id'
   */
  async createBatchInspection(formData) {
    const response = await apiClient.post('/inspections/batch/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  },

  /**
   * Check status of an asynchronous batch inspection
   * @param {string|number} batchId
   */
  async getBatchStatus(batchId) {
    const response = await apiClient.get(`/inspections/batch/${batchId}/`);
    return response.data;
  },

  // ==========================================
  // 4. INSPECTION HISTORY & DETAILS
  // ==========================================

  /**
   * Fetch inspection history with filters
   * @param {Object} filters - { search, predicted_class, status, review_status, date, page, product_id }
   */
  async getInspectionHistory(filters = {}) {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.predicted_class && filters.predicted_class !== 'all') {
      params.append('predicted_class', filters.predicted_class);
    }
    if (filters.status && filters.status !== 'all') {
      params.append('status', filters.status);
    }
    if (filters.review_status && filters.review_status !== 'all') {
      params.append('review_status', filters.review_status);
    }
    if (filters.date) params.append('date', filters.date);
    if (filters.product_id) params.append('product_id', filters.product_id);
    if (filters.page) params.append('page', filters.page);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    const response = await apiClient.get(`/inspections/${queryString}`);
    const data = response.data;
    if (Array.isArray(data)) return { results: data, count: data.length };
    if (data && Array.isArray(data.results)) return data;
    return { results: [], count: 0 };
  },

  /**
   * Fetch all inspection records for a specific product
   * Used by Admin Product Details -> Engineer Image Gallery
   * Calls: GET /api/inspections/?product_id=${productId}
   * @param {string} productId - e.g. "P-PLATE01"
   * @param {Object} extraFilters - { search, predicted_class, status, review_status, date, page }
   */
  async getInspectionsByProduct(productId, extraFilters = {}) {
    return this.getInspectionHistory({ ...extraFilters, product_id: productId });
  },

  /**
   * Alias for getInspectionHistory
   */
  async getInspections(filters) {
    return this.getInspectionHistory(filters);
  },

  /**
   * Fetch detailed inspection record by ID
   * @param {string|number} id
   */
  async getInspectionById(id) {
    const response = await apiClient.get(`/inspections/${id}/`);
    return response.data;
  },

  // ==========================================
  // 5. SUPERVISOR INSPECTION REVIEW
  // ==========================================

  /**
   * Fetch completed inspections requiring supervisor review
   * @param {Object} filters
   */
  async getPendingReviews(filters = {}) {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.predicted_class && filters.predicted_class !== 'all') {
      params.append('predicted_class', filters.predicted_class);
    }
    if (filters.review_status && filters.review_status !== 'all') {
      params.append('review_status', filters.review_status);
    }
    if (filters.date) params.append('date', filters.date);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    try {
      const response = await apiClient.get(`/supervisor/inspections/${queryString}`);
      const data = response.data;
      if (Array.isArray(data)) return { results: data, count: data.length };
      if (data && Array.isArray(data.results)) return data;
      return { results: [], count: 0 };
    } catch (err) {
      if (err.response?.status === 404) {
        // Fallback to /inspections/ endpoint with review filters
        const fallbackRes = await apiClient.get(`/inspections/${queryString}`);
        const data = fallbackRes.data;
        if (Array.isArray(data)) return { results: data, count: data.length };
        if (data && Array.isArray(data.results)) return data;
      }
      throw err;
    }
  },

  /**
   * Submit supervisor review for an inspection
   * @param {string|number} id
   * @param {Object} reviewData - { action: 'confirm'|'correct', corrected_class?: 'Normal'|'Defective', comment?: string }
   */
  async submitInspectionReview(id, reviewData) {
    try {
      const response = await apiClient.post(`/inspections/${id}/review/`, reviewData);
      return response.data;
    } catch (err) {
      if (err.response?.status === 404) {
        // Retry alternative path /supervisor/inspections/:id/review/
        const retryRes = await apiClient.post(`/supervisor/inspections/${id}/review/`, reviewData);
        return retryRes.data;
      }
      throw err;
    }
  }
};

export default inspectionService;
