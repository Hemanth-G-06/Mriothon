import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Cpu,
  FileText,
  MessageSquare,
  History,
  X,
  HardHat,
  Package,
  Scan,
  Layers,
  ShieldCheck,
  LogOut
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export default function Sidebar({ isOpen, onClose }) {
  const { role, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    if (onClose) onClose();
    await logout();
    navigate('/login', { replace: true });
  };

  const normalizedRole = role ? role.toLowerCase() : '';

  const getNavLinks = () => {
    switch (normalizedRole) {
      case 'admin':
        return [
          { to: '/admin', label: 'Admin Overview', icon: LayoutDashboard },
          { to: '/admin/users', label: 'Users & Roles', icon: Users },
          { to: '/admin/machines', label: 'Registered Machines', icon: Cpu },
          { to: '/admin/products', label: 'Product Registry', icon: Package },
          { to: '/admin/documents', label: 'Manuals & Upload', icon: FileText }
        ];
      case 'engineer':
        return [
          { to: '/engineer', label: 'Manual Assistant', icon: MessageSquare },
          { to: '/engineer/quality-inspection', label: 'Single Inspection', icon: Scan },
          { to: '/engineer/batch-inspection', label: 'Batch Inspection', icon: Layers },
          { to: '/engineer/inspection-history', label: 'Inspection History', icon: History }
        ];
      case 'supervisor':
        return [
          { to: '/supervisor', label: 'Manual QA Audit', icon: History },
          { to: '/supervisor/inspection-review', label: 'Inspection Review', icon: ShieldCheck }
        ];
      default:
        return [];
    }
  };

  const navLinks = getNavLinks();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="modal-backdrop fade show d-lg-none"
          style={{ zIndex: 99 }}
          onClick={onClose}
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'show' : ''}`}>
        {/* Sidebar Header */}
        <div className="p-3 border-bottom border-secondary border-opacity-25 d-flex align-items-center justify-content-between">
          <div className="d-flex align-items-center gap-2">
            <div className="p-2 bg-primary rounded text-white">
              <HardHat size={20} />
            </div>
            <div>
              <h6 className="mb-0 fw-bold text-white" style={{ fontSize: '0.95rem' }}>MMA Portal</h6>
              <span className="text-secondary small" style={{ fontSize: '0.72rem' }}>Manual Assistant</span>
            </div>
          </div>
          <button
            className="btn btn-sm text-secondary d-lg-none"
            onClick={onClose}
            aria-label="Close Sidebar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation links */}
        <div className="p-3 flex-grow-1 overflow-auto">
          <div className="text-uppercase text-secondary fw-bold px-2 mb-2" style={{ fontSize: '0.68rem', letterSpacing: '0.08em' }}>
            {normalizedRole ? `${normalizedRole.toUpperCase()} PORTAL` : 'MENU'}
          </div>
          <ul className="nav nav-pills flex-column gap-1">
            {navLinks.map((item) => {
              const Icon = item.icon;
              return (
                <li className="nav-item" key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/admin' || item.to === '/engineer' || item.to === '/supervisor'}
                    onClick={() => {
                      if (window.innerWidth < 992) onClose();
                    }}
                    className={({ isActive }) =>
                      `nav-link d-flex align-items-center gap-2 px-3 py-2 rounded-2 ${
                        isActive
                          ? 'active bg-primary text-white'
                          : 'text-light text-opacity-75 hover-bg-dark'
                      }`
                    }
                    style={({ isActive }) => ({
                      fontSize: '0.88rem',
                      fontWeight: isActive ? 600 : 400
                    })}
                  >
                    <Icon size={17} />
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-top border-secondary border-opacity-25 bg-black bg-opacity-20 text-secondary small">
          <div className="d-flex align-items-center justify-content-between mb-2">
            <span className="badge bg-secondary text-white" style={{ fontSize: '0.65rem' }}>v1.0.0</span>
            <span style={{ fontSize: '0.72rem' }}>Gemini RAG Architecture</span>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="btn btn-sm btn-outline-danger w-100 d-flex align-items-center justify-content-center gap-2"
            style={{ fontSize: '0.8rem' }}
          >
            <LogOut size={14} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>
    </>
  );
}
