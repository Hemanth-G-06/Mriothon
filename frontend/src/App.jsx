import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './hooks/useAuth';
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';
import LoginPage from './pages/auth/LoginPage';
import AdminDashboard from './pages/admin/AdminDashboard';
import UsersPage from './pages/admin/UsersPage';
import MachinesPage from './pages/admin/MachinesPage';
import DocumentsPage from './pages/admin/DocumentsPage';
import ProductsPage from './pages/admin/ProductsPage';
import EngineerDashboard from './pages/engineer/EngineerDashboard';
import QualityInspectionPage from './pages/engineer/QualityInspectionPage';
import BatchInspectionPage from './pages/engineer/BatchInspectionPage';
import InspectionHistoryPage from './pages/engineer/InspectionHistoryPage';
import SupervisorDashboard from './pages/supervisor/SupervisorDashboard';
import InspectionReviewPage from './pages/supervisor/InspectionReviewPage';
import NotFoundPage from './pages/common/NotFoundPage';
import UnauthorizedPage from './pages/common/UnauthorizedPage';
import ProtectedRoute from './components/auth/ProtectedRoute';
import LoadingSpinner from './components/common/LoadingSpinner';

// Dynamic root redirector
function RootRedirect() {
  const { user, role, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="d-flex justify-content-center align-items-center vh-100 bg-light">
        <LoadingSpinner text="Checking authentication status..." size="lg" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const normalizedRole = role ? role.toLowerCase() : null;
  if (normalizedRole === 'admin') return <Navigate to="/admin" replace />;
  if (normalizedRole === 'supervisor') return <Navigate to="/supervisor" replace />;
  if (normalizedRole === 'engineer') return <Navigate to="/engineer" replace />;
  return <Navigate to="/unauthorized" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          {/* Public Auth Routes */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
          </Route>

          {/* Root Redirect */}
          <Route path="/" element={<RootRedirect />} />

          {/* Protected Main Application Routes */}
          <Route element={<MainLayout />}>
            {/* Admin Routes */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AdminDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/users"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <UsersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/machines"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <MachinesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/products"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <ProductsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/products/:productId"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <ProductsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/documents"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <DocumentsPage />
                </ProtectedRoute>
              }
            />

            {/* Engineer Routes */}
            <Route
              path="/engineer"
              element={
                <ProtectedRoute allowedRoles={['engineer', 'admin']}>
                  <EngineerDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/engineer/quality-inspection"
              element={
                <ProtectedRoute allowedRoles={['engineer', 'admin']}>
                  <QualityInspectionPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/engineer/batch-inspection"
              element={
                <ProtectedRoute allowedRoles={['engineer', 'admin']}>
                  <BatchInspectionPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/engineer/inspection-history"
              element={
                <ProtectedRoute allowedRoles={['engineer', 'admin']}>
                  <InspectionHistoryPage />
                </ProtectedRoute>
              }
            />

            {/* Supervisor Routes */}
            <Route
              path="/supervisor"
              element={
                <ProtectedRoute allowedRoles={['supervisor', 'admin']}>
                  <SupervisorDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/supervisor/inspection-review"
              element={
                <ProtectedRoute allowedRoles={['supervisor', 'admin']}>
                  <InspectionReviewPage />
                </ProtectedRoute>
              }
            />

            {/* Common Status Pages */}
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
