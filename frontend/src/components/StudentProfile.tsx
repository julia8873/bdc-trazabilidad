import React, { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { API_URL } from '../lib/api';
import type { StudentMetrics, PaginatedInteractions } from '../lib/api';
import { BookOpen, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export const StudentProfile: React.FC = () => {
  const { courseId, studentId } = useParams();
  
  const [metrics, setMetrics] = useState<StudentMetrics | null>(null);
  const [interactions, setInteractions] = useState<PaginatedInteractions | null>(null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const location = useLocation();
  const studentName = location.state?.studentName || `Alumno ${studentId}`;

  const COURSE_NAMES: Record<string, string> = {
    '3': 'Ecuaciones Diferenciales II'
  };
  const courseName = courseId ? COURSE_NAMES[courseId] || `Curso ${courseId}` : `Curso ${courseId}`;

  useEffect(() => {
    const fetchStudentData = async () => {
      try {
        setLoading(true);
        const headers = { Authorization: `Bearer ${localStorage.getItem('token')}` };
        const [mRes, iRes] = await Promise.all([
          fetch(`${API_URL}/metrics/course/${courseId}/student/${studentId}`, { headers }),
          fetch(`${API_URL}/metrics/course/${courseId}/student/${studentId}/interactions?limit=10`, { headers })
        ]);

        if (mRes.status === 403) throw new Error('Acceso denegado a métricas del alumno');
        if (mRes.status === 503) throw new Error('Servicio de métricas no disponible');
        if (!mRes.ok) throw new Error('Error al cargar métricas del alumno');

        const mData = await mRes.json();
        const iData = await iRes.json();
        
        setMetrics(mData);
        setInteractions(iData);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    if (courseId && studentId) fetchStudentData();
  }, [courseId, studentId]);

  if (loading) return <div className="container mt-8" style={{ textAlign: 'center' }}>Cargando perfil del alumno...</div>;
  if (error) return <div className="container mt-8"><div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div></div>;
  if (!metrics) return null;

  const chartData = Object.entries(metrics.interactions_by_type).map(([name, value]) => ({ name, value }));

  return (
    <div className="container">
      <div className="flex items-center justify-between mb-8">
        <h2>Perfil de {studentName} ({courseName})</h2>
      </div>

      <div className="grid grid-cols-2 mb-8">
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Métricas Individuales</h3>
          </div>
          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
            <p style={{ color: 'var(--text-muted)' }}>Total Interacciones</p>
            <h2>{metrics.total_interactions}</h2>
          </div>
          
          <div className="mt-4" style={{ height: '200px' }}>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} />
                  <Tooltip cursor={{ fill: 'var(--bg-main)' }} contentStyle={{ borderRadius: 'var(--radius)' }} />
                  <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: '2rem' }}>Sin interacciones</p>
            )}
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Conceptos Cubiertos</h3>
          </div>
          <div className="empty-state">
            <p>Sin conceptos registrados para este curso todavía.</p>
            <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>El catálogo de conceptos estará disponible en futuras actualizaciones (Fase 3).</p>
          </div>
        </div>
      </div>

      <div className="card mt-8">
        <h3 className="mb-4">Línea Temporal de Interacciones</h3>
        {interactions && interactions.items.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {interactions.items.map(item => (
              <div key={item.id} className="flex items-center justify-between" style={{ padding: '1rem', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                <div className="flex items-center gap-4">
                  <div style={{ backgroundColor: 'var(--bg-main)', padding: '0.5rem 1rem', borderRadius: '4px', fontWeight: 500 }}>
                    {item.tipo_interaccion}
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{new Date(item.timestamp).toLocaleString()}</div>
                    {item.referencia_evento && <div style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>Ref: {item.referencia_evento}</div>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No hay interacciones registradas para este alumno.</p>
        )}
      </div>
    </div>
  );
};
