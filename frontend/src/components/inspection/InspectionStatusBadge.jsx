import React from 'react';
import { CheckCircle2, AlertOctagon, Clock, XCircle, CheckCheck, Edit3 } from 'lucide-react';

/**
 * InspectionStatusBadge
 * Formats prediction classes, processing statuses, and supervisor review states
 * with professional industrial styling.
 */
export default function InspectionStatusBadge({ type = 'class', value }) {
  if (!value) return null;

  const normalized = String(value).toLowerCase().trim();

  // 1. Predicted Class: Normal vs Defective
  if (type === 'class') {
    if (normalized === 'normal') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#dcfce7',
            color: '#15803d',
            border: '1px solid #bbf7d0',
            fontWeight: 600,
            fontSize: '0.78rem'
          }}
        >
          <CheckCircle2 size={13} strokeWidth={2.5} />
          <span>Normal</span>
        </span>
      );
    }
    if (normalized === 'defective') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#fee2e2',
            color: '#b91c1c',
            border: '1px solid #fecaca',
            fontWeight: 600,
            fontSize: '0.78rem'
          }}
        >
          <AlertOctagon size={13} strokeWidth={2.5} />
          <span>Defective</span>
        </span>
      );
    }
    return <span className="badge bg-light text-dark border">{value}</span>;
  }

  // 2. Processing Status: Queued, Processing, Completed, Failed
  if (type === 'processing') {
    if (normalized === 'completed') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#dcfce7',
            color: '#15803d',
            border: '1px solid #bbf7d0',
            fontSize: '0.75rem'
          }}
        >
          <CheckCircle2 size={12} strokeWidth={2.5} />
          <span>Completed</span>
        </span>
      );
    }
    if (normalized === 'processing') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#fef3c7',
            color: '#b45309',
            border: '1px solid #fde68a',
            fontSize: '0.75rem'
          }}
        >
          <span className="spinner-border spinner-border-sm" style={{ width: 10, height: 10 }} />
          <span>Processing</span>
        </span>
      );
    }
    if (normalized === 'queued') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#e0f2fe',
            color: '#0369a1',
            border: '1px solid #bae6fd',
            fontSize: '0.75rem'
          }}
        >
          <Clock size={12} strokeWidth={2.5} />
          <span>Queued</span>
        </span>
      );
    }
    if (normalized === 'failed') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#fee2e2',
            color: '#b91c1c',
            border: '1px solid #fecaca',
            fontSize: '0.75rem'
          }}
        >
          <XCircle size={12} strokeWidth={2.5} />
          <span>Failed</span>
        </span>
      );
    }
    return <span className="badge bg-light text-dark border">{value}</span>;
  }

  // 3. Supervisor Review Status: pending, confirmed, corrected
  if (type === 'review') {
    if (normalized === 'confirmed') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#eff6ff',
            color: '#1d4ed8',
            border: '1px solid #bfdbfe',
            fontSize: '0.75rem'
          }}
        >
          <CheckCheck size={12} strokeWidth={2.5} />
          <span>Confirmed</span>
        </span>
      );
    }
    if (normalized === 'corrected') {
      return (
        <span
          className="badge d-inline-flex align-items-center gap-1 px-2 py-1"
          style={{
            backgroundColor: '#fdf4ff',
            color: '#86198f',
            border: '1px solid #f5d0fe',
            fontSize: '0.75rem'
          }}
        >
          <Edit3 size={12} strokeWidth={2.5} />
          <span>Corrected</span>
        </span>
      );
    }
    // Default or pending
    return (
      <span
        className="badge d-inline-flex align-items-center gap-1 px-2 py-1 text-secondary border bg-light"
        style={{ fontSize: '0.75rem' }}
      >
        <Clock size={12} />
        <span>Pending Review</span>
      </span>
    );
  }

  return <span className="badge bg-light text-dark border">{value}</span>;
}
