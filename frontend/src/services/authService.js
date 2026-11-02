import apiClient, { USE_MOCK_FALLBACK } from './api';
import { MOCK_USERS } from './mockData';
import { normalizeUserRole } from '../utils/roleUtils';

// In-memory mock store for newly registered accounts in demo session
const mockRegisteredAccounts = [];

export const authService = {
  /**
   * Register a new user
   * @param {Object} data { first_name, last_name, email, password, password_confirm }
   */
  async register({ first_name, last_name, email, password, password_confirm }) {
    try {
      const response = await apiClient.post('/auth/register/', {
        first_name: first_name.trim(),
        last_name: last_name.trim(),
        email: email.trim().toLowerCase(),
        password: password,
        password_confirm: password_confirm
      });

      return {
        success: true,
        data: response.data,
        isMock: false,
        message: response.data?.message || 'Registration confirmed by backend. Please log in.'
      };
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';

      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[authService] Backend offline, validating registration in mock fallback');

        const cleanEmail = email.trim().toLowerCase();
        // Check for duplicates in initial mock users and registered accounts
        const existsInMockUsers = Object.values(MOCK_USERS).some(
          (u) => u.email?.toLowerCase() === cleanEmail
        );
        const existsInDynamic = mockRegisteredAccounts.some(
          (u) => u.email?.toLowerCase() === cleanEmail
        );

        if (existsInMockUsers || existsInDynamic) {
          throw new Error('A user with this Gmail address already exists.');
        }

        // Register new user in mock session (WITHOUT storing plain-text password)
        const newMockUser = {
          id: Date.now(),
          username: cleanEmail.split('@')[0],
          first_name: first_name.trim(),
          last_name: last_name.trim(),
          email: cleanEmail,
          full_name: `${first_name.trim()} ${last_name.trim()}`,
          role: 'engineer', // Default self-registered operator role
          access: `mock-access-token-${Date.now()}`,
          refresh: `mock-refresh-token-${Date.now()}`
        };
        mockRegisteredAccounts.push(newMockUser);

        return {
          success: true,
          data: newMockUser,
          isMock: true,
          message: 'Account successfully registered! Please sign in with your credentials.'
        };
      }

      // Parse Django REST Framework error response formats
      let message = 'Registration failed. Please verify your details.';
      if (err.response?.data) {
        const data = err.response.data;
        if (typeof data === 'string') {
          message = data;
        } else if (data.email) {
          message = Array.isArray(data.email) ? data.email[0] : data.email;
        } else if (data.password) {
          message = Array.isArray(data.password) ? data.password[0] : data.password;
        } else if (data.detail) {
          message = data.detail;
        } else if (data.non_field_errors) {
          message = Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : data.non_field_errors;
        } else if (data.message) {
          message = data.message;
        } else {
          const firstKey = Object.keys(data)[0];
          if (firstKey && data[firstKey]) {
            const val = data[firstKey];
            message = `${firstKey}: ${Array.isArray(val) ? val[0] : val}`;
          }
        }
      }
      throw new Error(message);
    }
  },

  /**
   * Log in user and resolve verified operational role
   * @param {string} emailOrUsername
   * @param {string} password
   */
  async login(emailOrUsername, password) {
    try {
      const cleanInput = (emailOrUsername || '').trim();
      const response = await apiClient.post('/auth/login/', {
        username: cleanInput,
        email: cleanInput,
        password: password
      });

      const data = response.data;
      const token = data.access || data.token;
      const refresh = data.refresh;

      if (token) localStorage.setItem('access_token', token);
      if (refresh) localStorage.setItem('refresh_token', refresh);
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;

      // Use user profile returned directly by verified login payload
      let user = data.user || data;

      // Explicitly extract and normalize the user's role
      const resolvedRole = normalizeUserRole(user, data);

      if (!resolvedRole) {
        throw new Error(
          'Authenticated account is missing a valid operational role (ADMIN, ENGINEER, or SUPERVISOR). Please contact your plant administrator.'
        );
      }

      user = {
        ...user,
        username: user.username || cleanInput,
        email: user.email || (cleanInput.includes('@') ? cleanInput : `${cleanInput}@gmail.com`),
        role: resolvedRole,
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        full_name: user.full_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || cleanInput
      };

      localStorage.setItem('user_info', JSON.stringify(user));

      return { success: true, user, isMock: false };
    } catch (err) {
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';

      if (USE_MOCK_FALLBACK && isNetworkError) {
        console.warn('[authService] Backend offline, evaluating mock credentials for dev/demo');
        const lowerInput = (emailOrUsername || '').trim().toLowerCase();

        // 1. Check newly registered accounts in demo session
        const dynamicUser = mockRegisteredAccounts.find(
          (u) => u.email.toLowerCase() === lowerInput || u.username.toLowerCase() === lowerInput
        );
        if (dynamicUser) {
          const finalRole = normalizeUserRole(dynamicUser) || dynamicUser.role;
          const finalUser = { ...dynamicUser, role: finalRole };
          localStorage.setItem('access_token', finalUser.access);
          localStorage.setItem('refresh_token', finalUser.refresh);
          localStorage.setItem('user_info', JSON.stringify(finalUser));
          return { success: true, user: finalUser, isMock: true };
        }

        // 2. Match exact predefined demo users by email, username, or role
        const matchedMockUser = Object.values(MOCK_USERS).find((u) => {
          const emailMatch = u.email && u.email.toLowerCase() === lowerInput;
          const usernameMatch = u.username && u.username.toLowerCase() === lowerInput;
          const roleMatch = u.role && u.role.toLowerCase() === lowerInput;
          const nameMatch = (
            (lowerInput.includes('sarah') || lowerInput.includes('connor')) && u.role === 'admin'
          ) || (
            (lowerInput.includes('marcus') || lowerInput.includes('brody')) && u.role === 'supervisor'
          ) || (
            (lowerInput.includes('alex') || lowerInput.includes('vance')) && u.role === 'engineer'
          );

          return emailMatch || usernameMatch || roleMatch || nameMatch;
        });

        if (matchedMockUser) {
          const normalizedRole = normalizeUserRole(matchedMockUser.role, matchedMockUser);
          const finalUser = {
            ...matchedMockUser,
            role: normalizedRole || matchedMockUser.role
          };
          localStorage.setItem('access_token', finalUser.access);
          localStorage.setItem('refresh_token', finalUser.refresh);
          localStorage.setItem('user_info', JSON.stringify(finalUser));
          return { success: true, user: finalUser, isMock: true };
        }

        throw new Error(
          'Invalid credentials. Account not found. Use the quick test credentials buttons for Admin, Engineer, or Supervisor.'
        );
      }

      // Backend returned real error
      const message =
        err.response?.data?.detail ||
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.message ||
        err.message ||
        'Invalid credentials. Please verify your Gmail address and password.';
      throw new Error(message);
    }
  },

  /**
   * Get current authenticated user profile
   */
  async getCurrentUser() {
    const token = localStorage.getItem('access_token');
    if (!token) {
      return null;
    }

    try {
      const response = await apiClient.get('/auth/me/');
      const rawUser = response.data?.user || response.data;
      if (rawUser) {
        const resolvedRole = normalizeUserRole(rawUser);
        const user = {
          ...rawUser,
          role: resolvedRole || rawUser.role || null
        };
        localStorage.setItem('user_info', JSON.stringify(user));
        return user;
      }
      return rawUser;
    } catch (err) {
      // If unauthorized (token expired or invalid), purge local credentials cleanly
      if (err.response && err.response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_info');
        delete apiClient.defaults.headers.common['Authorization'];
        return null;
      }

      // If network is offline, fall back to stored user for demo continuity
      const isNetworkError = !err.response || err.code === 'ERR_NETWORK';
      if (isNetworkError) {
        const stored = localStorage.getItem('user_info');
        if (stored) {
          try {
            const parsed = JSON.parse(stored);
            const resolvedRole = normalizeUserRole(parsed);
            return {
              ...parsed,
              role: resolvedRole || parsed.role || null
            };
          } catch {
            return null;
          }
        }
      }
      throw err;
    }
  },

  /**
   * Log out
   */
  async logout() {
    try {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh && !refresh.startsWith('mock-')) {
        await apiClient.post('/auth/logout/', { refresh });
      }
    } catch (err) {
      console.warn('Backend logout notification skipped or failed:', err.message);
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_info');
      delete apiClient.defaults.headers.common['Authorization'];
    }
  },

  /**
   * Check if user is currently authenticated
   */
  isAuthenticated() {
    return !!localStorage.getItem('access_token');
  },

  /**
   * Get stored user profile
   */
  getStoredUser() {
    const raw = localStorage.getItem('user_info');
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      const resolvedRole = normalizeUserRole(parsed);
      return {
        ...parsed,
        role: resolvedRole || parsed.role || null
      };
    } catch {
      return null;
    }
  }
};
