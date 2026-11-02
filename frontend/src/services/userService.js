import apiClient from './api';

export const userService = {
  /**
   * Fetch all system users (Administrator only)
   */
  async getUsers() {
    const response = await apiClient.get('/users/');
    const data = response.data;
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
  },

  /**
   * Fetch single user details
   * @param {number|string} id
   */
  async getUserById(id) {
    const response = await apiClient.get(`/users/${id}/`);
    return response.data;
  },

  /**
   * Create a new user with operational role (ADMIN, ENGINEER, SUPERVISOR)
   * @param {Object} userData { email, password, first_name, last_name, role }
   */
  async createUser(userData) {
    const payload = {
      email: userData.email.trim().toLowerCase(),
      password: userData.password,
      first_name: (userData.first_name || '').trim(),
      last_name: (userData.last_name || '').trim(),
      role: (userData.role || 'ENGINEER').toUpperCase()
    };
    const response = await apiClient.post('/users/', payload);
    return response.data;
  },

  /**
   * Update permitted user fields
   * @param {number|string} id
   * @param {Object} userData
   */
  async updateUser(id, userData) {
    const payload = {};
    if (userData.first_name !== undefined) payload.first_name = userData.first_name.trim();
    if (userData.last_name !== undefined) payload.last_name = userData.last_name.trim();
    if (userData.role !== undefined) payload.role = userData.role.toUpperCase();
    if (userData.is_active !== undefined) payload.is_active = Boolean(userData.is_active);

    const response = await apiClient.patch(`/users/${id}/`, payload);
    return response.data;
  },

  /**
   * Soft-deactivate a user account (preserves audit records; protected against last-admin deactivation)
   * @param {number|string} id
   */
  async deactivateUser(id) {
    const response = await apiClient.delete(`/users/${id}/`);
    return response.data;
  }
};
