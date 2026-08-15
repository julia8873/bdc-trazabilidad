import React, { useEffect } from 'react';
import { useLocation, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const AuthGuard: React.FC = () => {
  const { token } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (!token) {
      // Save only the path to sessionStorage as requested by user
      // No state or sensitive data
      sessionStorage.setItem('returnPath', location.pathname);
    }
  }, [token, location]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};

export const RoleGuard: React.FC<{ requireTeacher?: boolean }> = ({ requireTeacher }) => {
  const { user } = useAuth();
  
  if (requireTeacher && !user?.is_teacher) {
    return (
      <div className="container mt-8">
        <div className="card" style={{ borderColor: 'var(--danger)', textAlign: 'center' }}>
          <h2 style={{ color: 'var(--danger)' }}>Acceso Denegado</h2>
          <p className="mt-4">No tienes permisos para ver esta página.</p>
        </div>
      </div>
    );
  }

  return <Outlet />;
};
