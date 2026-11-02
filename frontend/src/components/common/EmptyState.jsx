import React from 'react';
import { FolderSearch } from 'lucide-react';

export default function EmptyState({
  title = 'No records found',
  description = 'There are no items matching your criteria.',
  icon: Icon = FolderSearch,
  actionButton = null
}) {
  return (
    <div className="text-center p-5 border border-dashed rounded-3 bg-white my-3">
      <div className="d-inline-flex p-3 rounded-circle bg-light text-secondary mb-3">
        <Icon size={32} />
      </div>
      <h6 className="fw-semibold text-dark mb-1">{title}</h6>
      <p className="text-muted small mb-3 max-w-sm mx-auto">{description}</p>
      {actionButton}
    </div>
  );
}
