import React, { useState, useEffect } from 'react';
import { Users, UserPlus, Search, CheckCircle2, AlertCircle, Shield, Wrench, Eye } from 'lucide-react';
import { userService } from '../../services/userService';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  // Create User Form State
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'ENGINEER'
  });

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const list = await userService.getUsers();
      setUsers(Array.isArray(list) ? list : []);
    } catch (err) {
      setFeedback({ type: 'danger', message: getErrorMessage(err, 'Failed to fetch users from server.') });
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleOpenModal = () => {
    setFormData({
      email: '',
      password: '',
      first_name: '',
      last_name: '',
      role: 'ENGINEER'
    });
    setShowModal(true);
    setFeedback({ type: '', message: '' });
  };

  const handleCloseModal = () => {
    if (!isSubmitting) setShowModal(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email.trim() || !formData.password) {
      setFeedback({ type: 'danger', message: 'Email and password are required.' });
      return;
    }

    setIsSubmitting(true);
    setFeedback({ type: '', message: '' });

    try {
      await userService.createUser(formData);
      setFeedback({ type: 'success', message: `User "${formData.email}" successfully provisioned!` });
      setShowModal(false);
      await fetchUsers();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to provision user.')
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (user) => {
    try {
      if (user.is_active) {
        await userService.deactivateUser(user.id);
        setFeedback({ type: 'success', message: `User ${user.email} deactivated.` });
      } else {
        await userService.updateUser(user.id, { is_active: true });
        setFeedback({ type: 'success', message: `User ${user.email} reactivated.` });
      }
      await fetchUsers();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to update user account status.')
      });
    }
  };

  const filteredUsers = (users || []).filter(
    (u) =>
      u.email?.toLowerCase().includes(search.toLowerCase()) ||
      u.first_name?.toLowerCase().includes(search.toLowerCase()) ||
      u.last_name?.toLowerCase().includes(search.toLowerCase()) ||
      u.role?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="container-fluid p-0">
      {/* Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h4 className="fw-bold text-dark mb-1">User & Role Management</h4>
          <p className="text-muted small mb-0">
            Provision and manage field engineers, supervisors, and plant administrators.
          </p>
        </div>
        <button
          onClick={handleOpenModal}
          className="btn btn-primary-industrial btn-sm d-flex align-items-center gap-1 align-self-start align-self-md-auto"
        >
          <UserPlus size={16} /> Provision User
        </button>
      </div>

      {/* Global alert feedback */}
      {feedback.message && (
        <div
          className={`alert alert-${feedback.type} alert-dismissible fade show py-2 small d-flex align-items-center justify-content-between mb-4`}
          role="alert"
        >
          <div className="d-flex align-items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{feedback.message}</span>
          </div>
          <button
            type="button"
            className="btn-close"
            style={{ padding: '0.6rem' }}
            onClick={() => setFeedback({ type: '', message: '' })}
          />
        </div>
      )}

      {/* Filter / Search Bar */}
      <div className="card card-industrial p-3 mb-4 bg-white">
        <div className="row g-2 align-items-center">
          <div className="col-12 col-md-6">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={15} className="text-muted" />
              </span>
              <input
                type="text"
                className="form-control form-control-sm border-start-0"
                placeholder="Search by name, email, or role..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="col-12 col-md-6 text-md-end text-muted small">
            Total Users: <strong>{users.length}</strong> | Filtered: <strong>{filteredUsers.length}</strong>
          </div>
        </div>
      </div>

      {/* Users Table */}
      {loading ? (
        <LoadingSpinner text="Loading users from PostgreSQL..." size="lg" />
      ) : filteredUsers.length === 0 ? (
        <EmptyState
          title="No Users Found"
          description={search ? `No accounts match "${search}".` : "No application users found. Provision your first engineer or supervisor."}
          icon={Users}
        />
      ) : (
        <div className="card card-industrial bg-white shadow-sm overflow-hidden mb-4">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0" style={{ fontSize: '0.88rem' }}>
              <thead className="table-light text-secondary text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '0.04em' }}>
                <tr>
                  <th className="ps-3">User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th className="text-end pe-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => {
                  const roleUpper = (u.role || '').toUpperCase();
                  const roleBadgeClass =
                    roleUpper === 'ADMIN'
                      ? 'bg-danger bg-opacity-10 text-danger border-danger border'
                      : roleUpper === 'SUPERVISOR'
                      ? 'bg-warning bg-opacity-10 text-dark border-warning border'
                      : 'bg-primary bg-opacity-10 text-primary border-primary border';

                  return (
                    <tr key={u.id}>
                      <td className="ps-3">
                        <div className="fw-semibold text-dark">
                          {u.first_name || u.last_name ? `${u.first_name} ${u.last_name}`.trim() : u.email}
                        </div>
                        <div className="text-muted small font-monospace" style={{ fontSize: '0.78rem' }}>
                          {u.email}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${roleBadgeClass} small px-2 py-1`}>
                          {roleUpper || 'ENGINEER'}
                        </span>
                      </td>
                      <td>
                        {u.is_active ? (
                          <span className="badge bg-success bg-opacity-10 text-success border border-success small">
                            Active
                          </span>
                        ) : (
                          <span className="badge bg-secondary bg-opacity-10 text-secondary border small">
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="text-muted small">
                        {u.date_joined ? formatDateTime(u.date_joined) : '—'}
                      </td>
                      <td className="text-end pe-3">
                        <button
                          className={`btn btn-sm ${u.is_active ? 'btn-outline-danger' : 'btn-outline-success'} py-0 px-2`}
                          style={{ fontSize: '0.75rem' }}
                          onClick={() => handleToggleActive(u)}
                        >
                          {u.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Provision User Modal */}
      {showModal && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0 shadow">
              <div className="modal-header">
                <h5 className="modal-title fw-bold">Provision New User</h5>
                <button type="button" className="btn-close" onClick={handleCloseModal} disabled={isSubmitting} />
              </div>
              <form onSubmit={handleSubmit}>
                <div className="modal-body p-4">
                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Email Address *</label>
                    <input
                      type="email"
                      name="email"
                      className="form-control form-control-sm"
                      placeholder="e.g. engineer.alex@plant.local"
                      value={formData.email}
                      onChange={handleInputChange}
                      required
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Password *</label>
                    <input
                      type="password"
                      name="password"
                      className="form-control form-control-sm"
                      placeholder="At least 8 characters"
                      value={formData.password}
                      onChange={handleInputChange}
                      required
                      minLength={8}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="row g-2 mb-3">
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">First Name</label>
                      <input
                        type="text"
                        name="first_name"
                        className="form-control form-control-sm"
                        placeholder="e.g. Alex"
                        value={formData.first_name}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">Last Name</label>
                      <input
                        type="text"
                        name="last_name"
                        className="form-control form-control-sm"
                        placeholder="e.g. Vance"
                        value={formData.last_name}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  <div className="mb-0">
                    <label className="form-label small fw-semibold text-secondary">Operational Role *</label>
                    <select
                      name="role"
                      className="form-select form-select-sm"
                      value={formData.role}
                      onChange={handleInputChange}
                      disabled={isSubmitting}
                    >
                      <option value="ENGINEER">Engineer (Query assigned machines & manuals)</option>
                      <option value="SUPERVISOR">Supervisor (Read-only monitoring & query audit)</option>
                      <option value="ADMIN">Administrator (Machines, users, and document upload)</option>
                    </select>
                  </div>
                </div>

                <div className="modal-footer bg-light py-2 px-4">
                  <button type="button" className="btn btn-sm btn-outline-secondary" onClick={handleCloseModal} disabled={isSubmitting}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-sm btn-primary-industrial d-flex align-items-center gap-1" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                        <span>Provisioning...</span>
                      </>
                    ) : (
                      <>
                        <UserPlus size={15} /> Save User
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
