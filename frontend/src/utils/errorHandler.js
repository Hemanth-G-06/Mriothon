/**
 * Centralized API and Network Error Handler
 * Formats errors into clear, actionable, user-friendly messages
 * without exposing stack traces or sensitive backend details.
 */

export function getErrorMessage(error, defaultMessage = 'An unexpected error occurred. Please try again.') {
  if (!error) return defaultMessage;

  // 1. Connection / Network errors (no response received from server)
  if (!error.response) {
    if (error.code === 'ERR_NETWORK' || error.message?.toLowerCase().includes('network error')) {
      return 'Network error. Please check your internet or local server connection.';
    }
    if (
      error.code === 'ECONNREFUSED' ||
      error.code === 'ERR_CONNECTION_REFUSED' ||
      error.message?.toLowerCase().includes('connection refused')
    ) {
      return 'Unable to connect to the server. Please check your connection and try again.';
    }
    return 'Unable to connect to the server. Please check your connection and try again.';
  }

  const status = error.response.status;

  // 2. Forbidden (403)
  if (status === 403) {
    return 'Access denied. You do not have permission to perform this action.';
  }

  // 3. Unauthorized (401)
  if (status === 401) {
    return 'Your session has expired. Please log in again.';
  }

  // 4. Server error (500)
  if (status >= 500) {
    return 'The server encountered an error processing your request. Please try again later.';
  }

  // 5. Backend response data error message extraction (400, 422, etc.)
  const data = error.response.data;
  if (data) {
    if (typeof data === 'string') return data;
    if (data.detail && typeof data.detail === 'string') return data.detail;
    if (data.message && typeof data.message === 'string') return data.message;
    if (data.error && typeof data.error === 'string') return data.error;

    // Field-specific DRF errors (e.g. data.file, data.title, data.non_field_errors)
    const firstKey = Object.keys(data)[0];
    if (firstKey) {
      const val = data[firstKey];
      if (Array.isArray(val) && val.length > 0) {
        return `${firstKey}: ${val[0]}`;
      }
      if (typeof val === 'string') {
        return `${firstKey}: ${val}`;
      }
    }
  }

  return defaultMessage;
}
