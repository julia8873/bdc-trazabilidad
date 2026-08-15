import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

export const TeacherHome: React.FC = () => {
  const { user } = useAuth();

  if (!user || !user.is_teacher) {
    return <div>Acceso denegado</div>;
  }

  const COURSE_NAMES: Record<number, string> = {
    3: 'Ecuaciones Diferenciales II'
  };

  return (
    <div className="container">
      <div className="mb-8">
        <h2>Mis Cursos</h2>
        <p style={{ color: 'var(--text-muted)' }}>Selecciona un curso para ver el dashboard y los alumnos matriculados.</p>
      </div>

      <div className="grid grid-cols-3">
        {user.allowed_courses.map(courseId => (
          <Link key={courseId} to={`/course/${courseId}`} style={{ textDecoration: 'none' }}>
            <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '1rem', cursor: 'pointer', transition: 'transform 0.2s' }}>
              <div style={{ padding: '1rem', backgroundColor: '#e0f2fe', color: 'var(--primary)', borderRadius: '50%' }}>
                <BookOpen size={24} />
              </div>
              <div>
                <h3 style={{ margin: 0, color: 'var(--text-main)' }}>{COURSE_NAMES[courseId] || `Curso ${courseId}`}</h3>
                <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875rem' }}>Ver Dashboard</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};
