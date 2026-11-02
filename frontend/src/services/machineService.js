import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_MACHINES } from './mockData';

// In-memory mock store for session state if mock fallback is active
let mockMachinesState = [...INITIAL_MOCK_MACHINES];

export const machineService = {
  /**
   * Fetch all registered machines
   */
  async getMachines() {
    try {
      const response = await apiClient.get('/machines/');
      // Handle Django paginated or raw list response
      const data = response.data;
      if (Array.isArray(data)) return data;
      if (data && Array.isArray(data.results)) return data.results;
      return [];
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[machineService] Backend offline, using mock machines');
        return [...mockMachinesState];
      }
      throw err;
    }
  },

  /**
   * Fetch single machine details
   * @param {string|number} machineId
   */
  async getMachineById(machineId) {
    try {
      const response = await apiClient.get(`/machines/${machineId}/`);
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        const found = mockMachinesState.find((m) => String(m.id) === String(machineId));
        if (found) return found;
      }
      throw err;
    }
  },

  /**
   * Register a new machine
   * @param {Object} machineData
   */
  async createMachine(machineData) {
    try {
      const response = await apiClient.post('/machines/', machineData);
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[machineService] Backend offline, creating mock machine');
        const newMachine = {
          id: Date.now(),
          name: machineData.name,
          model_number: machineData.model_number || 'N/A',
          serial_number: machineData.serial_number || 'SN-' + Math.floor(1000 + Math.random() * 9000),
          description: machineData.description || '',
          location: machineData.location || 'Main Floor',
          manuals_count: 0,
          created_at: new Date().toISOString()
        };
        mockMachinesState = [newMachine, ...mockMachinesState];
        return newMachine;
      }
      throw err;
    }
  }
};
