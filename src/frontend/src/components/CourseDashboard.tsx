import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import type { CourseMetrics, PaginatedInteractions } from '../lib/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Users, BarChart3, RefreshCw, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { RubricEditor } from './RubricEditor';

interface StudentCourseItem {
  moodle_user_id: number;
  moodle_username: string;
  repo_url: string | null;
  total_interactions: number;
  ultima_actividad: string | null;
  estado_sincronizacion: string;
}

interface Discrepancia {
  id: number;
  moodle_user_id: number;
  commit_sha: string;
  tipo_discrepancia: string;
  detalles: any;
  timestamp: string;
  resuelta: boolean;
  resuelta_at: string | null;
  resuelta_por: number | null;
  commit_log_ref: string | null;
}

export const CourseDashboard: React.FC = () => {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<CourseMetrics | null>(null);
  const [interactions, setInteractions] = useState<PaginatedInteractions | null>(null);
  const [students, setStudents] = useState<StudentCourseItem[]>([]);
  const [discrepancias, setDiscrepancias] = useState<Discrepancia[]>([]);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(true);

  // ── Sync state ──────────────────────────────────────────────────────────────
  const [syncingAll, setSyncingAll] = useState(false);
  const [syncingStudentId, setSyncingStudentId] = useState<number | null>(null);
  const [syncResult, setSyncResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  type SortField = 'name' | 'interactions' | 'activity' | 'status';
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const fetchStudents = useCallback(async () => {
    if (!courseId) return;
    const sRes = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes`);
    if (sRes.ok) {
      const sData = await sRes.json();
      setStudents(sData.students || []);
    }
    
    const dRes = await apiClient(`/v1/metrics/cursos/${courseId}/discrepancias`);
    if (dRes.ok) {
      const dData = await dRes.json();
      setDiscrepancias(dData.discrepancias || []);
    }
  }, [courseId]);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setLoading(true);
        const [mRes, iRes, sRes, dRes] = await Promise.all([
          apiClient(`/v1/metrics/cursos/${courseId}`),
          apiClient(`/v1/metrics/cursos/${courseId}/interacciones?limit=5`),
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes`),
          apiClient(`/v1/metrics/cursos/${courseId}/discrepancias`)
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
        let dData = { discrepancias: [] };
        if (dRes.ok) {
          dData = await dRes.json();
        }
        
        setMetrics(mData);
        setInteractions(iData);
        setStudents(sData.students || []);
        setDiscrepancias(dData.discrepancias || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    if (courseId) fetchDashboard();
  }, [courseId]);

  // ── Sync handlers ────────────────────────────────────────────────────────────
  const handleSyncAll = async () => {
    if (!courseId || syncingAll) return;
    setSyncingAll(true);
    setSyncResult(null);
    try {
      const res = await apiClient(`/v1/metrics/cursos/${courseId}/sync`, { method: 'POST' });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setSyncResult({
        type: 'success',
        message: `Sincronización completada: ${data.students_processed} alumno(s) procesado(s), ${data.commits_checked} commits revisados.`
      });
      await fetchStudents();
    } catch (e: any) {
      setSyncResult({ type: 'error', message: `Error al sincronizar: ${e.message}` });
    } finally {
      setSyncingAll(false);
      setTimeout(() => setSyncResult(null), 6000);
    }
  };

  const handleSyncStudent = async (studentId: number) => {
    if (!courseId || syncingStudentId !== null) return;
    setSyncingStudentId(studentId);
    setSyncResult(null);
    try {
      const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/sync`, { method: 'POST' });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setSyncResult({
        type: 'success',
        message: `Alumno sincronizado: ${data.commits_checked ?? data.synced ?? 0} commits revisados.`
      });
      await fetchStudents();
    } catch (e: any) {
      setSyncResult({ type: 'error', message: `Error al sincronizar alumno: ${e.message}` });
    } finally {
      setSyncingStudentId(null);
      setTimeout(() => setSyncResult(null), 6000);
    }
  };

  const unsyncedCount = students.filter(s => s.estado_sincronizacion !== 'OK').length;

  if (loading) return <div className="container mt-8" style={{ textAlign: 'center' }}>Cargando dashboard...</div>;
  if (error) return <div className="container mt-8"><div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div></div>;
  if (!metrics) return null;

  const chartData = Object.entries(metrics.interactions_by_type).map(([name, value]) => ({ name, value }));

  const COURSE_NAMES: Record<number, string> = {
    3: 'Ecuaciones Diferenciales II',
    8: 'UGRinfo Oficial',
    9: 'NBT Oficial'
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
    <div className="container animate-slide-up">
      <div className="mb-8 flex justify-between items-center">
        <h2>Dashboard de {COURSE_NAMES[Number(courseId)] || `Curso ${courseId}`}</h2>
        <button onClick={() => navigate('/')} className="btn-ghost" style={{ backgroundColor: 'var(--bg-card)' }}>
          Volver a Mis Cursos
        </button>
      </div>

      <div className="grid grid-cols-3 mb-8">
        <div className="card hover-lift flex items-center gap-4">
          <div style={{ padding: '1rem', backgroundColor: 'var(--primary-light)', color: 'var(--primary)', borderRadius: 'var(--radius)' }}>
            <Activity size={28} />
          </div>
          <div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', fontWeight: 500 }}>Total Interacciones</p>
            <h3 style={{ fontSize: '1.75rem', marginTop: '0.25rem' }}>{metrics.total_interactions}</h3>
          </div>
        </div>
        <div className="card hover-lift flex items-center gap-4">
          <div style={{ padding: '1rem', backgroundColor: 'var(--success-light)', color: 'var(--success)', borderRadius: 'var(--radius)' }}>
            <Users size={28} />
          </div>
          <div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', fontWeight: 500 }}>Alumnos activos</p>
            <h3 style={{ fontSize: '1.75rem', marginTop: '0.25rem' }}>{metrics.percentiles.unique_users || 0}</h3>
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

        <div className="card hover-lift">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Percentiles de Interacción</h3>
          </div>
          
          {metrics.percentiles.unique_users < 5 ? (
            <div className="empty-state" style={{ padding: '2rem 1rem' }}>
              <p>Datos insuficientes para percentiles.</p>
              <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>Se requieren al menos 5 alumnos activos.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex justify-between items-center" style={{ padding: '0.8rem 1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontWeight: 500 }}>Top 10% (p90)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--primary)' }}>{metrics.percentiles.p90}</span>
              </div>
              <div className="flex justify-between items-center" style={{ padding: '0.8rem 1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontWeight: 500 }}>Cuartil Superior (p75)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>{metrics.percentiles.p75}</span>
              </div>
              <div className="flex justify-between items-center" style={{ padding: '0.8rem 1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontWeight: 500 }}>Mediana (p50)</span>
                <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>{metrics.percentiles.p50}</span>
              </div>
              <div className="flex justify-between items-center" style={{ padding: '0.8rem 1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontWeight: 500 }}>Cuartil Inferior (p25)</span>
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h3 style={{ margin: 0 }}>Alumnos Matriculados</h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Ordenar por:</span>
            <select 
              value={sortField} 
              onChange={(e) => setSortField(e.target.value as SortField)}
              style={{ padding: '0.4rem 0.6rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--bg-main)', color: 'var(--text-main)' }}
            >
              <option value="name">Nombre</option>
              <option value="interactions">Nº interacciones</option>
              <option value="activity">Última actividad</option>
              <option value="status">Estado de sincronización</option>
            </select>
            <button 
              className="btn-ghost"
              onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              style={{ padding: '0.4rem 0.8rem', border: '1px solid var(--border)' }}
            >
              {sortDirection === 'asc' ? '↑ Asc' : '↓ Desc'}
            </button>

            {/* ── Sync All Button ─────────────────────────────────────── */}
            {unsyncedCount > 0 && (
              <button
                id="btn-sync-all-students"
                className="btn-primary"
                onClick={handleSyncAll}
                disabled={syncingAll || syncingStudentId !== null}
                title={`Sincronizar los ${unsyncedCount} alumno(s) con discrepancias pendientes`}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', padding: '0.45rem 0.9rem' }}
              >
                {syncingAll
                  ? <><Loader2 size={14} className="animate-spin" /> Sincronizando...</>
                  : <><RefreshCw size={14} /> Sincronizar todo ({unsyncedCount})</>}
              </button>
            )}
          </div>
        </div>

        {/* ── Sync feedback banner ──────────────────────────────────────────── */}
        {syncResult && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.6rem 1rem', borderRadius: 'var(--radius-sm)', marginBottom: '1rem',
            backgroundColor: syncResult.type === 'success' ? 'var(--success-light, #dcfce7)' : 'var(--danger-light, #fee2e2)',
            color: syncResult.type === 'success' ? 'var(--success, #166534)' : 'var(--danger, #991b1b)',
            fontSize: '0.875rem',
          }}>
            {syncResult.type === 'success'
              ? <CheckCircle2 size={16} />
              : <AlertTriangle size={16} />}
            {syncResult.message}
          </div>
        )}
        
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
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Acción</th>
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
                    <td style={{ padding: '0.75rem' }}>
                      {student.estado_sincronizacion !== 'OK' ? (
                        <button
                          id={`btn-sync-student-${student.moodle_user_id}`}
                          onClick={() => handleSyncStudent(student.moodle_user_id)}
                          disabled={syncingStudentId === student.moodle_user_id || syncingAll}
                          title="Sincronizar este alumno con GitHub"
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                            padding: '0.3rem 0.7rem', fontSize: '0.8rem', cursor: 'pointer',
                            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                            backgroundColor: 'var(--bg-main)', color: 'var(--text-muted)',
                            transition: 'all 0.15s ease',
                            opacity: syncingStudentId !== null && syncingStudentId !== student.moodle_user_id ? 0.5 : 1,
                          }}
                        >
                          {syncingStudentId === student.moodle_user_id
                            ? <><Loader2 size={13} className="animate-spin" /> Sincronizando...</>
                            : <><RefreshCw size={13} /> Sincronizar</>}
                        </button>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>—</span>
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
      <div className="card mt-8">
        <h3 className="mb-4">Historial de Discrepancias</h3>
        {discrepancias && discrepancias.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Alumno ID</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Tipo</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Estado</th>
                  <th style={{ padding: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>Log Commit</th>
                </tr>
              </thead>
              <tbody>
                {discrepancias.map(d => {
                  const student = students.find(s => s.moodle_user_id === d.moodle_user_id);
                  let commitUrl = null;
                  if (d.commit_log_ref && student?.repo_url) {
                    const repoBase = student.repo_url.replace('.git', '');
                    commitUrl = `${repoBase}/commit/${d.commit_log_ref}`;
                  }
                  
                  return (
                    <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.75rem' }}>{new Date(d.timestamp).toLocaleString()}</td>
                      <td style={{ padding: '0.75rem' }}>
                        <Link to={`/course/${courseId}/student/${d.moodle_user_id}`} style={{ color: 'var(--primary)', textDecoration: 'none' }}>
                          {student?.moodle_username || d.moodle_user_id}
                        </Link>
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        <span style={{ backgroundColor: 'var(--bg-main)', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.875rem' }}>
                          {d.tipo_discrepancia}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        {d.resuelta ? (
                          <span style={{ backgroundColor: '#dcfce7', color: '#166534', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.875rem' }}>
                            Resuelta el {new Date(d.resuelta_at!).toLocaleDateString()}
                          </span>
                        ) : (
                          <span style={{ backgroundColor: '#fef3c7', color: '#92400e', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.875rem' }}>
                            Pendiente
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        {commitUrl ? (
                          <a href={commitUrl} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)', textDecoration: 'none' }}>
                            Ver Auditoría
                          </a>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No hay historial de discrepancias.</p>
        )}
      </div>
      </div>
      
      {/* ── Editor de Rúbrica ────────────────────────────────────────────── */}
      <RubricEditor courseId={courseId!} />
    </div>
  );
};
