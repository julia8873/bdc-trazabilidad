import React, { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import type { StudentMetrics, TimelineDetalladoResponse } from '../lib/api';
import { BookOpen, Activity, User, Bot, Search, ArrowDown, ArrowUp, Check } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export const StudentProfile: React.FC = () => {
  const { courseId, studentId } = useParams();

  const [metrics, setMetrics] = useState<StudentMetrics | null>(null);
  const [timeline, setTimeline] = useState<TimelineDetalladoResponse | null>(null);
  const [selectedConcepts, setSelectedConcepts] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
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
        const [mRes, iRes] = await Promise.all([
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}`),
          apiClient(`/v1/cursos/${courseId}/estudiantes/${studentId}/timeline_detallado?limit=20`)
        ]);

        if (mRes.status === 403) throw new Error('Acceso denegado a métricas del alumno');
        if (mRes.status === 503) throw new Error('Servicio de métricas no disponible');
        if (!mRes.ok) throw new Error('Error al cargar métricas del alumno');

        const mData = await mRes.json();
        const iData = await iRes.json();

        setMetrics(mData);
        setTimeline(iData);
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
  
  // Extraer frecuencias de conceptos del timeline
  const conceptCounts = (timeline?.items || []).reduce((acc, item) => {
    (item.conceptos || []).forEach(c => {
      acc[c] = (acc[c] || 0) + 1;
    });
    return acc;
  }, {} as Record<string, number>);
  
  const sortedConcepts = Object.entries(conceptCounts)
    .filter(([c]) => c.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => sortOrder === 'desc' ? b[1] - a[1] : a[1] - b[1]);

  // Filtrar timeline items por conceptos seleccionados
  const filteredTimelineItems = timeline?.items.filter(item => {
    if (selectedConcepts.size === 0) return true;
    if (!item.conceptos) return false;
    return item.conceptos.some(c => selectedConcepts.has(c));
  }) || [];
  
  const toggleConcept = (c: string) => {
    const nextSet = new Set(selectedConcepts);
    if (nextSet.has(c)) {
      nextSet.delete(c);
    } else {
      nextSet.add(c);
    }
    setSelectedConcepts(nextSet);
  };

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
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BookOpen size={20} color="var(--primary)" />
              <h3 style={{ margin: 0 }}>Conceptos Cubiertos (Frecuencia)</h3>
            </div>
          </div>
          
          <div className="flex gap-2 mb-4">
            <div style={{ position: 'relative', flex: 1 }}>
              <div style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
                <Search size={16} />
              </div>
              <input 
                type="text" 
                placeholder="Buscar conceptos..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.5rem 0.75rem 0.5rem 2.5rem', 
                  borderRadius: 'var(--radius)', 
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-main)',
                  color: 'var(--text-main)',
                  outline: 'none'
                }}
              />
            </div>
            <button 
              onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
              title={`Ordenar por frecuencia (${sortOrder === 'desc' ? 'descendente' : 'ascendente'})`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0 0.75rem',
                backgroundColor: 'var(--bg-main)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                cursor: 'pointer',
                color: 'var(--text-main)'
              }}
            >
              {sortOrder === 'desc' ? <ArrowDown size={18} /> : <ArrowUp size={18} />}
            </button>
          </div>

          {sortedConcepts.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {sortedConcepts.map(([c, count]) => {
                const isSelected = selectedConcepts.has(c);
                return (
                  <button 
                    key={c} 
                    onClick={() => toggleConcept(c)}
                    style={{ 
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      backgroundColor: isSelected ? 'var(--primary)' : 'var(--bg-main)', 
                      color: isSelected ? 'white' : 'var(--text-main)', 
                      border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border)'}`,
                      padding: '0.25rem 0.75rem', 
                      borderRadius: '1rem', 
                      fontSize: '0.875rem',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease-in-out'
                    }}
                  >
                    {isSelected && <Check size={14} />}
                    {c} <span style={{ opacity: 0.8, fontSize: '0.75rem' }}>({count})</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">
              <p>{searchQuery ? 'No se encontraron conceptos para esa búsqueda.' : 'Sin conceptos registrados en interacciones recientes.'}</p>
            </div>
          )}
        </div>
      </div>

      <div className="card mt-8">
        <h3 className="mb-4">
          Línea Temporal Detallada
          {selectedConcepts.size > 0 && <span style={{fontSize: '1rem', color: 'var(--text-muted)', fontWeight: 'normal', marginLeft: '0.5rem'}}>- Filtrado por {selectedConcepts.size} concepto{selectedConcepts.size !== 1 ? 's' : ''}</span>}
        </h3>
        {filteredTimelineItems.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {filteredTimelineItems.map((item, idx) => (
              <div key={idx} style={{ padding: '1.5rem', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div style={{ backgroundColor: 'var(--bg-main)', padding: '0.25rem 0.75rem', borderRadius: '4px', fontWeight: 500, fontSize: '0.875rem' }}>
                      {item.tipo_interaccion}
                    </div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{new Date(item.timestamp).toLocaleString()}</div>
                  </div>
                  {item.referencia_evento && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>Ref: {item.referencia_evento.substring(0, 7)}</div>}
                </div>
                
                {item.conceptos && item.conceptos.length > 0 && (
                  <div className="mb-4" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {item.conceptos.map(c => (
                        <span key={c} style={{ fontSize: '0.75rem', backgroundColor: 'var(--border)', padding: '2px 8px', borderRadius: '12px' }}>{c}</span>
                    ))}
                  </div>
                )}
                
                {(item.mensaje_alumno || item.respuesta_bot) ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {item.mensaje_alumno && (
                      <div style={{ display: 'flex', gap: '1rem' }}>
                        <div style={{ backgroundColor: 'var(--bg-main)', padding: '0.5rem', borderRadius: '50%', height: 'fit-content' }}>
                          <User size={16} />
                        </div>
                        <div style={{ backgroundColor: 'var(--bg-main)', padding: '1rem', borderRadius: '0 1rem 1rem 1rem', flex: 1, whiteSpace: 'pre-wrap' }}>
                          {item.mensaje_alumno}
                        </div>
                      </div>
                    )}
                    
                    {item.respuesta_bot && (
                      <div style={{ display: 'flex', gap: '1rem', flexDirection: 'row-reverse' }}>
                        <div style={{ backgroundColor: 'var(--primary)', color: 'white', padding: '0.5rem', borderRadius: '50%', height: 'fit-content' }}>
                          <Bot size={16} />
                        </div>
                        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: '1rem 0 1rem 1rem', flex: 1, whiteSpace: 'pre-wrap' }}>
                          {item.respuesta_bot}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.875rem' }}>Interacción sin contenido de chat visible o anterior a Fase 10.5</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No hay interacciones detalladas registradas para este alumno.</p>
        )}
      </div>
    </div>
  );
};
