import React, { useState, useEffect } from 'react';
import { Cpu, Plus, Search, CheckCircle2, AlertCircle, MapPin, Hash, FileText } from 'lucide-react';
import { machineService } from '../../services/machineService';
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

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    model_number: '',
    serial_number: '',
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
      model_number: '',
      serial_number: '',
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

  const filteredMachines = (machines || []).filter(
    (m) =>
      m.name?.toLowerCase().includes(search.toLowerCase()) ||
      m.model_number?.toLowerCase().includes(search.toLowerCase()) ||
      m.serial_number?.toLowerCase().includes(search.toLowerCase()) ||
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
      {feedback.message && !showModal && (
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
                placeholder="Search by name, model, serial #, or bay..."
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
                  <span className="badge bg-light text-secondary border small">
                    <FileText size={11} className="me-1 inline" />
                    {machine.manuals_count || 0} Manuals
                  </span>
                </div>

                <h6 className="fw-bold text-dark mb-1">{machine.name}</h6>
                
                <div className="d-flex flex-column gap-1 my-2 py-2 border-top border-bottom small text-muted">
                  <div className="d-flex align-items-center gap-2">
                    <Hash size={13} className="text-secondary" />
                    <span>Model: <strong className="text-dark">{machine.model_number || 'N/A'}</strong></span>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <span className="font-monospace text-secondary" style={{ fontSize: '0.75rem' }}>S/N:</span>
                    <span className="font-monospace text-dark">{machine.serial_number || 'Unspecified'}</span>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <MapPin size={13} className="text-secondary" />
                    <span>{machine.location || 'Factory Floor'}</span>
                  </div>
                </div>

                <p className="text-muted small flex-grow-1 mb-2" style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
                  {machine.description || 'No detailed specifications entered.'}
                </p>

                <div className="pt-2 border-top text-muted d-flex justify-content-between" style={{ fontSize: '0.72rem' }}>
                  <span>Registered:</span>
                  <span>{formatDateTime(machine.created_at)}</span>
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
                    <label className="form-label small fw-semibold text-secondary">Machine Name *</label>
                    <input
                      type="text"
                      name="name"
                      className="form-control form-control-sm"
                      placeholder="e.g. HP-200 CNC Milling Center"
                      value={formData.name}
                      onChange={handleInputChange}
                      required
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="row g-2 mb-3">
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">Model Number</label>
                      <input
                        type="text"
                        name="model_number"
                        className="form-control form-control-sm"
                        placeholder="e.g. HP-200-V4"
                        value={formData.model_number}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                      />
                    </div>
                    <div className="col-6">
                      <label className="form-label small fw-semibold text-secondary">Serial Number</label>
                      <input
                        type="text"
                        name="serial_number"
                        className="form-control form-control-sm"
                        placeholder="e.g. CNC-2023-8891"
                        value={formData.serial_number}
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
                      placeholder="e.g. Bay 3, Plant Alpha"
                      value={formData.location}
                      onChange={handleInputChange}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="mb-0">
                    <label className="form-label small fw-semibold text-secondary">Technical Description & Specs</label>
                    <textarea
                      name="description"
                      rows={3}
                      className="form-control form-control-sm"
                      placeholder="e.g. High-precision 5-axis vertical machining center used for tooling..."
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
    </div>
  );
}
