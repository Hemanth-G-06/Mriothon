import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_DOCUMENTS } from './mockData';

let mockDocumentsState = [...INITIAL_MOCK_DOCUMENTS];

export const documentService = {
  /**
   * Fetch all documents, optionally filtered by machineId
   */
  async getDocuments(machineId = null) {
    try {
      const params = machineId ? { machine_id: machineId } : {};
      const response = await apiClient.get('/documents/', { params });
      const data = response.data;
      if (Array.isArray(data)) return data;
      if (data && Array.isArray(data.results)) return data.results;
      return [];
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[documentService] Backend offline, using mock documents');
        if (machineId) {
          return mockDocumentsState.filter((d) => String(d.machine_id) === String(machineId));
        }
        return [...mockDocumentsState];
      }
      throw err;
    }
  },

  /**
   * Fetch single document by ID
   */
  async getDocumentById(docId) {
    try {
      const response = await apiClient.get(`/documents/${docId}/`);
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const found = mockDocumentsState.find((d) => String(d.id) === String(docId));
        if (found) return found;
      }
      throw err;
    }
  },

  /**
   * Upload manual PDF with metadata
   * @param {FormData} formData
   * @param {Function} onUploadProgress
   */
  async uploadDocument(formData, onUploadProgress = null) {
    try {
      let response;
      try {
        // Direct DRF DocumentViewSet create endpoint
        response = await apiClient.post('/documents/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress
        });
      } catch (err404) {
        if (err404.response && (err404.response.status === 404 || err404.response.status === 405)) {
          response = await apiClient.post('/documents/upload/', formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            },
            onUploadProgress
          });
        } else {
          throw err404;
        }
      }
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[documentService] Backend offline, creating mock document');
        const file = formData.get('file');
        const machineId = formData.get('machine_id') || formData.get('machine');
        const title = formData.get('title') || file?.name || 'Uploaded Manual';
        const modelNumber = formData.get('model_number') || 'N/A';
        const revision = formData.get('revision') || 'Rev 1.0';

        const newDoc = {
          id: 'doc-mock-' + Date.now(),
          machine_id: machineId,
          machine_name: 'Machine #' + machineId,
          title,
          model_number: modelNumber,
          revision,
          original_filename: file ? file.name : 'manual.pdf',
          file_size: file ? file.size : 1024000,
          status: 'READY',
          created_at: new Date().toISOString()
        };
        mockDocumentsState = [newDoc, ...mockDocumentsState];
        return newDoc;
      }
      throw err;
    }
  },

  /**
   * Trigger ChromaDB vector indexing for an extracted PDF document
   * @param {string} docId
   */
  async indexDocument(docId) {
    const response = await apiClient.post(`/documents/${docId}/index/`);
    return response.data;
  },

  /**
   * Fetch current ChromaDB indexing status for a document
   * @param {string} docId
   */
  async getIndexStatus(docId) {
    const response = await apiClient.get(`/documents/${docId}/index-status/`);
    return response.data;
  },

  /**
   * Fetch protected PDF binary as ArrayBuffer for PDF.js rendering
   * @param {string} docId
   * @returns {Promise<ArrayBuffer>}
   */
  async getDocumentPdfBinary(docId) {
    try {
      let response;
      try {
        response = await apiClient.get(`/documents/${docId}/pdf/`, {
          responseType: 'arraybuffer'
        });
      } catch (errFallback) {
        if (errFallback.response && (errFallback.response.status === 404 || errFallback.response.status === 405)) {
          response = await apiClient.get(`/documents/${docId}/download/`, {
            responseType: 'arraybuffer'
          });
        } else {
          throw errFallback;
        }
      }
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[documentService] Backend offline, returning empty buffer for mock preview');
        return new ArrayBuffer(0);
      }
      throw err;
    }
  },

  /**
   * Delete a technical manual document and clean up its vector index
   * @param {string} docId
   * @param {boolean} permanent
   */
  async deleteDocument(docId, permanent = true) {
    const response = await apiClient.delete(`/documents/${docId}/`, {
      params: permanent ? { permanent: 'true' } : {}
    });
    return response.data;
  },

  /**
   * Fetch protected PDF binary stream or blob URL for viewing
   * @param {string} docId
   */
  async getDocumentPdfUrl(docId) {
    try {
      let response;
      try {
        // Preferred authenticated PDF streaming endpoint
        response = await apiClient.get(`/documents/${docId}/pdf/`, {
          responseType: 'blob'
        });
      } catch (errFallback) {
        if (errFallback.response && (errFallback.response.status === 404 || errFallback.response.status === 405)) {
          response = await apiClient.get(`/documents/${docId}/download/`, {
            responseType: 'blob'
          });
        } else {
          throw errFallback;
        }
      }

      const blob = new Blob([response.data], { type: 'application/pdf' });
      return URL.createObjectURL(blob);
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[documentService] Returning placeholder sample PDF for viewer demo');
        return null;
      }
      throw err;
    }
  }
};
