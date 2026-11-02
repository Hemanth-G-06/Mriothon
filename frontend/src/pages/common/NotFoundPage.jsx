import React from 'react';
import { Link } from 'react-router-dom';
import { FileQuestion, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export default function NotFoundPage() {
  const { role } = useAuth();
  const homePath = role ? `/${role}` : '/login';

  return (
    <div className="text-center py-5">
      <div className="d-inline-flex p-3 rounded-circle bg-light text-muted mb-3">
        <FileQuestion size={48} />
      </div>
      <h3 className="fw-bold text-dark">404 - Page Not Found</h3>
      <p className="text-muted mb-4">
        The manufacturing resource or page you requested does not exist or has been relocated.
      </p>
      <Link to={homePath} className="btn btn-primary-industrial d-inline-flex align-items-center gap-2">
        <ArrowLeft size={16} /> Return to Dashboard
      </Link>
    </div>
  );
}
