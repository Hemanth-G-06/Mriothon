/**
 * Centralized API and Network Error Handler
 * Formats errors into clear, actionable, user-friendly messages
 * without exposing stack traces or sensitive backend details.
 */

export function getErrorMessage(error, defaultMessage = 'An unexpected error occurred. Please try again.') {
  if (!error) return defaultMessage;

  // 1. Connection / Timeout / Network errors (no response received from server)
  if (!error.response) {
    if (
      error.code === 'ECONNABORTED' ||
      error.message?.toLowerCase().includes('timeout') ||
      error.message?.toLowerCase().includes('timed out')
    ) {
      return 'The request timed out while waiting for the assistant service. Please wait a moment and try again.';
    }
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
    if (error.message && !error.message.toLowerCase().includes('status code')) {
      return error.message;
    }
    return 'Unable to connect to the server. Please check your connection and try again.';
  }

  const status = error.response.status;
  const data = error.response.data;

  // 2. Unauthorized (401)
  if (status === 401) {
    return 'Your session has expired. Please log in again.';
  }

  // 3. Extract explicit, sanitized backend error messages first (including 400, 403, 404, 429, 503)
  if (data && typeof data === 'object') {
    if (data.detail && typeof data.detail === 'string') return data.detail;
    if (data.message && typeof data.message === 'string') return data.message;
    if (data.error && typeof data.error === 'string') return data.error;

    // Field-specific DRF validation errors (e.g. data.file, data.title, data.non_field_errors)
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
  } else if (typeof data === 'string' && data.trim().length > 0 && !data.trim().startsWith('<')) {
    return data.trim();
  }

  // 4. Forbidden (403) fallback
  if (status === 403) {
    return 'Access denied. You do not have permission to perform this action.';
  }

  // 5. Rate Limited / Service Unavailable (429 / 503) fallback
  if (status === 429 || status === 503) {
    return 'The AI assistant service is temporarily rate-limited or unavailable. Please wait a moment and try again.';
  }

  // 6. Server error (500+) fallback
  if (status >= 500) {
    return 'The server encountered an error processing your request. Please try again later.';
  }

  return defaultMessage;
}
