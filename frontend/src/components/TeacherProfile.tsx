import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import { User, BookOpen, Mail, ShieldCheck } from 'lucide-react';

export const TeacherProfile: React.FC = () => {
  const { user } = useAuth();

  if (!user) return null;

  const COURSE_NAMES: Record<number, string> = {
    3: 'Ecuaciones Diferenciales II'
  };

  return (
    <div className="container">
      <div className="mb-8">
        <h2>Perfil del Profesor</h2>
        <p style={{ color: 'var(--text-muted)' }}>Tus datos y asignaciones en BDC Metrics.</p>
      </div>

      <div className="grid grid-cols-2 gap-8">
        <div className="card">
          <div className="flex items-center gap-4 mb-6">
            <div style={{ padding: '1.5rem', backgroundColor: '#f0fdf4', color: '#166534', borderRadius: '50%' }}>
              <User size={32} />
            </div>
            <div>
              <h3 style={{ margin: 0, color: 'var(--text-main)', fontSize: '1.5rem' }}>{user.sub}</h3>
              <p style={{ margin: 0, color: 'var(--text-muted)' }}>Moodle ID: {user.moodle_user_id}</p>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Mail color="var(--text-muted)" size={20} />
              <span style={{ color: 'var(--text-main)' }}>No disponible (API mock)</span>
            </div>
            <div className="flex items-center gap-3">
              <ShieldCheck color="var(--primary)" size={20} />
              <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>Rol: Profesor (Acceso Total)</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="mb-4 flex items-center gap-2">
            <BookOpen size={20} color="var(--primary)" />
            Cursos Asignados
          </h3>
          
          <div className="flex flex-col gap-3">
            {user.allowed_courses.map(courseId => (
              <div key={courseId} className="flex justify-between items-center" style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                <div>
                  <h4 style={{ margin: '0 0 0.25rem 0', color: 'var(--text-main)' }}>
                    {COURSE_NAMES[courseId] || `Curso ${courseId}`}
                  </h4>
                  <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                    ID Moodle: {courseId}
                  </p>
                </div>
                <Link to={`/course/${courseId}`} className="button" style={{ backgroundColor: 'var(--primary)', color: 'white', textDecoration: 'none', padding: '0.5rem 1rem' }}>
                  Ir al Dashboard
                </Link>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
