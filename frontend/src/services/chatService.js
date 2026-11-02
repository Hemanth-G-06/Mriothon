import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_CHAT_HISTORY } from './mockData';
import { INSUFFICIENT_EVIDENCE_MESSAGE } from '../utils/constants';

let mockChatState = [...INITIAL_MOCK_CHAT_HISTORY];
let mockConversations = [];

export const chatService = {
  /**
   * List all conversations belonging to the authenticated engineer
   * @param {string|number|null} machineId
   */
  async getConversations(machineId = null) {
    try {
      const params = machineId ? { machine_id: machineId } : {};
      const response = await apiClient.get('/chat/conversations/', { params });
      return Array.isArray(response.data) ? response.data : [];
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        if (machineId) {
          return mockConversations.filter((c) => String(c.machine_id) === String(machineId));
        }
        return [...mockConversations];
      }
      throw err;
    }
  },

  /**
   * Create a new persistent conversation session for an authorized machine
   * @param {string|number} machineId
   * @param {string} title
   */
  async createConversation(machineId, title = 'New Conversation') {
    try {
      const response = await apiClient.post('/chat/conversations/', {
        machine_id: machineId,
        title: title || 'New Conversation'
      });
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const newConv = {
          id: 'conv-' + Date.now(),
          title: title || 'New Conversation',
          machine_id: machineId,
          machine_name: 'Selected Machine',
          machine_code: 'MACH',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          messages: []
        };
        mockConversations.unshift(newConv);
        return newConv;
      }
      throw err;
    }
  },

  /**
   * Retrieve a conversation and all its chronological messages by ID
   * @param {string} conversationId
   */
  async getConversation(conversationId) {
    try {
      const response = await apiClient.get(`/chat/conversations/${conversationId}/`);
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const found = mockConversations.find((c) => String(c.id) === String(conversationId));
        if (found) return found;
      }
      throw err;
    }
  },

  /**
   * Post a new user message to a conversation and receive the grounded assistant response
   * @param {string} conversationId
   * @param {string} content
   */
  async sendMessage(conversationId, content) {
    try {
      const response = await apiClient.post(`/chat/conversations/${conversationId}/messages/`, {
        content: content.trim()
      });
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        await new Promise((resolve) => setTimeout(resolve, 600));
        const userMsg = {
          id: 'm-u-' + Date.now(),
          conversation_id: conversationId,
          role: 'USER',
          content: content.trim(),
          citations: [],
          created_at: new Date().toISOString()
        };
        const asstMsg = {
          id: 'm-a-' + Date.now(),
          conversation_id: conversationId,
          role: 'ASSISTANT',
          content: 'Normal operating parameters verified from operations manual: pressure must stay between 180 and 200 bar.',
          citations: [{ document_title: 'Operations Manual', page_number: 4, source_id: 'DOC-1' }],
          created_at: new Date().toISOString()
        };
        return {
          user_message: userMsg,
          assistant_message: asstMsg,
          answer: asstMsg.content,
          citations: asstMsg.citations
        };
      }

      // Propagate real error message
      let errorMsg = 'Failed to submit message to assistant.';
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
   * Update conversation title
   * @param {string} conversationId
   * @param {string} title
   */
  async updateConversationTitle(conversationId, title) {
    const response = await apiClient.patch(`/chat/conversations/${conversationId}/`, {
      title: title.trim()
    });
    return response.data;
  },

  /**
   * Delete conversation permanently
   * @param {string} conversationId
   */
  async deleteConversation(conversationId) {
    const response = await apiClient.delete(`/chat/conversations/${conversationId}/`);
    return response.data;
  },

  /**
   * Legacy flat askQuestion endpoint for backwards compatibility
   */
  async askQuestion(machineId, question) {
    try {
      let response;
      try {
        response = await apiClient.post('/rag/query/', {
          machine_id: machineId,
          question: question.trim()
        });
      } catch (errFallback) {
        if (errFallback.response && (errFallback.response.status === 404 || errFallback.response.status === 405)) {
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
   * Legacy query history endpoint
   */
  async getChatHistory(machineId = null) {
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
  }
};
