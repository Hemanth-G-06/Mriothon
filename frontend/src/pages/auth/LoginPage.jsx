import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { HardHat, Eye, EyeOff, LogIn, UserPlus, AlertCircle, CheckCircle2, Check, X } from 'lucide-react';
import { validateGmail, validatePassword } from '../../utils/validators';

export default function LoginPage() {
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'

  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Registration form state
  const [regData, setRegData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [showRegConfirmPassword, setShowRegConfirmPassword] = useState(false);
  const [regTouched, setRegTouched] = useState({
    firstName: false,
    lastName: false,
    email: false,
    password: false,
    confirmPassword: false
  });

  // Global feedback & loading
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Check if session expired query param was passed
  const queryParams = new URLSearchParams(location.search);
  const sessionExpired = queryParams.get('session_expired') === 'true';

  // Live password validation
  const passwordValidation = validatePassword(regData.password);

  // Inline validation calculations
  const getFieldErrors = () => {
    const errors = {};
    if (regTouched.firstName && !regData.firstName.trim()) {
      errors.firstName = 'First Name is required and must not be empty.';
    }
    if (regTouched.lastName && !regData.lastName.trim()) {
      errors.lastName = 'Last Name is required and must not be empty.';
    }
    if (regTouched.email) {
      const emailErr = validateGmail(regData.email);
      if (emailErr) errors.email = emailErr;
    }
    if (regTouched.password) {
      if (!regData.password) {
        errors.password = 'Password is required.';
      } else if (!passwordValidation.isValid) {
        errors.password = passwordValidation.errors[0];
      }
    }
    if (regTouched.confirmPassword) {
      if (!regData.confirmPassword) {
        errors.confirmPassword = 'Confirm Password is required.';
      } else if (regData.confirmPassword !== regData.password) {
        errors.confirmPassword = 'Passwords do not match.';
      }
    }
    return errors;
  };

  const fieldErrors = getFieldErrors();

  const handleRegChange = (e) => {
    const { name, value } = e.target;
    setRegData((prev) => ({ ...prev, [name]: value }));
  };

  const handleBlur = (field) => {
    setRegTouched((prev) => ({ ...prev, [field]: true }));
  };

  // Handle Login submission
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (!loginEmail.trim()) {
      setError('Please enter your Gmail address.');
      return;
    }
    if (!loginPassword) {
      setError('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await login(loginEmail.trim(), loginPassword);
      const userRole = res.user?.role?.toLowerCase();

      // Redirect user strictly according to their verified role
      if (userRole === 'admin') {
        navigate('/admin', { replace: true });
      } else if (userRole === 'supervisor') {
        navigate('/supervisor', { replace: true });
      } else if (userRole === 'engineer') {
        navigate('/engineer', { replace: true });
      } else {
        setError(
          `Unable to identify a valid operational role (${userRole || 'unassigned'}) for this account. Access denied.`
        );
        return;
      }
    } catch (err) {
      setError(err.message || 'Invalid credentials. Please verify your Gmail address and password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Registration submission
  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    // Mark all fields as touched
    setRegTouched({
      firstName: true,
      lastName: true,
      email: true,
      password: true,
      confirmPassword: true
    });

    // Validate First Name
    if (!regData.firstName.trim()) {
      setError('First Name is required.');
      return;
    }
    // Validate Last Name
    if (!regData.lastName.trim()) {
      setError('Last Name is required.');
      return;
    }
    // Validate Gmail Address
    const emailErr = validateGmail(regData.email);
    if (emailErr) {
      setError(emailErr);
      return;
    }
    // Validate Password
    if (!passwordValidation.isValid) {
      setError(passwordValidation.errors[0] || 'Password does not meet the security requirements.');
      return;
    }
    // Validate Confirm Password
    if (regData.confirmPassword !== regData.password) {
      setError('Confirm Password does not match the entered password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await register({
        first_name: regData.firstName,
        last_name: regData.lastName,
        email: regData.email,
        password: regData.password,
        password_confirm: regData.confirmPassword
      });

      // Clear sensitive registration state (never store plain password)
      const registeredEmail = regData.email.trim();
      setRegData({
        firstName: '',
        lastName: '',
        email: '',
        password: '',
        confirmPassword: ''
      });
      setRegTouched({
        firstName: false,
        lastName: false,
        email: false,
        password: false,
        confirmPassword: false
      });

      // Switch to Login tab with success message and pre-filled email
      setAuthMode('login');
      setLoginEmail(registeredEmail);
      setLoginPassword('');
      setSuccessMsg(result.message || 'Registration confirmed by backend! Please log in with your credentials.');
    } catch (err) {
      setError(err.message || 'Registration failed. Please check your information and try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Quick Demo Credentials preset helper for hackathon demonstration
  const fillQuickCredentials = (userType) => {
    setError('');
    setSuccessMsg('');
    setAuthMode('login');
    if (userType === 'admin') {
      setLoginEmail('sarah.connor@gmail.com');
      setLoginPassword('Admin@123');
    } else if (userType === 'engineer') {
      setLoginEmail('alex.vance@gmail.com');
      setLoginPassword('Engineer@123');
    } else if (userType === 'supervisor') {
      setLoginEmail('marcus.brody@gmail.com');
      setLoginPassword('Supervisor@123');
    }
  };

  return (
    <div className="card card-industrial border-0 shadow-sm">
      <div className="card-body p-4 p-sm-5">
        {/* Branding */}
        <div className="text-center mb-4">
          <div className="d-inline-flex p-3 rounded-3 bg-primary text-white mb-2 shadow-sm">
            <HardHat size={32} />
          </div>
          <h4 className="fw-bold text-dark mb-1">Manufacturing Manual Assistant</h4>
          <p className="text-muted small">RAG-Powered Technical Documentation Portal</p>
        </div>

        {/* Tab Selection: Existing User Login vs New User Registration */}
        <div className="d-flex p-1 bg-light rounded-3 mb-4 border">
          <button
            type="button"
            className={`btn btn-sm flex-grow-1 fw-semibold py-2 d-flex align-items-center justify-content-center gap-1 ${
              authMode === 'login' ? 'btn-white bg-white shadow-sm text-primary' : 'text-secondary'
            }`}
            onClick={() => {
              setAuthMode('login');
              setError('');
              setSuccessMsg('');
            }}
          >
            <LogIn size={15} />
            <span>Existing User Login</span>
          </button>
          <button
            type="button"
            className={`btn btn-sm flex-grow-1 fw-semibold py-2 d-flex align-items-center justify-content-center gap-1 ${
              authMode === 'register' ? 'btn-white bg-white shadow-sm text-primary' : 'text-secondary'
            }`}
            onClick={() => {
              setAuthMode('register');
              setError('');
              setSuccessMsg('');
            }}
          >
            <UserPlus size={15} />
            <span>New User Registration</span>
          </button>
        </div>

        {/* Session Expired Notice */}
        {sessionExpired && (
          <div className="alert alert-warning py-2 small d-flex align-items-center gap-2 mb-3">
            <AlertCircle size={16} />
            <span>Your session has expired. Please sign in again.</span>
          </div>
        )}

        {/* Success Alert */}
        {successMsg && (
          <div className="alert alert-success py-2 small d-flex align-items-center gap-2 mb-3">
            <CheckCircle2 size={16} className="text-success flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Global Error Alert */}
        {error && (
          <div className="alert alert-danger py-2 small d-flex align-items-center gap-2 mb-3">
            <AlertCircle size={16} className="text-danger flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* ======================= LOGIN FORM ======================= */}
        {authMode === 'login' ? (
          <form onSubmit={handleLoginSubmit}>
            <div className="mb-3">
              <label className="form-label small fw-semibold text-secondary">Gmail Address</label>
              <input
                type="email"
                className="form-control"
                placeholder="e.g. alex.vance@gmail.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                disabled={isSubmitting}
                autoComplete="email"
                required
              />
            </div>

            <div className="mb-4">
              <label className="form-label small fw-semibold text-secondary">Password</label>
              <div className="input-group">
                <input
                  type={showLoginPassword ? 'text' : 'password'}
                  className="form-control"
                  placeholder="Enter password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  disabled={isSubmitting}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => setShowLoginPassword(!showLoginPassword)}
                  title={showLoginPassword ? 'Hide password' : 'Show password'}
                >
                  {showLoginPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary-industrial w-100 py-2 d-flex align-items-center justify-content-center gap-2"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <LogIn size={18} />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>
        ) : (
          /* ======================= REGISTRATION FORM ======================= */
          <form onSubmit={handleRegisterSubmit}>
            <div className="row g-2 mb-3">
              <div className="col-6">
                <label className="form-label small fw-semibold text-secondary">First Name *</label>
                <input
                  type="text"
                  name="firstName"
                  className={`form-control ${fieldErrors.firstName ? 'is-invalid' : ''}`}
                  placeholder="e.g. John"
                  value={regData.firstName}
                  onChange={handleRegChange}
                  onBlur={() => handleBlur('firstName')}
                  disabled={isSubmitting}
                  required
                />
                {fieldErrors.firstName && (
                  <div className="invalid-feedback small" style={{ fontSize: '0.72rem' }}>
                    {fieldErrors.firstName}
                  </div>
                )}
              </div>
              <div className="col-6">
                <label className="form-label small fw-semibold text-secondary">Last Name *</label>
                <input
                  type="text"
                  name="lastName"
                  className={`form-control ${fieldErrors.lastName ? 'is-invalid' : ''}`}
                  placeholder="e.g. Smith"
                  value={regData.lastName}
                  onChange={handleRegChange}
                  onBlur={() => handleBlur('lastName')}
                  disabled={isSubmitting}
                  required
                />
                {fieldErrors.lastName && (
                  <div className="invalid-feedback small" style={{ fontSize: '0.72rem' }}>
                    {fieldErrors.lastName}
                  </div>
                )}
              </div>
            </div>

            {/* Gmail Address */}
            <div className="mb-3">
              <label className="form-label small fw-semibold text-secondary">Gmail Address *</label>
              <input
                type="email"
                name="email"
                className={`form-control ${fieldErrors.email ? 'is-invalid' : ''}`}
                placeholder="e.g. johnsmith@gmail.com"
                value={regData.email}
                onChange={handleRegChange}
                onBlur={() => handleBlur('email')}
                disabled={isSubmitting}
                required
              />
              {fieldErrors.email ? (
                <div className="invalid-feedback small" style={{ fontSize: '0.72rem' }}>
                  {fieldErrors.email}
                </div>
              ) : (
                <div className="text-muted small" style={{ fontSize: '0.72rem' }}>
                  Must end with <strong>@gmail.com</strong>
                </div>
              )}
            </div>

            {/* Password */}
            <div className="mb-2">
              <label className="form-label small fw-semibold text-secondary">Password *</label>
              <div className="input-group">
                <input
                  type={showRegPassword ? 'text' : 'password'}
                  name="password"
                  className={`form-control ${fieldErrors.password ? 'is-invalid' : ''}`}
                  placeholder="e.g. Manual@123"
                  value={regData.password}
                  onChange={handleRegChange}
                  onBlur={() => handleBlur('password')}
                  disabled={isSubmitting}
                  required
                />
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => setShowRegPassword(!showRegPassword)}
                  title={showRegPassword ? 'Hide password' : 'Show password'}
                >
                  {showRegPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {fieldErrors.password && (
                <div className="text-danger small mt-1" style={{ fontSize: '0.72rem' }}>
                  {fieldErrors.password}
                </div>
              )}
            </div>

            {/* Real-time Password Requirements Card */}
            <div className="p-2 mb-3 bg-light rounded border" style={{ fontSize: '0.72rem' }}>
              <div className="text-secondary fw-semibold mb-1">PASSWORD REQUIREMENTS:</div>
              <div className="row g-1">
                <div className="col-12 d-flex align-items-center gap-1">
                  {passwordValidation.checks.firstUpper ? (
                    <Check size={12} className="text-success fw-bold" />
                  ) : (
                    <span className="text-muted">•</span>
                  )}
                  <span className={passwordValidation.checks.firstUpper ? 'text-success fw-medium' : 'text-muted'}>
                    First character must be uppercase (A–Z)
                  </span>
                </div>
                <div className="col-12 d-flex align-items-center gap-1">
                  {passwordValidation.checks.minLength ? (
                    <Check size={12} className="text-success fw-bold" />
                  ) : (
                    <span className="text-muted">•</span>
                  )}
                  <span className={passwordValidation.checks.minLength ? 'text-success fw-medium' : 'text-muted'}>
                    At least 8 characters in length
                  </span>
                </div>
                <div className="col-12 d-flex align-items-center gap-1">
                  {passwordValidation.checks.hasLower ? (
                    <Check size={12} className="text-success fw-bold" />
                  ) : (
                    <span className="text-muted">•</span>
                  )}
                  <span className={passwordValidation.checks.hasLower ? 'text-success fw-medium' : 'text-muted'}>
                    At least one lowercase letter (a–z)
                  </span>
                </div>
                <div className="col-12 d-flex align-items-center gap-1">
                  {passwordValidation.checks.hasNumber ? (
                    <Check size={12} className="text-success fw-bold" />
                  ) : (
                    <span className="text-muted">•</span>
                  )}
                  <span className={passwordValidation.checks.hasNumber ? 'text-success fw-medium' : 'text-muted'}>
                    At least one number (0–9)
                  </span>
                </div>
                <div className="col-12 d-flex align-items-center gap-1">
                  {passwordValidation.checks.hasSpecial ? (
                    <Check size={12} className="text-success fw-bold" />
                  ) : (
                    <span className="text-muted">•</span>
                  )}
                  <span className={passwordValidation.checks.hasSpecial ? 'text-success fw-medium' : 'text-muted'}>
                    At least one special character (@, #, $, %, &, !, *)
                  </span>
                </div>
              </div>
            </div>

            {/* Confirm Password */}
            <div className="mb-4">
              <label className="form-label small fw-semibold text-secondary">Confirm Password *</label>
              <div className="input-group">
                <input
                  type={showRegConfirmPassword ? 'text' : 'password'}
                  name="confirmPassword"
                  className={`form-control ${fieldErrors.confirmPassword ? 'is-invalid' : ''}`}
                  placeholder="Re-enter password"
                  value={regData.confirmPassword}
                  onChange={handleRegChange}
                  onBlur={() => handleBlur('confirmPassword')}
                  disabled={isSubmitting}
                  required
                />
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => setShowRegConfirmPassword(!showRegConfirmPassword)}
                  title={showRegConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showRegConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {fieldErrors.confirmPassword ? (
                <div className="text-danger small mt-1" style={{ fontSize: '0.72rem' }}>
                  {fieldErrors.confirmPassword}
                </div>
              ) : regData.confirmPassword && regData.confirmPassword === regData.password ? (
                <div className="text-success small mt-1 d-flex align-items-center gap-1" style={{ fontSize: '0.72rem' }}>
                  <Check size={12} /> Passwords match
                </div>
              ) : null}
            </div>

            <button
              type="submit"
              className="btn btn-primary-industrial w-100 py-2 d-flex align-items-center justify-content-center gap-2"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                  <span>Registering Account...</span>
                </>
              ) : (
                <>
                  <UserPlus size={18} />
                  <span>Create Account</span>
                </>
              )}
            </button>
          </form>
        )}

        {/* Quick Demo Credentials Preset Bar */}
        <div className="mt-4 pt-3 border-top">
          <div className="d-flex align-items-center justify-content-between mb-2">
            <span className="text-muted small fw-semibold" style={{ fontSize: '0.72rem' }}>
              QUICK TEST CREDENTIALS:
            </span>
          </div>
          <div className="d-flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary flex-grow-1"
              style={{ fontSize: '0.75rem' }}
              onClick={() => fillQuickCredentials('admin')}
            >
              Admin
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary flex-grow-1"
              style={{ fontSize: '0.75rem' }}
              onClick={() => fillQuickCredentials('engineer')}
            >
              Engineer
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary flex-grow-1"
              style={{ fontSize: '0.75rem' }}
              onClick={() => fillQuickCredentials('supervisor')}
            >
              Supervisor
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
