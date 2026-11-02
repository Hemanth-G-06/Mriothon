import React from 'react';
import { CheckCircle2, Clock, AlertTriangle, XCircle, FileText } from 'lucide-react';

export default function StatusBadge({ status }) {
  if (!status) return null;

  const normalized = String(status).toLowerCase().trim();

  let badgeClass = 'badge-status';
  let Icon = FileText;
  let label = status;

  if (normalized === 'indexed' || normalized === 'answered') {
    badgeClass += ' badge-status-indexed';
    Icon = CheckCircle2;
    label = normalized === 'indexed' ? 'Indexed' : 'Answered';
  } else if (normalized === 'processing' || normalized === 'pending') {
    badgeClass += ' badge-status-processing';
    Icon = Clock;
    label = 'Processing';
  } else if (normalized === 'uploaded') {
    badgeClass += ' badge-status-uploaded';
    Icon = FileText;
    label = 'Uploaded';
  } else if (normalized === 'failed') {
    badgeClass += ' badge-status-failed';
    Icon = XCircle;
    label = 'Failed';
  } else if (normalized === 'insufficient_evidence' || normalized.includes('insufficient')) {
    badgeClass += ' badge-status-insufficient';
    Icon = AlertTriangle;
    label = 'Insufficient Evidence';
  } else {
    badgeClass += ' bg-light text-dark border';
  }

  return (
    <span className={badgeClass}>
      <Icon size={12} strokeWidth={2.5} />
      <span>{label}</span>
    </span>
  );
}
