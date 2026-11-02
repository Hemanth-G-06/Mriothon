import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_CHAT_HISTORY } from './mockData';

let mockSupervisorRecords = [...INITIAL_MOCK_CHAT_HISTORY];

export const supervisorService = {
  /**
   * Fetch supervisor question history with filters
   * @param {Object} filters { machine, engineer, date, status, search, page }
   */
  async getHistory(filters = {}) {
    try {
      const response = await apiClient.get('/supervisor/history/', { params: filters });
      const data = response.data;
      if (Array.isArray(data)) return { results: data, total: data.length };
      if (data && Array.isArray(data.results)) return data;
      return { results: [], total: 0 };
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[supervisorService] Backend offline, using mock supervisor history');
        let records = [...mockSupervisorRecords];

        if (filters.machine) {
          records = records.filter(
            (r) => String(r.machine_id) === String(filters.machine) || r.machine_name?.toLowerCase().includes(filters.machine.toLowerCase())
          );
        }

        if (filters.engineer) {
          records = records.filter((r) =>
            r.engineer_name?.toLowerCase().includes(filters.engineer.toLowerCase())
          );
        }

        if (filters.date) {
          records = records.filter((r) => r.created_at?.startsWith(filters.date));
        }

        if (filters.status) {
          if (filters.status === 'answered') {
            records = records.filter((r) => !r.is_insufficient_evidence);
          } else if (filters.status === 'insufficient_evidence') {
            records = records.filter((r) => r.is_insufficient_evidence);
          }
        }

        if (filters.search) {
          const q = filters.search.toLowerCase();
          records = records.filter(
            (r) =>
              r.question?.toLowerCase().includes(q) ||
              r.answer?.toLowerCase().includes(q) ||
              r.machine_name?.toLowerCase().includes(q)
          );
        }

        return {
          results: records,
          total: records.length
        };
      }
      throw err;
    }
  },

  /**
   * Fetch details for a specific question record
   */
  async getHistoryDetail(id) {
    try {
      const response = await apiClient.get(`/supervisor/history/${id}/`);
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const found = mockSupervisorRecords.find((r) => String(r.id) === String(id));
        if (found) return found;
      }
      throw err;
    }
  },

  /**
   * Get supervisor summary statistics
   */
  async getStatistics() {
    try {
      const response = await apiClient.get('/supervisor/statistics/');
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const total = mockSupervisorRecords.length;
        const insufficient = mockSupervisorRecords.filter((r) => r.is_insufficient_evidence).length;
        const answered = total - insufficient;

        return {
          total_questions: total,
          answered_questions: answered,
          insufficient_evidence_questions: insufficient,
          active_machines_monitored: 3
        };
      }
      throw err;
    }
  }
};
