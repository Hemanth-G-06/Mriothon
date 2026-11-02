import React, { useState, useEffect } from 'react';
import { History, Search, Filter, MessageSquare, CheckCircle2, AlertTriangle, Eye, ShieldCheck, Calendar, User, Cpu } from 'lucide-react';
import { supervisorService } from '../../services/supervisorService';
import { machineService } from '../../services/machineService';
import StatusBadge from '../../components/common/StatusBadge';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import QuestionDetailModal from './QuestionDetailModal';
import PdfViewerModal from '../../components/pdf/PdfViewerModal';
import { formatDateTime, truncateText } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errorHandler';

export default function SupervisorDashboard() {
  const [historyRecords, setHistoryRecords] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  // Filters State
  const [filters, setFilters] = useState({
    search: '',
    machine: '',
    engineer: '',
    date: '',
    status: ''
  });

  // Selected Record for Detail Modal
  const [selectedRecord, setSelectedRecord] = useState(null);

  // PDF Viewer Modal State
  const [pdfModal, setPdfModal] = useState({
    isOpen: false,
    documentId: null,
    documentTitle: '',
    revision: '',
    pageNumber: 1,
    directPdfUrl: null
  });

  const loadData = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const results = await Promise.allSettled([
        supervisorService.getHistory(filters),
        supervisorService.getStatistics(),
        machineService.getMachines()
      ]);

      const [histRes, statsRes, machRes] = results;

      if (histRes.status === 'fulfilled') {
        const histData = histRes.value;
        setHistoryRecords(histData?.results || (Array.isArray(histData) ? histData : []));
      } else {
        console.warn('Supervisor history failed to load:', histRes.reason);
      }

      if (statsRes.status === 'fulfilled') {
        setStatistics(statsRes.value || null);
      } else {
        console.warn('Supervisor statistics failed to load:', statsRes.reason);
      }

      if (machRes.status === 'fulfilled') {
        setMachines(machRes.value || []);
      } else {
        console.warn('Machines failed to load:', machRes.reason);
      }

      const failed = results.filter((r) => r.status === 'rejected');
      if (failed.length === results.length) {
        setErrorMessage(getErrorMessage(failed[0]?.reason, 'Unable to load supervisor data from the backend. Please check network connection.'));
      }
    } catch (err) {
      console.error('Failed to load supervisor data:', err);
      setErrorMessage(getErrorMessage(err, 'Unexpected error loading supervisor dashboard data.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filters]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleResetFilters = () => {
    setFilters({
      search: '',
      machine: '',
      engineer: '',
      date: '',
      status: ''
    });
  };

  const handleOpenPdf = (pdfInfo) => {
    if (!pdfInfo?.document_id && !pdfInfo?.pdf_url) {
      setErrorMessage('Citation metadata is missing document identifier. Unable to open PDF manual.');
      return;
    }
    setPdfModal({
      isOpen: true,
      documentId: pdfInfo.document_id,
      documentTitle: pdfInfo.document_title || 'Technical Manual',
      revision: pdfInfo.revision || 'Rev 1.0',
      pageNumber: Math.max(1, Number(pdfInfo.page_number) || 1),
      directPdfUrl: pdfInfo.pdf_url || null
    });
  };

  return (
    <div className="container-fluid p-0">
      {/* Page Header */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
        <div>
          <div className="d-flex align-items-center gap-2 mb-1">
            <h4 className="fw-bold text-dark mb-0">Supervisor Intelligence & Audit</h4>
            <span className="badge bg-secondary bg-opacity-10 text-secondary border d-flex align-items-center gap-1 small">
              <ShieldCheck size={12} /> Read-Only Audit Log
            </span>
          </div>
          <p className="text-muted small mb-0">
            Monitor operator inquiries, verify manual grounding accuracy, and inspect insufficient-evidence escalations.
          </p>
        </div>
      </div>

      {/* API Error Notification */}
      {errorMessage && (
        <div className="alert alert-warning py-2 small d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center gap-2">
            <AlertTriangle size={16} className="text-warning flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button className="btn btn-sm btn-link text-dark p-0" onClick={() => setErrorMessage(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Statistics Cards */}
      <div className="row g-3 mb-4">
        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">TOTAL INQUIRIES</span>
              <div className="p-2 rounded bg-primary bg-opacity-10 text-primary">
                <MessageSquare size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-dark mb-1">{statistics?.total_questions || 0}</h3>
            <span className="text-muted small">Recorded operator questions</span>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">ANSWERED & GROUNDED</span>
              <div className="p-2 rounded bg-success bg-opacity-10 text-success">
                <CheckCircle2 size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-success mb-1">{statistics?.answered_questions || 0}</h3>
            <span className="text-muted small">Backed by manual citations</span>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">INSUFFICIENT EVIDENCE</span>
              <div className="p-2 rounded bg-warning bg-opacity-10 text-warning">
                <AlertTriangle size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-warning mb-1">{statistics?.insufficient_evidence_questions || 0}</h3>
            <span className="text-muted small">Manual coverage gap flagged</span>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div className="card card-industrial p-3 h-100">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <span className="text-muted small fw-semibold">MACHINES MONITORED</span>
              <div className="p-2 rounded bg-info bg-opacity-10 text-info">
                <Cpu size={18} />
              </div>
            </div>
            <h3 className="fw-bold text-dark mb-1">{machines.length}</h3>
            <span className="text-muted small">Active equipment lines</span>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="card card-industrial p-3 bg-white mb-4">
        <div className="row g-2 align-items-center">
          {/* Keyword Search */}
          <div className="col-12 col-md-3">
            <div className="input-group input-group-sm">
              <span className="input-group-text bg-light border-end-0">
                <Search size={14} className="text-muted" />
              </span>
              <input
                type="text"
                name="search"
                className="form-control border-start-0"
                placeholder="Search questions or keywords..."
                value={filters.search}
                onChange={handleFilterChange}
              />
            </div>
          </div>

          {/* Machine Filter */}
          <div className="col-6 col-md-2">
            <select
              name="machine"
              className="form-select form-select-sm"
              value={filters.machine}
              onChange={handleFilterChange}
            >
              <option value="">All Machines</option>
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="col-6 col-md-2">
            <select
              name="status"
              className="form-select form-select-sm"
              value={filters.status}
              onChange={handleFilterChange}
            >
              <option value="">All Statuses</option>
              <option value="answered">Answered</option>
              <option value="insufficient_evidence">Insufficient Evidence</option>
            </select>
          </div>

          {/* Engineer Search */}
          <div className="col-6 col-md-2">
            <input
              type="text"
              name="engineer"
              className="form-control form-control-sm"
              placeholder="Filter Engineer..."
              value={filters.engineer}
              onChange={handleFilterChange}
            />
          </div>

          {/* Date Filter */}
          <div className="col-6 col-md-2">
            <input
              type="date"
              name="date"
              className="form-control form-control-sm"
              value={filters.date}
              onChange={handleFilterChange}
            />
          </div>

          {/* Reset Filters */}
          <div className="col-12 col-md-1 text-md-end">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary w-100"
              onClick={handleResetFilters}
              title="Reset all filters"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* History Table */}
      {loading ? (
        <LoadingSpinner text="Loading question audit records..." size="lg" />
      ) : historyRecords.length === 0 ? (
        <EmptyState
          title="No Audit Records Found"
          description="No question records match your selected filter criteria."
          icon={History}
          actionButton={
            <button className="btn btn-sm btn-outline-primary mt-2" onClick={handleResetFilters}>
              Clear Filters
            </button>
          }
        />
      ) : (
        <div className="card card-industrial bg-white overflow-hidden">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th className="small text-secondary fw-semibold">Timestamp</th>
                  <th className="small text-secondary fw-semibold">Engineer</th>
                  <th className="small text-secondary fw-semibold">Target Machine</th>
                  <th className="small text-secondary fw-semibold" style={{ width: '38%' }}>Question</th>
                  <th className="small text-secondary fw-semibold text-center">Status</th>
                  <th className="small text-secondary fw-semibold text-center">Citations</th>
                  <th className="small text-secondary fw-semibold text-end">Action</th>
                </tr>
              </thead>
              <tbody>
                {historyRecords.map((item) => (
                  <tr key={item.id}>
                    <td className="small text-muted" style={{ whiteSpace: 'nowrap' }}>
                      {formatDateTime(item.created_at)}
                    </td>
                    <td className="small text-dark fw-medium">
                      {item.engineer_name || 'Engineer #2'}
                    </td>
                    <td className="small text-muted">
                      {item.machine_name || `Machine #${item.machine_id}`}
                    </td>
                    <td className="small text-dark">
                      <div className="fw-medium">{truncateText(item.question, 75)}</div>
                    </td>
                    <td className="text-center">
                      <StatusBadge status={item.is_insufficient_evidence ? 'insufficient_evidence' : 'answered'} />
                    </td>
                    <td className="text-center">
                      <span className="badge bg-light text-secondary border">
                        {item.citations?.length || 0}
                      </span>
                    </td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1"
                        style={{ fontSize: '0.78rem' }}
                        onClick={() => setSelectedRecord(item)}
                        title="Inspect full audit record"
                      >
                        <Eye size={13} /> Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Question Details Audit Modal */}
      <QuestionDetailModal
        isOpen={!!selectedRecord}
        record={selectedRecord}
        onClose={() => setSelectedRecord(null)}
        onOpenPdf={handleOpenPdf}
      />

      {/* PDF Viewer Modal */}
      <PdfViewerModal
        isOpen={pdfModal.isOpen}
        onClose={() => setPdfModal({ ...pdfModal, isOpen: false })}
        documentId={pdfModal.documentId}
        documentTitle={pdfModal.documentTitle}
        revision={pdfModal.revision}
        pageNumber={pdfModal.pageNumber}
        directPdfUrl={pdfModal.directPdfUrl}
      />
    </div>
  );
}
