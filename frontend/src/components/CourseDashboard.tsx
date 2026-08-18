import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import type { CourseMetrics, PaginatedInteractions } from '../lib/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Users, BarChart3 } from 'lucide-react';

interface StudentCourseItem {
  moodle_user_id: number;
  moodle_username: string;
  repo_url: string | null;
  total_interactions: number;
  ultima_actividad: string | null;
  estado_sincronizacion: string;
}

export const CourseDashboard: React.FC = () => {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<CourseMetrics | null>(null);
  const [interactions, setInteractions] = useState<PaginatedInteractions | null>(null);
  const [students, setStudents] = useState<StudentCourseItem[]>([]);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(true);

  type SortField = 'name' | 'interactions' | 'activity' | 'status';
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setLoading(true);
        const [mRes, iRes, sRes] = await Promise.all([
          apiClient(`/v1/metrics/course/${courseId}`),
          apiClient(`/v1/metrics/course/${courseId}/interactions?limit=5`),
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes`)
        ]);

        if (mRes.status === 403) throw new Error('Acceso denegado a métricas del curso');
        if (mRes.status === 503) throw new Error('Servicio de métricas no disponible');
        if (!mRes.ok) throw new Error('Error al cargar métricas');

        const mData = await mRes.json();
        const iData = await iRes.json();
        let sData = { students: [] };
        if (sRes.ok) {
          sData = await sRes.json();
        }
        
        setMetrics(mData);
        setInteractions(iData);
        setStudents(sData.students || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    if (courseId) fetchDashboard();
  }, [courseId]);

  if (loading) return <div className="container mt-8" style={{ textAlign: 'center' }}>Cargando dashboard...</div>;
  if (error) return <div className="container mt-8"><div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div></div>;
  if (!metrics) return null;

  const chartData = Object.entries(metrics.interactions_by_type).map(([name, value]) => ({ name, value }));

  const COURSE_NAMES: Record<number, string> = {
    3: 'Ecuaciones Diferenciales II'
  };

  const sortedStudents = [...students].sort((a, b) => {
    let comparison = 0;
    switch (sortField) {
      case 'name':
        comparison = a.moodle_username.localeCompare(b.moodle_username);
        break;
      case 'interactions':
        comparison = a.total_interactions - b.total_interactions;
        break;
      case 'activity':
        const dateA = a.ultima_actividad ? new Date(a.ultima_actividad).getTime() : 0;
        const dateB = b.ultima_actividad ? new Date(b.ultima_actividad).getTime() : 0;
        comparison = dateA - dateB;
        break;
      case 'status':
        comparison = a.estado_sincronizacion.localeCompare(b.estado_sincronizacion);
        break;
    }
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  return (
    <div className="container">
      <div className="mb-8 flex justify-between items-center">
        <h2>Dashboard de {COURSE_NAMES[Number(courseId)] || `Curso ${courseId}`}</h2>
        <button onClick={() => navigate('/')} className="button" style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-main)' }}>
          Volver a Mis Cursos
        </button>
      </div>

      <div className="grid grid-cols-3 mb-8">
        <div className="card flex items-center gap-4">
          <div style={{ padding: '1rem', backgroundColor: '#e0f2fe', color: 'var(--primary)', borderRadius: '50%' }}>
            <Activity size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Total Interacciones</p>
            <h3>{metrics.total_interactions}</h3>
          </div>
        </div>
        <div className="card flex items-center gap-4">
          <div style={{ padding: '1rem', backgroundColor: '#e0f2fe', color: 'var(--primary)', borderRadius: '50%' }}>
            <Users size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Alumnos que han interactuado</p>
            <h3>{metrics.percentiles.unique_users || 0}</h3>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2">
        <div className="card">
          <h3 className="mb-4">Interacciones por Tipo</h3>
          {chartData.length > 0 ? (
            <div style={{ height: '300px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} />
                  <Tooltip cursor={{ fill: 'var(--bg-main)' }} contentStyle={{ borderRadius: 'var(--radius)', border: '1px solid var(--border)' }} />
                  <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
             <div className="empty-state">No hay interacciones registradas en este curso.</div>
          )}
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} color="var(--text-muted)" />
            <h3 style={{ margin: 0 }}>Percentiles de Interacción</h3>
          </div>
          
          {metrics.percentiles.unique_users < 5 ? (
            <div className="empty-state" style={{ padding: '2rem 1rem' }}>
              <p>Datos insuficientes para el cálculo de percentiles.</p>
              <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>Se requieren al menos 5 alumnos interactuando.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex justify-between items-center" style={{ padding: '0.75rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                <span style={{ fontWeight: 500 }}>Percentil 90 (Top 10%)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--primary)' }}>{metrics.percentiles.p90}</span>
              </div>
              <div className="flex justify-between items-center" style={{ padding: '0.75rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                <span style={{ fontWeight: 500 }}>Percentil 75 (Cuartil Superior)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>{metrics.percentiles.p75}</span>
              </div>
              <div className="flex justify-between items-center" style={{ padding: '0.75rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                <span style={{ fontWeight: 500 }}>Percentil 50 (Mediana)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>{metrics.percentiles.p50}</span>
              </div>
              <div className="flex justify-between items-center" style={{ padding: '0.75rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                <span style={{ fontWeight: 500 }}>Percentil 25 (Cuartil Inferior)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-muted)' }}>{metrics.percentiles.p25}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card mt-8">
        <h3 className="mb-4">Últimas Interacciones</h3>
        {interactions && interactions.items.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Alumno ID</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Tipo</th>
                </tr>
              </thead>
              <tbody>
                {interactions.items.map(item => (
                  <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.75rem' }}>{new Date(item.timestamp).toLocaleString()}</td>
                    <td style={{ padding: '0.75rem' }}>{item.moodle_user_id}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <span style={{ backgroundColor: 'var(--bg-main)', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.875rem' }}>
                        {item.tipo_interaccion}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No hay interacciones recientes.</p>
        )}
      </div>
      <div className="card mt-8">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: 0 }}>Alumnos Matriculados</h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Ordenar por:</span>
            <select 
              value={sortField} 
              onChange={(e) => setSortField(e.target.value as SortField)}
              style={{ padding: '0.25rem 0.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', background: 'var(--bg-main)', color: 'var(--text-main)' }}
            >
              <option value="name">Nombre</option>
              <option value="interactions">Nº interacciones</option>
              <option value="activity">Última actividad</option>
              <option value="status">Estado de sincronización</option>
            </select>
            <button 
              onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              style={{ padding: '0.25rem 0.75rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', background: 'var(--bg-main)', color: 'var(--text-main)', cursor: 'pointer' }}
            >
              {sortDirection === 'asc' ? '↑ Asc' : '↓ Desc'}
            </button>
          </div>
        </div>
        
        {students && students.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Alumno</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Enlace al repo</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Nº interacciones</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Última actividad</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Estado de sincronización</th>
                </tr>
              </thead>
              <tbody>
                {sortedStudents.map(student => (
                  <tr key={student.moodle_user_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.75rem' }}>
                      <Link to={`/course/${courseId}/student/${student.moodle_user_id}`} state={{ studentName: student.moodle_username }} style={{ color: 'var(--primary)', textDecoration: 'none', fontWeight: 500 }}>
                        {student.moodle_username}
                      </Link>
                    </td>
                    <td style={{ padding: '0.75rem' }}>
                      {student.repo_url ? (
                        <a href={student.repo_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)', textDecoration: 'none' }}>
                          Ver en GitHub
                        </a>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Pendiente</span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem' }}>{student.total_interactions}</td>
                    <td style={{ padding: '0.75rem' }}>
                      {student.ultima_actividad ? new Date(student.ultima_actividad).toLocaleString() : '-'}
                    </td>
                    <td style={{ padding: '0.75rem' }}>
                      {student.estado_sincronizacion === "OK" ? (
                        <span style={{ backgroundColor: '#dcfce7', color: '#166534', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.875rem' }}>OK</span>
                      ) : (
                        <span style={{ backgroundColor: '#fef3c7', color: '#92400e', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.875rem' }}>Con discrepancias pendientes</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No hay alumnos matriculados o sincronizados todavía.</p>
        )}
      </div>
    </div>
  );
};
