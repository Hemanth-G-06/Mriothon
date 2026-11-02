import React from 'react';

export default function LoadingSpinner({ text = 'Loading...', size = 'md', className = '' }) {
  const spinnerClass = size === 'sm' ? 'spinner-border-sm' : size === 'lg' ? 'spinner-border-lg' : '';

  return (
    <div className={`d-flex flex-column align-items-center justify-content-center p-4 ${className}`}>
      <div className={`spinner-border text-primary ${spinnerClass}`} role="status">
        <span className="visually-hidden">{text}</span>
      </div>
      {text && <p className="mt-2 text-muted small mb-0">{text}</p>}
    </div>
  );
}
