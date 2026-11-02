import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Cpu, FileText, CheckCircle2, Clock, PlusCircle, Upload, ArrowRight, AlertCircle } from 'lucide-react';
import { machineService } from '../../services/machineService';
import { documentService } from '../../services/documentService';
import StatusBadge from '../../components/common/StatusBadge';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { formatDateTime, formatFileSize } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

export default function AdminDashboard() {
  const [machines, setMachines] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const results = await Promise.allSettled([
          machineService.getMachines(),
          documentService.getDocuments()
        ]);

        const [mRes, dRes] = results;

        if (mRes.status === 'fulfilled') {
          setMachines(Array.isArray(mRes.value) ? mRes.value : (mRes.value?.results || []));
        } else {
          console.warn('Machines failed to load:', mRes.reason);
        }

        if (dRes.status === 'fulfilled') {
          setDocuments(Array.isArray(dRes.value) ? dRes.value : (dRes.value?.results || []));
        } else {
          console.warn('Documents failed to load:', dRes.reason);
        }

        const failed = results.filter((r) => r.status === 'rejected');
        if (failed.length === results.length) {
          setErrorMessage(getErrorMessage(failed[0]?.reason, 'Unable to load administration data from backend.'));
        }
      } catch (err) {
        console.error('Failed to load admin overview data:', err);
        setErrorMessage(getErrorMessage(err, 'Unexpected error loading administration overview.'));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Poll for document status updates if any document is in non-terminal state (Uploaded or Processing)
  useEffect(() => {
    const hasPending = documents.some((d) => {
      const s = d.status?.toLowerCase();
      return s === 'uploaded' || s === 'processing';
    });

    if (!hasPending) return;

    const timer = setInterval(async () => {
      try {
        const updated = await documentService.getDocuments();
        const docList = Array.isArray(updated) ? updated : (updated?.results || []);
        setDocuments(docList);
      } catch (e) {
        console.warn('Status polling error:', e);
      }
    }, 4000);

    return () => clearInterval(timer);
  }, [documents]);

  if (loading) {
    return <LoadingSpinner text="Loading admin telemetry and equipment catalogs..." size="lg" />;
  }

  const indexedCount = documents.filter((d) => d.status?.toLowerCase() === 'indexed').length;
  const processingCount = documents.filter((d) => d.status?.toLowerCase() === 'processing').length;

  return (
    <div className="container-fluid p-0">
      {/* Welcome & Overview Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <h4 className="fw-bold text-dark mb-1">Plant Administration</h4>
          <p className="text-muted small mb-0">
            Manage industrial machinery registry, PDF technical manuals, and RAG vector indexing pipeline.
          </p>
        </div>
        <div className="d-flex gap-2">
          <Link to="/admin/machines" className="btn btn-outline-primary btn-sm d-flex align-items-center gap-1">
            <PlusCircle size={15} /> Register Machine
          </Link>
          <Link to="/admin/documents" className="btn btn-primary-industrial btn-sm d-flex align-items-center gap-1">
            <Upload size={15} /> Upload Manual
          </Link>
        </div>
      </div>

      {/* API Error Notification */}
      {errorMessage && (
        <div className="alert alert-warning py-2 small d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center gap-2">
            <AlertCircle size={16} className="text-warning flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button className="btn btn-sm btn-link text-dark p-0" onClick={() => setErrorMessage(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="row g-3 mb-4">
        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">REGISTERED MACHINES</span>
              <div className="p-2 rounded bg-primary bg-opacity-10 text-primary">
                <Cpu size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-dark mb-1">{machines.length}</h3>
            <span className="text-muted small">Active manufacturing assets</span>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">UPLOADED MANUALS</span>
              <div className="p-2 rounded bg-info bg-opacity-10 text-info">
                <FileText size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-dark mb-1">{documents.length}</h3>
            <span className="text-muted small">PDF documents registered</span>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">INDEXED IN RAG</span>
              <div className="p-2 rounded bg-success bg-opacity-10 text-success">
                <CheckCircle2 size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-success mb-1">{indexedCount}</h3>
            <span className="text-muted small">Chunked & embedded for AI</span>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">PROCESSING QUEUE</span>
              <div className="p-2 rounded bg-warning bg-opacity-10 text-warning">
                <Clock size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-warning mb-1">{processingCount}</h3>
            <span className="text-muted small">Pending vectorization</span>
          </div>
        </div>
      </div>

      {/* Two Column Grid: Recent Machines & Recent Documents */}
      <div className="row g-4">
        {/* Recent Machines Table */}
        <div className="col-lg-6 col-12">
          <div className="card card-industrial h-100">
            <div className="card-header bg-white border-bottom py-3 d-flex align-items-center justify-content-between">
              <h6 className="fw-bold text-dark mb-0 d-flex align-items-center gap-2">
                <Cpu size={16} className="text-primary" /> Registered Machines
              </h6>
              <Link to="/admin/machines" className="text-decoration-none small d-flex align-items-center gap-1">
                View All <ArrowRight size={13} />
              </Link>
            </div>
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th className="small text-secondary fw-semibold">Machine Name</th>
                    <th className="small text-secondary fw-semibold">Model / S/N</th>
                    <th className="small text-secondary fw-semibold text-center">Manuals</th>
                  </tr>
                </thead>
                <tbody>
                  {machines.length === 0 ? (
                    <tr>
                      <td colSpan="3" className="text-center text-muted small py-4">
                        No equipment records found from backend endpoint (/api/machines/).
                      </td>
                    </tr>
                  ) : (
                    machines.slice(0, 4).map((m) => (
                      <tr key={m.id}>
                        <td>
                          <div className="fw-semibold text-dark small">{m.name}</div>
                          <div className="text-muted" style={{ fontSize: '0.72rem' }}>{m.location || 'Plant Floor'}</div>
                        </td>
                        <td className="small text-muted">
                          <div>{m.model_number || 'Standard'}</div>
                          <div className="font-monospace text-secondary" style={{ fontSize: '0.7rem' }}>{m.serial_number}</div>
                        </td>
                        <td className="text-center">
                          <span className="badge bg-light text-dark border">
                            {m.manuals_count || 0}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Recent Documents Table */}
        <div className="col-lg-6 col-12">
          <div className="card card-industrial h-100">
            <div className="card-header bg-white border-bottom py-3 d-flex align-items-center justify-content-between">
              <h6 className="fw-bold text-dark mb-0 d-flex align-items-center gap-2">
                <FileText size={16} className="text-primary" /> Technical Manuals Status
              </h6>
              <Link to="/admin/documents" className="text-decoration-none small d-flex align-items-center gap-1">
                Manage Manuals <ArrowRight size={13} />
              </Link>
            </div>
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th className="small text-secondary fw-semibold">Document Title</th>
                    <th className="small text-secondary fw-semibold">Type & Rev</th>
                    <th className="small text-secondary fw-semibold text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan="3" className="text-center text-muted small py-4">
                        No technical manuals recorded from backend endpoint (/api/documents/).
                      </td>
                    </tr>
                  ) : (
                    documents.slice(0, 4).map((d) => (
                      <tr key={d.id}>
                        <td>
                          <div className="fw-semibold text-dark small">{d.title}</div>
                          <div className="text-muted" style={{ fontSize: '0.72rem' }}>
                            {formatFileSize(d.file_size)} • {formatDateTime(d.created_at)}
                          </div>
                        </td>
                        <td className="small text-muted">
                          <div>{d.manual_type || 'Operations'}</div>
                          <span className="badge bg-light text-secondary border" style={{ fontSize: '0.68rem' }}>
                            {d.revision || 'Rev 1.0'}
                          </span>
                        </td>
                        <td className="text-center">
                          <StatusBadge status={d.status} />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
