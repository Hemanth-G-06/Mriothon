import axios from 'axios';

// Centralized backend API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
export const USE_MOCK_FALLBACK = import.meta.env.VITE_USE_MOCK_FALLBACK !== 'false';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 15000
});

// Request interceptor to attach JWT access token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for automatic refresh / 401 handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    const isAuthEndpoint = originalRequest.url && (
      originalRequest.url.includes('/auth/login/') ||
      originalRequest.url.includes('/auth/refresh/') ||
      originalRequest.url.includes('/auth/logout/')
    );

    // Handle 401 Unauthorized (token expired) on protected endpoints
    if (error.response && error.response.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');

      if (refreshToken && !refreshToken.startsWith('mock-')) {
        try {
          const res = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
            refresh: refreshToken
          });
          if (res.data && res.data.access) {
            localStorage.setItem('access_token', res.data.access);
            apiClient.defaults.headers.common.Authorization = `Bearer ${res.data.access}`;
            originalRequest.headers.Authorization = `Bearer ${res.data.access}`;
            return apiClient(originalRequest);
          }
        } catch (refreshErr) {
          // Token refresh failed, clean up and redirect to login
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user_info');
          window.location.href = '/login?session_expired=true';
          return Promise.reject(refreshErr);
        }
      } else {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_info');
        window.location.href = '/login?session_expired=true';
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
