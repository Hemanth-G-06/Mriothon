import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_CHAT_HISTORY } from './mockData';
import { INSUFFICIENT_EVIDENCE_MESSAGE } from '../utils/constants';

let mockChatState = [...INITIAL_MOCK_CHAT_HISTORY];

export const chatService = {
  /**
   * Ask question for a selected machine using the real Gemini-backed RAG API
   * @param {string|number} machineId
   * @param {string} question
   */
  async askQuestion(machineId, question) {
    try {
      let response;
      try {
        // Primary backend endpoint: POST /api/rag/query/
        response = await apiClient.post('/rag/query/', {
          machine_id: machineId,
          question: question.trim()
        });
      } catch (errFallback) {
        if (errFallback.response && (errFallback.response.status === 404 || errFallback.response.status === 405)) {
          // Secondary endpoint alias: POST /api/rag/ask/
          response = await apiClient.post('/rag/ask/', {
            machine_id: machineId,
            question: question.trim()
          });
        } else {
          throw errFallback;
        }
      }

      const data = response.data;
      const isAbstained = Boolean(data.abstained || data.is_insufficient_evidence);

      return {
        id: data.query_id || data.id || ('q-' + Date.now()),
        machine_id: machineId,
        question: question.trim(),
        answer: data.answer || (isAbstained ? INSUFFICIENT_EVIDENCE_MESSAGE : ''),
        citations: Array.isArray(data.citations) ? data.citations : [],
        abstained: isAbstained,
        is_insufficient_evidence: isAbstained,
        created_at: data.created_at || new Date().toISOString()
      };
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[chatService] Backend offline, generating mock RAG response for demo');
        await new Promise((resolve) => setTimeout(resolve, 600));

        const qLower = question.toLowerCase();
        let answer = '';
        let isInsufficient = false;
        let citations = [];

        if (qLower.includes('warm') || qLower.includes('spindle') || qLower.includes('rpm')) {
          answer = `**High-Speed Warm-up Protocol:**\n\n1. Ensure axis interlocks are cleared and coolant chiller temperature is stabilized at **22°C - 25°C**.\n2. In MDI mode, command program **O9001**.\n3. Cycle through stage 1: **3,000 RPM for 10 minutes**.\n4. Ramp to stage 2: **6,000 RPM for 5 minutes**.\n5. Verify lubrication pressure indicator is steady in the green zone before commencing cutting operations.`;
          citations = [
            {
              id: 'c-mock-1',
              document_id: 101,
              document_title: 'Operations Manual',
              revision: 'Rev 2.4',
              page_number: 34,
              snippet: 'Section 4.2 Spindle Warm-up Cycle: Cold starts without executing O9001 warmup may cause ceramic bearing micro-fractures.',
              source_id: 'DOC-MOCK-P34-C0'
            }
          ];
        } else {
          isInsufficient = true;
          answer = INSUFFICIENT_EVIDENCE_MESSAGE;
          citations = [];
        }

        const newRecord = {
          id: 'mock-' + Date.now(),
          machine_id: machineId,
          machine_name: 'Selected Machine',
          engineer_name: 'Current Engineer',
          question,
          answer,
          abstained: isInsufficient,
          is_insufficient_evidence: isInsufficient,
          citations,
          created_at: new Date().toISOString()
        };

        mockChatState = [newRecord, ...mockChatState];
        return newRecord;
      }

      // Propagate real error message
      let errorMsg = 'Failed to submit question to technical assistant.';
      if (err.response?.data) {
        const d = err.response.data;
        errorMsg = d.detail || d.error || (typeof d === 'string' ? d : JSON.stringify(d));
      } else if (err.message) {
        errorMsg = err.message;
      }
      const customErr = new Error(errorMsg);
      customErr.response = err.response;
      customErr.code = err.code;
      throw customErr;
    }
  },

  /**
   * Fetch previous questions and answers for a specific machine or user
   * @param {number|string} machineId
   */
  async getChatHistory(machineId = null) {
    try {
      const params = machineId ? { machine_id: machineId } : {};
      const response = await apiClient.get('/history/', { params });
      const data = response.data;
      const rawList = Array.isArray(data) ? data : (data && Array.isArray(data.results) ? data.results : []);

      return rawList.map((item) => {
        const isAbstained = Boolean(item.abstained || item.is_insufficient_evidence);
        return {
          id: item.id,
          machine_id: item.machine_id || item.machine,
          machine_name: item.machine_name || '',
          machine_code: item.machine_code || '',
          question: item.question,
          answer: item.answer || (isAbstained ? INSUFFICIENT_EVIDENCE_MESSAGE : ''),
          citations: Array.isArray(item.citations) ? item.citations : [],
          abstained: isAbstained,
          is_insufficient_evidence: isAbstained,
          created_at: item.created_at
        };
      });
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        if (machineId) {
          return mockChatState.filter((item) => String(item.machine_id) === String(machineId));
        }
        return [...mockChatState];
      }
      throw err;
    }
  },

  /**
   * Fetch single question record by ID
   */
  async getChatRecordById(id) {
    try {
      const response = await apiClient.get(`/history/${id}/`);
      const item = response.data;
      const isAbstained = Boolean(item.abstained || item.is_insufficient_evidence);
      return {
        ...item,
        abstained: isAbstained,
        is_insufficient_evidence: isAbstained
      };
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const found = mockChatState.find((c) => String(c.id) === String(id));
        if (found) return found;
      }
      throw err;
    }
  }
};
