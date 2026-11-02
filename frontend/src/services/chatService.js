import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_CHAT_HISTORY } from './mockData';
import { INSUFFICIENT_EVIDENCE_MESSAGE } from '../utils/constants';

let mockChatState = [...INITIAL_MOCK_CHAT_HISTORY];

export const chatService = {
  /**
   * Ask question for a selected machine
   * @param {number|string} machineId
   * @param {string} question
   */
  async askQuestion(machineId, question) {
    try {
      let response;
      try {
        // Primary endpoint matching backend config/urls.py (api/rag/)
        response = await apiClient.post('/rag/ask/', {
          machine_id: machineId,
          question: question
        });
      } catch (err404) {
        if (err404.response && (err404.response.status === 404 || err404.response.status === 405)) {
          // Secondary endpoint alias
          response = await apiClient.post('/chat/ask/', {
            machine_id: machineId,
            question: question
          });
        } else {
          throw err404;
        }
      }
      return response.data;
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
          answer = `**HP-200 High-Speed Warm-up Protocol:**\n\n1. Ensure axis interlocks are cleared and coolant chiller temperature is stabilized at **22°C - 25°C**.\n2. In MDI mode, command program **O9001**.\n3. Cycle through stage 1: **3,000 RPM for 10 minutes**.\n4. Ramp to stage 2: **6,000 RPM for 5 minutes**.\n5. Verify lubrication pressure indicator is steady in the green zone before commencing cutting operations.`;
          citations = [
            {
              id: 'c-mock-1',
              document_id: 101,
              document_title: 'HP-200 Operations Manual',
              revision: 'Rev 2.4',
              page_number: 34,
              snippet: 'Section 4.2 Spindle Warm-up Cycle: Cold starts without executing O9001 warmup may cause ceramic bearing micro-fractures.',
              pdf_url: null
            },
            {
              id: 'c-mock-2',
              document_id: 102,
              document_title: 'HP-200 Maintenance Manual',
              revision: 'Rev 1.8',
              page_number: 89,
              snippet: 'Cooling lubrication reservoir operating range: 22°C - 25°C under continuous duty.',
              pdf_url: null
            }
          ];
        } else if (qLower.includes('pressure') || qLower.includes('shutoff') || qLower.includes('emergency') || qLower.includes('leak')) {
          answer = `**AC-90 Compressor Pressure Protection:**\n\nThe dual-stage differential sensor automatically triggers an emergency interlock cutoff at **14.5 bar (210 PSI)**.\n\n- If discharge pressure exceeds **15.0 bar**, the mechanical pop-off safety valve releases immediately.\n- If differential oil pressure drops below **1.2 bar** for > 15 seconds, system logs fault **E-302** and powers down compressor drive coils.`;
          citations = [
            {
              id: 'c-mock-3',
              document_id: 103,
              document_title: 'AC-90 Operations and Maintenance Manual',
              revision: 'Rev 3.1',
              page_number: 48,
              snippet: 'Automatic Interlock Shutoff: Dual-stage pressure sensor calibrated for 14.5 bar hard-trip limit.',
              pdf_url: null
            }
          ];
        } else {
          isInsufficient = true;
          answer = INSUFFICIENT_EVIDENCE_MESSAGE;
          citations = [];
        }

        const newRecord = {
          id: Date.now(),
          machine_id: Number(machineId),
          machine_name: 'Selected Machine',
          engineer_name: 'Current Engineer',
          question,
          answer,
          is_insufficient_evidence: isInsufficient,
          citations,
          created_at: new Date().toISOString()
        };

        mockChatState = [newRecord, ...mockChatState];
        return newRecord;
      }
      throw err;
    }
  },

  /**
   * Fetch previous questions and answers for a specific machine or all
   * @param {number|string} machineId
   */
  async getChatHistory(machineId = null) {
    try {
      const params = machineId ? { machine_id: machineId } : {};
      let response;
      try {
        // Backend config/urls.py maps api/history/
        response = await apiClient.get('/history/', { params });
      } catch (err404) {
        if (err404.response && (err404.response.status === 404 || err404.response.status === 405)) {
          response = await apiClient.get('/chat/history/', { params });
        } else {
          throw err404;
        }
      }
      const data = response.data;
      if (Array.isArray(data)) return data;
      if (data && Array.isArray(data.results)) return data.results;
      return [];
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
      let response;
      try {
        response = await apiClient.get(`/history/${id}/`);
      } catch (err404) {
        if (err404.response && (err404.response.status === 404 || err404.response.status === 405)) {
          response = await apiClient.get(`/chat/history/${id}/`);
        } else {
          throw err404;
        }
      }
      return response.data;
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
