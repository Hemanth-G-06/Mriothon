import React from 'react';
import ReactMarkdown from 'react-markdown';
import { X, User, Cpu, Clock, Layers, AlertTriangle, CheckCircle2, BookOpen } from 'lucide-react';
import StatusBadge from '../../components/common/StatusBadge';
import { formatDateTime } from '../../utils/formatters';

export default function QuestionDetailModal({ isOpen, onClose, record, onOpenPdf }) {
  if (!isOpen || !record) return null;

  return (
    <div
      className="modal fade show d-block"
      tabIndex="-1"
      style={{ backgroundColor: 'rgba(15, 23, 42, 0.75)', zIndex: 1040 }}
    >
      <div className="modal-dialog modal-lg modal-dialog-centered">
        <div className="modal-content border-0 shadow-lg">
          {/* Header */}
          <div className="modal-header bg-white border-bottom py-3">
            <div>
              <div className="d-flex align-items-center gap-2 mb-1">
                <StatusBadge status={record.is_insufficient_evidence ? 'insufficient_evidence' : 'answered'} />
                <span className="text-muted small">Record ID: #{record.id}</span>
              </div>
              <h6 className="modal-title fw-bold text-dark mb-0">Supervisor Audit: Question Inquiry Details</h6>
            </div>
            <button type="button" className="btn-close" onClick={onClose} aria-label="Close" />
          </div>

          <div className="modal-body p-4 bg-light">
            {/* Metadata strip */}
            <div className="card card-industrial p-3 bg-white mb-3">
              <div className="row g-2 small">
                <div className="col-12 col-sm-4 d-flex align-items-center gap-2">
                  <User size={15} className="text-secondary" />
                  <div>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>OPERATOR / ENGINEER</div>
                    <div className="fw-semibold text-dark">{record.engineer_name || 'Plant Engineer'}</div>
                  </div>
                </div>

                <div className="col-12 col-sm-4 d-flex align-items-center gap-2">
                  <Cpu size={15} className="text-secondary" />
                  <div>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>TARGET MACHINE</div>
                    <div className="fw-semibold text-dark">{record.machine_name || `Machine #${record.machine_id}`}</div>
                  </div>
                </div>

                <div className="col-12 col-sm-4 d-flex align-items-center gap-2">
                  <Clock size={15} className="text-secondary" />
                  <div>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>TIMESTAMP</div>
                    <div className="fw-semibold text-dark">{formatDateTime(record.created_at)}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Question Box */}
            <div className="card card-industrial p-3 bg-white mb-3">
              <div className="text-muted small fw-semibold mb-1 text-uppercase" style={{ fontSize: '0.72rem' }}>
                Question Submitted:
              </div>
              <p className="fw-medium text-dark mb-0" style={{ fontSize: '0.92rem' }}>
                {record.question}
              </p>
            </div>

            {/* Answer Box */}
            <div className="card card-industrial p-3 bg-white mb-3">
              <div className="d-flex align-items-center justify-content-between mb-2">
                <span className="text-muted small fw-semibold text-uppercase" style={{ fontSize: '0.72rem' }}>
                  Grounded AI Answer:
                </span>
                {record.is_insufficient_evidence ? (
                  <span className="badge bg-warning bg-opacity-25 text-warning-emphasis small">
                    Flagged: Insufficient Evidence
                  </span>
                ) : (
                  <span className="badge bg-success bg-opacity-25 text-success-emphasis small">
                    Grounded in Manuals
                  </span>
                )}
              </div>

              {record.is_insufficient_evidence ? (
                <div className="alert alert-warning py-2 small mb-0 d-flex align-items-start gap-2">
                  <AlertTriangle size={16} className="text-warning flex-shrink-0 mt-1" />
                  <div>{record.answer}</div>
                </div>
              ) : (
                <div className="text-dark small" style={{ lineHeight: '1.55' }}>
                  <ReactMarkdown>{record.answer}</ReactMarkdown>
                </div>
              )}
            </div>

            {/* Citations Audit List */}
            <div className="card card-industrial p-3 bg-white">
              <div className="d-flex align-items-center gap-2 mb-2 pb-1 border-bottom">
                <Layers size={15} className="text-primary" />
                <span className="fw-semibold small text-dark">
                  Referenced Manual Citations ({record.citations?.length || 0})
                </span>
              </div>

              {!record.citations || record.citations.length === 0 ? (
                <p className="text-muted small mb-0">No direct manual citations recorded for this answer.</p>
              ) : (
                <div className="d-flex flex-column gap-2">
                  {record.citations.map((c, i) => (
                    <div key={c.id || i} className="p-2 border rounded bg-light d-flex justify-content-between align-items-center">
                      <div>
                        <div className="fw-semibold small text-dark d-flex align-items-center gap-1">
                          <BookOpen size={13} className="text-primary" />
                          <span>{c.document_title}</span>
                          <span className="badge bg-secondary ms-1 small" style={{ fontSize: '0.68rem' }}>
                            {c.revision || 'Rev 1.0'}
                          </span>
                        </div>
                        {c.snippet && (
                          <div className="text-muted small font-monospace mt-1" style={{ fontSize: '0.74rem' }}>
                            "{c.snippet}"
                          </div>
                        )}
                      </div>

                      <div className="d-flex align-items-center gap-2 flex-shrink-0 ms-3">
                        <span className="badge bg-primary text-white" style={{ fontSize: '0.75rem' }}>
                          Page {c.page_number}
                        </span>
                        <button
                          className="btn btn-sm btn-outline-primary"
                          style={{ fontSize: '0.72rem' }}
                          onClick={() =>
                            onOpenPdf({
                              document_id: c.document_id,
                              document_title: c.document_title,
                              revision: c.revision,
                              page_number: c.page_number,
                              pdf_url: c.pdf_url
                            })
                          }
                        >
                          View Page
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="modal-footer bg-white py-2 px-4">
            <button type="button" className="btn btn-sm btn-secondary" onClick={onClose}>
              Close Audit Record
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
