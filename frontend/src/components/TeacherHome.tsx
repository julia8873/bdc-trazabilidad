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
    <div className="container animate-slide-up">
      <div className="mb-8">
        <h2>Mis Cursos</h2>
        <p style={{ color: 'var(--text-muted)' }}>Selecciona un curso para ver el dashboard y los alumnos matriculados.</p>
      </div>

      <div className="grid grid-cols-3">
        {user.allowed_courses.map(courseId => (
          <Link key={courseId} to={`/course/${courseId}`} style={{ textDecoration: 'none' }}>
            <div className="card hover-lift flex items-center gap-4">
              <div style={{ padding: '1.25rem', backgroundColor: 'var(--primary-light)', color: 'var(--primary)', borderRadius: 'var(--radius)' }}>
                <BookOpen size={28} />
              </div>
              <div>
                <h3 style={{ margin: 0, color: 'var(--text-main)', fontSize: '1.1rem' }}>{COURSE_NAMES[courseId] || `Curso ${courseId}`}</h3>
                <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>Ver Dashboard &rarr;</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};
