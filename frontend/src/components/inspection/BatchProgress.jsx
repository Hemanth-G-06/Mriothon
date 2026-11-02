import React from 'react';
import { CheckCircle2, XCircle, Clock, RefreshCw, Layers } from 'lucide-react';

/**
 * BatchProgress Component
 * Displays batch execution metrics, progress bar, and refresh trigger.
 */
export default function BatchProgress({
  total = 0,
  completed = 0,
  failed = 0,
  pending = 0,
  isRefreshing = false,
  onRefresh
}) {
  const processed = completed + failed;
  const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
  const isFinished = total > 0 && processed === total;

  return (
    <div className="card card-industrial p-3 bg-white mb-4">
      <div className="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center pb-2 mb-3 border-bottom gap-2">
        <div className="d-flex align-items-center gap-2">
          <Layers size={18} className="text-primary" />
          <h6 className="fw-bold text-dark mb-0">Batch Inspection Execution Telemetry</h6>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw size={13} className={isRefreshing ? 'spinner-border spinner-border-sm' : ''} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh Status'}</span>
          </button>
        )}
      </div>

      {/* Metric Counters */}
      <div className="row g-2 mb-3 text-center">
        <div className="col-3">
          <div className="p-2 rounded bg-light border">
            <div className="text-muted small" style={{ fontSize: '0.7rem' }}>TOTAL</div>
            <div className="fw-bold text-dark fs-5">{total}</div>
          </div>
        </div>
        <div className="col-3">
          <div className="p-2 rounded bg-success bg-opacity-10 border border-success border-opacity-25 text-success">
            <div className="small" style={{ fontSize: '0.7rem' }}>COMPLETED</div>
            <div className="fw-bold fs-5">{completed}</div>
          </div>
        </div>
        <div className="col-3">
          <div className="p-2 rounded bg-danger bg-opacity-10 border border-danger border-opacity-25 text-danger">
            <div className="small" style={{ fontSize: '0.7rem' }}>FAILED</div>
            <div className="fw-bold fs-5">{failed}</div>
          </div>
        </div>
        <div className="col-3">
          <div className="p-2 rounded bg-warning bg-opacity-10 border border-warning border-opacity-25 text-warning-emphasis">
            <div className="small" style={{ fontSize: '0.7rem' }}>PENDING</div>
            <div className="fw-bold fs-5">{pending}</div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="d-flex justify-content-between small text-muted mb-1" style={{ fontSize: '0.75rem' }}>
          <span>Overall Batch Progress</span>
          <span className="fw-bold text-dark">{percentage}% ({processed} of {total} processed)</span>
        </div>
        <div className="progress" style={{ height: '8px' }}>
          <div
            className={`progress-bar progress-bar-striped ${!isFinished ? 'progress-bar-animated' : ''} ${
              failed > 0 && completed === 0 ? 'bg-danger' : 'bg-primary'
            }`}
            role="progressbar"
            style={{ width: `${percentage}%` }}
            aria-valuenow={percentage}
            aria-valuemin="0"
            aria-valuemax="100"
          />
        </div>
      </div>
    </div>
  );
}
