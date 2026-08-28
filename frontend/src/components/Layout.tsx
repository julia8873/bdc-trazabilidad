import React from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogOut, LayoutDashboard, User } from 'lucide-react';

export const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const defaultCourse = user?.allowed_courses?.[0];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{ backgroundColor: 'var(--bg-card)', borderBottom: '1px solid var(--border)', padding: '1rem 0' }}>
        <div className="container flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 style={{ fontSize: '1.25rem', color: 'var(--primary)', margin: 0 }}>BDC Metrics</h1>
            <nav className="flex gap-4" style={{ marginLeft: '2rem' }}>
              {user?.is_teacher ? (
                <>
                  <Link to="/" className="flex items-center gap-2" style={{ color: 'var(--text-main)' }}>
                    <LayoutDashboard size={18} />
                    <span>Mis Cursos</span>
                  </Link>
                  <Link to="/profile" className="flex items-center gap-2" style={{ color: 'var(--text-main)' }}>
                    <User size={18} />
                    <span>Mi Perfil</span>
                  </Link>
                </>
              ) : (
                defaultCourse && user?.moodle_user_id && (
                  <Link to={`/course/${defaultCourse}/student/${user.moodle_user_id}`} className="flex items-center gap-2" style={{ color: 'var(--text-main)' }}>
                    <User size={18} />
                    <span>Mi Perfil</span>
                  </Link>
                )
              )}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              {user?.sub} {user?.is_teacher ? '(Profesor)' : '(Alumno)'}
            </div>
            <button onClick={handleLogout} className="btn-danger flex items-center gap-2" style={{ padding: '0.25rem 0.75rem', fontSize: '0.875rem' }}>
              <LogOut size={16} />
              <span>Salir</span>
            </button>
          </div>
        </div>
      </header>

      <main style={{ flex: 1, padding: '2rem 0' }}>
        <Outlet />
      </main>
    </div>
  );
};
