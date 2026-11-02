import React, { useState, useEffect } from 'react';
import { Cpu, Plus, Search, CheckCircle2, AlertCircle, MapPin, Hash, FileText, UserCheck, UserX, UserPlus, Users, Trash2, AlertTriangle } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { machineService } from '../../services/machineService';
import { userService } from '../../services/userService';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import { formatDateTime } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

export default function MachinesPage() {
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  // Assignment Modal State
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedMachineForAssign, setSelectedMachineForAssign] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [allEngineers, setAllEngineers] = useState([]);
  const [selectedEngineerId, setSelectedEngineerId] = useState('');
  const [loadingAssignments, setLoadingAssignments] = useState(false);

  // Delete Modal State
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [machineToDelete, setMachineToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteDetails, setDeleteDetails] = useState({ manualsCount: 0, assignmentsCount: 0, loading: false });

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    machine_code: '',
    model_number: '',
    manufacturer: '',
    location: '',
    description: ''
  });

  const fetchMachines = async () => {
    setLoading(true);
    try {
      const list = await machineService.getMachines();
      setMachines(Array.isArray(list) ? list : []);
    } catch (err) {
      setFeedback({ type: 'danger', message: getErrorMessage(err, 'Failed to fetch registered machines from server.') });
      setMachines([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMachines();
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleOpenModal = () => {
    setFormData({
      name: '',
      machine_code: '',
      model_number: '',
      manufacturer: '',
      location: '',
      description: ''
    });
    setShowModal(true);
    setFeedback({ type: '', message: '' });
  };

  const handleCloseModal = () => {
    if (!isSubmitting) setShowModal(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setFeedback({ type: 'danger', message: 'Machine Name is required.' });
      return;
    }

    setIsSubmitting(true);
    setFeedback({ type: '', message: '' });

    try {
      await machineService.createMachine(formData);
      setFeedback({ type: 'success', message: `Machine "${formData.name}" successfully registered!` });
      setShowModal(false);
      await fetchMachines();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Error creating machine record.')
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenDeleteModal = async (machine) => {
    setMachineToDelete(machine);
    setDeleteDetails({ manualsCount: 0, assignmentsCount: 0, loading: true });
    setShowDeleteModal(true);
    try {
      const [docs, asgns] = await Promise.allSettled([
        documentService.getDocuments(machine.id),
        machineService.getAssignments(machine.id)
      ]);
      const manualsCount = docs.status === 'fulfilled' && Array.isArray(docs.value) ? docs.value.length : 0;
      const assignmentsCount = asgns.status === 'fulfilled' && Array.isArray(asgns.value) ? asgns.value.length : 0;
      setDeleteDetails({ manualsCount, assignmentsCount, loading: false });
    } catch {
      setDeleteDetails({ manualsCount: 0, assignmentsCount: 0, loading: false });
    }
  };

  const handleConfirmDelete = async () => {
    if (!machineToDelete) return;
    setIsDeleting(true);
    try {
      await machineService.deleteMachine(machineToDelete.id, true);
      setFeedback({
        type: 'success',
        message: `Machine "${machineToDelete.name}" (${machineToDelete.machine_code}) and its dependent manuals/vector chunks were successfully deleted.`
      });
      setShowDeleteModal(false);
      setMachineToDelete(null);
      await fetchMachines();
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to delete machine asset. Please try again.')
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleOpenAssignModal = async (machine) => {

    setSelectedMachineForAssign(machine);
    setShowAssignModal(true);
    setLoadingAssignments(true);
    setSelectedEngineerId('');
    try {
      const [assigns, users] = await Promise.all([
        machineService.getAssignments(machine.id),
        userService.getUsers()
      ]);
      setAssignments(Array.isArray(assigns) ? assigns : []);
      // Filter for active engineers
      const engineers = (Array.isArray(users) ? users : []).filter(
        (u) => (u.role || '').toUpperCase() === 'ENGINEER' && u.is_active
      );
      setAllEngineers(engineers);
      if (engineers.length > 0) {
        setSelectedEngineerId(String(engineers[0].id));
      }
    } catch (err) {
      console.error('Failed to load assignments or engineers:', err);
    } finally {
      setLoadingAssignments(false);
    }
  };

  const handleAssignEngineer = async (e) => {
    e.preventDefault();
    if (!selectedEngineerId || !selectedMachineForAssign) return;

    try {
      await machineService.assignEngineer(selectedMachineForAssign.id, selectedEngineerId);
      setFeedback({ type: 'success', message: 'Engineer successfully assigned to machine.' });
      // Refresh assignments
      const updated = await machineService.getAssignments(selectedMachineForAssign.id);
      setAssignments(Array.isArray(updated) ? updated : []);
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to assign engineer.')
      });
    }
  };

  const handleUnassignEngineer = async (assignmentId) => {
    if (!selectedMachineForAssign) return;
    try {
      await machineService.unassignEngineer(selectedMachineForAssign.id, assignmentId);
      setFeedback({ type: 'success', message: 'Engineer assignment revoked.' });
      const updated = await machineService.getAssignments(selectedMachineForAssign.id);
      setAssignments(Array.isArray(updated) ? updated : []);
    } catch (err) {
      setFeedback({
        type: 'danger',
        message: getErrorMessage(err, 'Failed to revoke engineer assignment.')
      });
    }
  };

  const filteredMachines = (machines || []).filter(
    (m) =>
      m.name?.toLowerCase().includes(search.toLowerCase()) ||
      m.machine_code?.toLowerCase().includes(search.toLowerCase()) ||
      m.model_number?.toLowerCase().includes(search.toLowerCase()) ||
      m.location?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="container-fluid p-0">
      {/* Page Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h4 className="fw-bold text-dark mb-1">Equipment Registry</h4>
          <p className="text-muted small mb-0">
            Register and monitor industrial machinery active on the production floor.
          </p>
        </div>
        <button onClick={handleOpenModal} className="btn btn-primary-industrial btn-sm d-flex align-items-center gap-1">
          <Plus size={16} /> Register New Machine
        </button>
      </div>

      {/* Global Feedback message */}
      {feedback.message && !showModal && !showAssignModal && (
        <div className={`alert alert-${feedback.type} alert-dismissible fade show py-2 small mb-3`} role="alert">
          <div className="d-flex align-items-center gap-2">
            {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{feedback.message}</span>
          </div>
          <button type="button" className="btn-close py-2" onClick={() => setFeedback({ type: '', message: '' })} />
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-2 align-items-center">
          <div className="col-12 col-md-6 col-lg-4">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                className="form-control border-start-0"
                placeholder="Search by code, name, model, or bay..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="col-12 col-md-6 col-lg-8 text-md-end text-muted small">
            Displaying <strong>{filteredMachines.length}</strong> of {machines.length} total machines
          </div>
        </div>
      </div>

      {/* Machines Grid */}
      {loading ? (
        <LoadingSpinner text="Retrieving equipment registry..." size="lg" />
      ) : filteredMachines.length === 0 ? (
        <EmptyState
          title="No Machines Found"
          description={search ? `No equipment matched "${search}".` : 'No manufacturing machines registered yet.'}
          icon={Cpu}
          actionButton={
            <button onClick={handleOpenModal} className="btn btn-sm btn-primary-industrial mt-2">
              Register First Machine
            </button>
          }
        />
      ) : (
        <div className="row g-3">
          {filteredMachines.map((machine) => (
            <div key={machine.id} className="col-12 col-md-6 col-xl-4">
              <div className="card card-industrial h-100 p-3 bg-white d-flex flex-column">
                <div className="d-flex align-items-start justify-content-between mb-2">
                  <div className="p-2 rounded bg-primary bg-opacity-10 text-primary">
                    <Cpu size={20} />
                  </div>
                  <span className="badge bg-primary text-white font-monospace small px-2 py-1">
                    {machine.machine_code || 'CODE'}
                  </span>
                </div>

                <h6 className="fw-bold text-dark mb-1">{machine.name}</h6>
                
                <div className="d-flex flex-column gap-1 my-2 py-2 border-top border-bottom small text-muted">
                  <div className="d-flex align-items-center gap-2">
                    <Hash size={13} className="text-secondary" />
                    <span>Model: <strong className="text-dark">{machine.model_number || 'N/A'}</strong></span>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <span className="text-secondary" style={{ fontSize: '0.75rem' }}>Make:</span>
                    <span className="text-dark">{machine.manufacturer || 'General Machining'}</span>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <MapPin size={13} className="text-secondary" />
                    <span>{machine.location || 'Factory Floor'}</span>
                  </div>
                </div>

                <p className="text-muted small flex-grow-1 mb-2" style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
                  {machine.description || 'Standard technical documentation specifications.'}
                </p>

                <div className="d-flex align-items-center justify-content-between pt-2 border-top">
                  <div className="d-flex align-items-center gap-1">
                    <button
                      onClick={() => handleOpenAssignModal(machine)}
                      className="btn btn-outline-primary btn-sm d-flex align-items-center gap-1 py-1 px-2"
                      style={{ fontSize: '0.78rem' }}
                    >
                      <Users size={13} /> Assignments
                    </button>
                    <button
                      onClick={() => handleOpenDeleteModal(machine)}
                      className="btn btn-outline-danger btn-sm d-flex align-items-center gap-1 py-1 px-2"
                      style={{ fontSize: '0.78rem' }}
                      title={`Delete ${machine.name}`}
                    >
                      <Trash2 size={13} /> Delete
                    </button>
                  </div>
                  <span className="badge bg-success bg-opacity-10 text-success border border-success small">
                    {machine.status || 'ACTIVE'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Register Machine Modal */}
      {showModal && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0 shadow">
              <div className="modal-header">
                <h5 className="modal-title fw-bold">Register Equipment Asset</h5>
                <button type="button" className="btn-close" onClick={handleCloseModal} disabled={isSubmitting} />
              </div>
              <form onSubmit={handleSubmit}>
                <div className="modal-body p-4">
                  {feedback.message && (
                    <div className="alert alert-danger py-2 small mb-3">{feedback.message}</div>
                  )}

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Machine Code * (Unique uppercase ID)</label>
                    <input
                      type="text"
                      name="machine_code"
                      className="form-control form-control-sm font-monospace"
                      placeholder="e.g. CNC-VMC-850"
                      value={formData.machine_code}
                      onChange={handleInputChange}
                      required
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Machine Name *</label>
                    <input
                      type="text"
                      name="name"
                      className="form-control form-control-sm"
                      placeholder="e.g. Vertical Machining Center 850"
                      value={formData.name}
                      onChange={handleInputChange}
                      required
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="row g-2 mb-3">
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">Manufacturer</label>
                      <input
                        type="text"
                        name="manufacturer"
                        className="form-control form-control-sm"
                        placeholder="e.g. Haas Automation"
                        value={formData.manufacturer}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">Model Number</label>
                      <input
                        type="text"
                        name="model_number"
                        className="form-control form-control-sm"
                        placeholder="e.g. VMC-850-HEAVY"
                        value={formData.model_number}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  <div className="mb-3">
                    <label className="form-label small fw-semibold text-secondary">Floor Location / Bay</label>
                    <input
                      type="text"
                      name="location"
                      className="form-control form-control-sm"
                      placeholder="e.g. Sector 4 - Machining Bay"
                      value={formData.location}
                      onChange={handleInputChange}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="mb-0">
                    <label className="form-label small fw-semibold text-secondary">Technical Description</label>
                    <textarea
                      name="description"
                      rows={3}
                      className="form-control form-control-sm"
                      placeholder="e.g. High-precision 5-axis vertical machining center..."
                      value={formData.description}
                      onChange={handleInputChange}
                      disabled={isSubmitting}
                    />
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
                        <span>Saving...</span>
                      </>
                    ) : (
                      <>
                        <Plus size={15} /> Save Machine
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Manage Engineer Assignments Modal */}
      {showAssignModal && selectedMachineForAssign && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered modal-lg">
            <div className="modal-content border-0 shadow">
              <div className="modal-header">
                <div>
                  <h5 className="modal-title fw-bold mb-0">Engineer Assignments</h5>
                  <span className="text-muted small">
                    Machine: <strong>{selectedMachineForAssign.name}</strong> ({selectedMachineForAssign.machine_code})
                  </span>
                </div>
                <button type="button" className="btn-close" onClick={() => setShowAssignModal(false)} />
              </div>
              <div className="modal-body p-4">
                {/* Assign Form */}
                <form onSubmit={handleAssignEngineer} className="p-3 bg-light rounded border mb-4">
                  <h6 className="fw-semibold mb-2 small text-uppercase">Assign Active Engineer</h6>
                  <div className="row g-2 align-items-center">
                    <div className="col-md-8 col-12">
                      <select
                        className="form-select form-select-sm"
                        value={selectedEngineerId}
                        onChange={(e) => setSelectedEngineerId(e.target.value)}
                        disabled={allEngineers.length === 0}
                      >
                        {allEngineers.length === 0 ? (
                          <option value="">No active engineers found in system</option>
                        ) : (
                          allEngineers.map((eng) => (
                            <option key={eng.id} value={eng.id}>
                              {eng.first_name || eng.last_name ? `${eng.first_name} ${eng.last_name} (${eng.email})` : eng.email}
                            </option>
                          ))
                        )}
                      </select>
                    </div>
                    <div className="col-md-4 col-12">
                      <button
                        type="submit"
                        className="btn btn-sm btn-primary-industrial w-100 d-flex align-items-center justify-content-center gap-1"
                        disabled={!selectedEngineerId || allEngineers.length === 0}
                      >
                        <UserPlus size={14} /> Assign to Machine
                      </button>
                    </div>
                  </div>
                </form>

                {/* Assigned List */}
                <h6 className="fw-semibold small text-uppercase mb-2">Currently Assigned Engineers</h6>
                {loadingAssignments ? (
                  <LoadingSpinner text="Loading assignments..." size="sm" />
                ) : assignments.length === 0 ? (
                  <div className="text-muted small py-3 text-center border rounded bg-white">
                    No engineers assigned to this machine yet. Unassigned engineers cannot query its manuals.
                  </div>
                ) : (
                  <div className="list-group list-group-flush border rounded">
                    {assignments.map((asgn) => (
                      <div key={asgn.id} className="list-group-item d-flex justify-content-between align-items-center p-3">
                        <div className="d-flex align-items-center gap-2">
                          <UserCheck size={18} className="text-success flex-shrink-0" />
                          <div>
                            <div className="fw-semibold small text-dark">
                              {asgn.user?.first_name || asgn.user?.last_name
                                ? `${asgn.user.first_name} ${asgn.user.last_name}`
                                : asgn.user?.email || 'Engineer'}
                            </div>
                            <div className="text-muted small font-monospace" style={{ fontSize: '0.75rem' }}>
                              {asgn.user?.email} | Assigned {formatDateTime(asgn.assigned_at)}
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => handleUnassignEngineer(asgn.id)}
                          className="btn btn-outline-danger btn-sm py-0 px-2 d-flex align-items-center gap-1"
                          style={{ fontSize: '0.75rem' }}
                        >
                          <UserX size={12} /> Revoke
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="modal-footer bg-light py-2 px-4">
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => setShowAssignModal(false)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    
      {/* Delete Machine Confirmation Modal */}
      {showDeleteModal && machineToDelete && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1055 }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0 shadow">
              <div className="modal-header bg-danger text-white">
                <div className="d-flex align-items-center gap-2">
                  <AlertTriangle size={20} />
                  <h5 className="modal-title fw-bold">Delete Machine Asset</h5>
                </div>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => !isDeleting && setShowDeleteModal(false)}
                  disabled={isDeleting}
                />
              </div>
              <div className="modal-body p-4">
                <p className="mb-3 text-dark">
                  Are you sure you want to permanently delete machine <strong>{machineToDelete.name}</strong>?
                </p>

                <div className="card bg-light border p-3 mb-3 small">
                  <div className="d-flex justify-content-between mb-1">
                    <span className="text-muted">Machine Code:</span>
                    <strong className="font-monospace text-dark">{machineToDelete.machine_code}</strong>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span className="text-muted">Associated Manuals:</span>
                    <span className="badge bg-secondary">
                      {deleteDetails.loading ? 'Checking...' : `${deleteDetails.manualsCount} document(s)`}
                    </span>
                  </div>
                  <div className="d-flex justify-content-between">
                    <span className="text-muted">Active Assignments:</span>
                    <span className="badge bg-secondary">
                      {deleteDetails.loading ? 'Checking...' : `${deleteDetails.assignmentsCount} engineer(s)`}
                    </span>
                  </div>
                </div>

                <div className="alert alert-warning py-2 small d-flex align-items-start gap-2 mb-0">
                  <AlertTriangle size={16} className="text-warning flex-shrink-0 mt-1" />
                  <div>
                    <strong>Permanent Action Warning:</strong> Deleting this machine will remove all associated engineer assignments, uploaded manual PDFs, extracted text pages, and ChromaDB vector chunks. This action cannot be undone.
                  </div>
                </div>
              </div>
              <div className="modal-footer bg-light">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => setShowDeleteModal(false)}
                  disabled={isDeleting}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-danger d-flex align-items-center gap-1"
                  onClick={handleConfirmDelete}
                  disabled={isDeleting}
                >
                  {isDeleting ? (
                    <>
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      <span>Deleting Asset & Vectors...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 size={14} />
                      <span>Permanently Delete</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
</div>
  );
}
