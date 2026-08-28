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
      <header className="glass" style={{ position: 'sticky', top: 0, zIndex: 50, borderBottom: '1px solid var(--border)' }}>
        <div className="container flex items-center justify-between p-4">
          <div className="flex items-center gap-6">
            <h1 style={{ fontSize: '1.25rem', color: 'var(--primary)', margin: 0, textShadow: '0 2px 4px var(--primary-light)' }}>
              BDC Metrics
            </h1>
            <nav className="flex gap-4">
              {user?.is_teacher ? (
                <>
                  <Link to="/" className="flex items-center gap-2 hover-lift" style={{ color: 'var(--text-main)' }}>
                    <LayoutDashboard size={18} />
                    <span style={{ fontWeight: 500 }}>Mis Cursos</span>
                  </Link>
                  <Link to="/profile" className="flex items-center gap-2 hover-lift" style={{ color: 'var(--text-main)' }}>
                    <User size={18} />
                    <span style={{ fontWeight: 500 }}>Mi Perfil</span>
                  </Link>
                </>
              ) : (
                defaultCourse && user?.moodle_user_id && (
                  <Link to={`/course/${defaultCourse}/student/${user.moodle_user_id}`} className="flex items-center gap-2 hover-lift" style={{ color: 'var(--text-main)' }}>
                    <User size={18} />
                    <span style={{ fontWeight: 500 }}>Mi Perfil</span>
                  </Link>
                )
              )}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              {user?.sub} <span style={{opacity: 0.7}}>{user?.is_teacher ? '(Profesor)' : '(Alumno)'}</span>
            </div>
            <button onClick={handleLogout} className="btn-ghost flex items-center gap-2" style={{ padding: '0.4rem 0.8rem', fontSize: '0.9rem' }}>
              <LogOut size={16} />
              <span>Salir</span>
            </button>
          </div>
        </div>
      </header>

      <main className="animate-fade-in" style={{ flex: 1, padding: '2rem 0' }}>
        <Outlet />
      </main>
    </div>
  );
};
