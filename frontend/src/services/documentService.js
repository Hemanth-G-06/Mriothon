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
        response = await apiClient.post('/documents/upload/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress
        });
      } catch (err404) {
        if (err404.response && (err404.response.status === 404 || err404.response.status === 405)) {
          response = await apiClient.post('/documents/', formData, {
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
        const manualType = formData.get('manual_type') || 'Operations Manual';
        const modelNumber = formData.get('model_number') || 'N/A';
        const revision = formData.get('revision') || 'Rev 1.0';

        const newDoc = {
          id: Date.now(),
          machine_id: Number(machineId),
          machine_name: 'Machine #' + machineId,
          title,
          manual_type: manualType,
          model_number: modelNumber,
          revision,
          file_name: file ? file.name : 'manual.pdf',
          file_size: file ? file.size : 1024000,
          status: 'Uploaded', // Initially Uploaded, backend worker will change to Indexed
          created_at: new Date().toISOString(),
          pdf_url: null
        };
        mockDocumentsState = [newDoc, ...mockDocumentsState];
        return newDoc;
      }
      throw err;
    }
  },

  /**
   * Fetch protected PDF binary or URL for viewing
   */
  async getDocumentPdfUrl(docId) {
    try {
      // First attempt to get the protected PDF binary stream with auth header
      let response;
      try {
        response = await apiClient.get(`/documents/${docId}/pdf/`, {
          responseType: 'blob'
        });
      } catch (err404) {
        if (err404.response && (err404.response.status === 404 || err404.response.status === 405)) {
          response = await apiClient.get(`/documents/${docId}/download/`, {
            responseType: 'blob'
          });
        } else {
          throw err404;
        }
      }
      const blob = new Blob([response.data], { type: 'application/pdf' });
      return URL.createObjectURL(blob);
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[documentService] Returning placeholder sample PDF for viewer demo');
        // Return a reliable data URI or empty pdf blob for demo if backend is offline
        return null;
      }
      throw err;
    }
  }
};
