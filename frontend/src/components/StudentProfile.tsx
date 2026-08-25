import React, { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import type { StudentMetrics, TimelineDetalladoResponse, AgentSummaryResponse, AgentFollowUpMessage } from '../lib/api';
import { BookOpen, Activity, User, Bot, Search, ArrowDown, ArrowUp, Check, Brain, Send, AlertTriangle, Lightbulb } from 'lucide-react';
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

  // Estados del Agente Evaluador
  const [agentSummary, setAgentSummary] = useState<AgentSummaryResponse | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState<string>('');
  const [agentChat, setAgentChat] = useState<AgentFollowUpMessage[]>([]);
  const [agentInput, setAgentInput] = useState('');
  const [agentChatLoading, setAgentChatLoading] = useState(false);

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

  const generateEvaluation = async () => {
    try {
      setAgentLoading(true);
      setAgentError('');
      const res = await apiClient(`/v1/cursos/${courseId}/estudiantes/${studentId}/resumen`, {
        method: 'POST'
      });
      if (res.status === 503) throw new Error('El Agente Evaluador no está habilitado en este entorno.');
      if (res.status === 403) throw new Error('No tienes permisos para evaluar a este alumno.');
      if (!res.ok) throw new Error('Error al generar la evaluación del agente.');
      
      const data = await res.json();
      setAgentSummary(data);
      setAgentChat([]); // Reset chat when generating new summary
    } catch (err: any) {
      setAgentError(err.message);
    } finally {
      setAgentLoading(false);
    }
  };

  const sendFollowUpMessage = async () => {
    if (!agentInput.trim() || !agentSummary?.resumen_hash) return;
    
    const newMessage: AgentFollowUpMessage = { rol: 'user', contenido: agentInput };
    const currentChat = [...agentChat, newMessage];
    setAgentChat(currentChat);
    setAgentInput('');
    setAgentChatLoading(true);

    try {
      const res = await apiClient(`/v1/cursos/${courseId}/estudiantes/${studentId}/resumen/seguimiento`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mensaje: newMessage.contenido,
          historial: agentChat,
          resumen_hash: agentSummary.resumen_hash
        })
      });
      if (!res.ok) throw new Error('Error al enviar mensaje de seguimiento.');
      const data = await res.json();
      setAgentChat(data.historial_actualizado);
    } catch (err: any) {
      setAgentError('Fallo en el chat de seguimiento: ' + err.message);
    } finally {
      setAgentChatLoading(false);
    }
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

      <div className="card mt-8 mb-8" style={{ border: '2px solid var(--primary)', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', backgroundColor: 'var(--primary)' }}></div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain size={24} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Evaluación Automática (LLM-as-a-Judge)</h3>
          </div>
          {!agentSummary && (
            <button 
              onClick={generateEvaluation}
              disabled={agentLoading}
              className="btn"
              style={{ backgroundColor: 'var(--primary)', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: 'var(--radius)', cursor: agentLoading ? 'not-allowed' : 'pointer', opacity: agentLoading ? 0.7 : 1 }}
            >
              {agentLoading ? 'Evaluando...' : 'Solicitar Evaluación a la IA'}
            </button>
          )}
        </div>

        {agentError && <div style={{ color: 'var(--danger)', marginBottom: '1rem', padding: '1rem', backgroundColor: 'rgba(255,0,0,0.1)', borderRadius: 'var(--radius)' }}>{agentError}</div>}

        {agentSummary && agentSummary.estado === "evaluado" && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            <div className="grid grid-cols-2 gap-4">
              <div style={{ backgroundColor: 'var(--bg-main)', padding: '1rem', borderRadius: 'var(--radius)' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0, color: 'var(--primary)' }}><Lightbulb size={18} /> Fortalezas</h4>
                <ul style={{ paddingLeft: '1.2rem', margin: 0, fontSize: '0.9rem' }}>
                  {agentSummary.fortalezas.map((f, i) => <li key={i} style={{ marginBottom: '0.5rem' }}>{f}</li>)}
                </ul>
              </div>
              <div style={{ backgroundColor: 'var(--bg-main)', padding: '1rem', borderRadius: 'var(--radius)' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0, color: '#f59e0b' }}><AlertTriangle size={18} /> Señales de Alerta</h4>
                <ul style={{ paddingLeft: '1.2rem', margin: 0, fontSize: '0.9rem' }}>
                  {agentSummary.senales_alerta.length > 0 ? agentSummary.senales_alerta.map((s, i) => <li key={i} style={{ marginBottom: '0.5rem' }}>{s}</li>) : <li style={{ color: 'var(--text-muted)' }}>No se detectaron alertas críticas.</li>}
                </ul>
              </div>
            </div>

            <div>
              <h4 style={{ marginTop: 0 }}>Criterios de Evaluación</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.5rem' }}>
                {agentSummary.criterios.map((c, i) => (
                  <div key={i} style={{ padding: '0.75rem', border: '1px solid var(--border)', borderRadius: 'var(--radius)', backgroundColor: 'var(--bg-main)' }}>
                    <strong>{c.nombre}</strong>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>{c.observacion}</p>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1.5rem', marginTop: '0.5rem' }}>
              <h4 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Bot size={18} /> Chat de Seguimiento</h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>Puedes conversar con el agente evaluador sobre este reporte.</p>
              
              {agentChat.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1rem', maxHeight: '300px', overflowY: 'auto', padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                  {agentChat.map((msg, i) => (
                    <div key={i} style={{ display: 'flex', gap: '1rem', flexDirection: msg.rol === 'user' ? 'row' : 'row-reverse' }}>
                      <div style={{ backgroundColor: msg.rol === 'user' ? 'var(--bg-main)' : 'var(--primary)', color: msg.rol === 'user' ? 'inherit' : 'white', padding: '0.5rem', borderRadius: '50%', height: 'fit-content', border: msg.rol === 'user' ? '1px solid var(--border)' : 'none' }}>
                        {msg.rol === 'user' ? <User size={16} /> : <Brain size={16} />}
                      </div>
                      <div style={{ 
                        backgroundColor: msg.rol === 'user' ? 'white' : 'var(--primary)', 
                        color: msg.rol === 'user' ? 'inherit' : 'white',
                        border: msg.rol === 'user' ? '1px solid var(--border)' : 'none', 
                        padding: '0.75rem 1rem', 
                        borderRadius: msg.rol === 'user' ? '0 1rem 1rem 1rem' : '1rem 0 1rem 1rem', 
                        flex: 1, 
                        whiteSpace: 'pre-wrap',
                        fontSize: '0.9rem'
                      }}>
                        {msg.contenido}
                      </div>
                    </div>
                  ))}
                  {agentChatLoading && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>El agente está escribiendo...</div>}
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input 
                  type="text" 
                  value={agentInput}
                  onChange={e => setAgentInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendFollowUpMessage()}
                  placeholder="Ej: ¿Por qué consideras que le falta base matemática?"
                  style={{ flex: 1, padding: '0.75rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', outline: 'none' }}
                  disabled={agentChatLoading}
                />
                <button 
                  onClick={sendFollowUpMessage}
                  disabled={agentChatLoading || !agentInput.trim()}
                  style={{ backgroundColor: 'var(--primary)', color: 'white', border: 'none', padding: '0 1rem', borderRadius: 'var(--radius)', cursor: (agentChatLoading || !agentInput.trim()) ? 'not-allowed' : 'pointer', opacity: (agentChatLoading || !agentInput.trim()) ? 0.7 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  <Send size={18} />
                </button>
              </div>
            </div>

          </div>
        )}
        
        {agentSummary && agentSummary.estado === "sin_actividad" && (
          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)', textAlign: 'center', color: 'var(--text-muted)' }}>
            El alumno no tiene suficiente actividad (mensajes procesados) para generar una evaluación.
          </div>
        )}
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
