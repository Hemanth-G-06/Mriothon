import React from 'react';
import { Outlet } from 'react-router-dom';

export default function AuthLayout() {
  return (
    <div className="min-vh-100 d-flex flex-column justify-content-center align-items-center bg-light p-3">
      <div className="w-100" style={{ maxWidth: '480px' }}>
        <Outlet />
      </div>
    </div>
  );
}
