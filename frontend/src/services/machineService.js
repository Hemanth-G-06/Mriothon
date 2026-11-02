import apiClient, { USE_MOCK_FALLBACK } from './api';
import { INITIAL_MOCK_MACHINES } from './mockData';

let mockMachinesState = [...INITIAL_MOCK_MACHINES];

export const machineService = {
  /**
   * Fetch all registered machines
   */
  async getMachines() {
    try {
      const response = await apiClient.get('/machines/');
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
      // Ensure machine_code is present and uppercase
      const code = (
        machineData.machine_code ||
        machineData.serial_number ||
        machineData.name.replace(/[^a-zA-Z0-9]/g, '-').toUpperCase().slice(0, 20)
      ).trim().toUpperCase();

      const payload = {
        name: machineData.name.trim(),
        machine_code: code,
        model_number: (machineData.model_number || '').trim(),
        manufacturer: (machineData.manufacturer || '').trim(),
        location: (machineData.location || '').trim(),
        description: (machineData.description || '').trim(),
        status: machineData.status || 'ACTIVE'
      };

      const response = await apiClient.post('/machines/', payload);
      return response.data;
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[machineService] Backend offline, creating mock machine');
        const newMachine = {
          id: 'mock-' + Date.now(),
          name: machineData.name,
          machine_code: (machineData.machine_code || machineData.serial_number || 'MACH-01').toUpperCase(),
          model_number: machineData.model_number || 'N/A',
          serial_number: machineData.serial_number || 'SN-' + Math.floor(1000 + Math.random() * 9000),
          description: machineData.description || '',
          location: machineData.location || 'Main Floor',
          status: 'ACTIVE',
          created_at: new Date().toISOString()
        };
        mockMachinesState = [newMachine, ...mockMachinesState];
        return newMachine;
      }
      throw err;
    }
  },

  /**
   * Fetch engineer assignments for a specific machine
   * @param {string} machineId
   */
  async getAssignments(machineId) {
    const response = await apiClient.get(`/machines/${machineId}/assignments/`);
    const data = response.data;
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
  },

  /**
   * Assign an engineer to a machine
   * @param {string} machineId
   * @param {number|string} userId
   */
  async assignEngineer(machineId, userId) {
    const response = await apiClient.post(`/machines/${machineId}/assignments/`, {
      user_id: Number(userId)
    });
    return response.data;
  },

  /**
   * Revoke an engineer assignment from a machine
   * @param {string} machineId
   * @param {number|string} assignmentId
   */
  async unassignEngineer(machineId, assignmentId) {
    const response = await apiClient.delete(`/machines/${machineId}/assignments/${assignmentId}/`);
    return response.data;
  },

  /**
   * Delete a machine asset, associated documents, and ChromaDB vector index
   * @param {string} machineId
   * @param {boolean} permanent
   */
  async deleteMachine(machineId, permanent = true) {
    const response = await apiClient.delete(`/machines/${machineId}/`, {
      params: permanent ? { permanent: 'true' } : {}
    });
    return response.data;
  },

  /**
   * Fetch documents associated with a specific machine
   * @param {string} machineId
   */
  async getMachineDocuments(machineId) {
    const response = await apiClient.get(`/machines/${machineId}/documents/`);
    const data = response.data;
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
  }
};
