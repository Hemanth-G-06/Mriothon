import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Cpu,
  FileText,
  MessageSquare,
  History,
  X,
  Wrench,
  Shield,
  HardHat,
  Package,
  Scan,
  Layers,
  ShieldCheck
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export default function Sidebar({ isOpen, onClose }) {
  const { role } = useAuth();

  const getNavLinks = () => {
    switch (role) {
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
            {role ? `${role.toUpperCase()} PORTAL` : 'MENU'}
          </div>
          <ul className="nav nav-pills flex-column gap-1">
            {navLinks.map((item) => {
              const Icon = item.icon;
              return (
                <li className="nav-item" key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/admin'}
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
          <div className="d-flex align-items-center gap-2">
            <span className="badge bg-secondary text-white" style={{ fontSize: '0.65rem' }}>v1.0.0</span>
            <span style={{ fontSize: '0.75rem' }}>Gemini RAG Architecture</span>
          </div>
        </div>
      </aside>
    </>
  );
}
