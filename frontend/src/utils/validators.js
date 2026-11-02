/**
 * Validate Gmail address
 * Must be non-empty and end with @gmail.com
 */
export function validateGmail(email) {
  if (!email || !email.trim()) {
    return 'Gmail address is required.';
  }
  const trimmed = email.trim();
  // Valid characters before @gmail.com, case-insensitive
  const gmailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/i;
  if (!gmailRegex.test(trimmed)) {
    return 'Please enter a valid Gmail address ending with @gmail.com.';
  }
  return '';
}

/**
 * Validate Password according to strict security criteria:
 * - Must contain at least 8 characters.
 * - The first character must be an uppercase English letter (A–Z).
 * - Must contain at least one lowercase English letter (a–z).
 * - Must contain at least one number (0–9).
 * - Must contain at least one special character, such as @, #, $, %, &, !, or *.
 */
export function validatePassword(password) {
  if (!password) {
    return {
      isValid: false,
      errors: ['Password is required.'],
      checks: {
        firstUpper: false,
        minLength: false,
        hasLower: false,
        hasNumber: false,
        hasSpecial: false
      }
    };
  }

  const checks = {
    firstUpper: /^[A-Z]/.test(password),
    minLength: password.length >= 8,
    hasLower: /[a-z]/.test(password),
    hasNumber: /\d/.test(password),
    hasSpecial: /[@#$%&!*^()_\-+=[\]{}|;:'",.<>/?\\~`]/.test(password)
  };

  const errors = [];
  if (!checks.firstUpper) {
    errors.push('The first character must be an uppercase English letter (A–Z).');
  }
  if (!checks.minLength) {
    errors.push('Must contain at least 8 characters.');
  }
  if (!checks.hasLower) {
    errors.push('Must contain at least one lowercase English letter.');
  }
  if (!checks.hasNumber) {
    errors.push('Must contain at least one number.');
  }
  if (!checks.hasSpecial) {
    errors.push('Must contain at least one special character (e.g. @, #, $, %, &, !, *).');
  }

  return {
    isValid: errors.length === 0,
    errors,
    checks
  };
}
