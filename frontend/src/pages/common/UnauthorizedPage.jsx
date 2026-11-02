import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export default function UnauthorizedPage() {
  const { role } = useAuth();
  const homePath = role ? `/${role}` : '/login';

  return (
    <div className="text-center py-5">
      <div className="d-inline-flex p-3 rounded-circle bg-danger bg-opacity-10 text-danger mb-3">
        <ShieldAlert size={48} />
      </div>
      <h3 className="fw-bold text-dark">403 - Access Forbidden</h3>
      <p className="text-muted mb-4 max-w-md mx-auto">
        Your current role (<strong>{role || 'Guest'}</strong>) does not have authorization to view this section.
        Access permissions are governed by role-based operational policies.
      </p>
      <Link to={homePath} className="btn btn-outline-primary d-inline-flex align-items-center gap-2">
        <ArrowLeft size={16} /> Return to Your Portal
      </Link>
    </div>
  );
}
