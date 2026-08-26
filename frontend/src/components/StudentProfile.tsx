import React, { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import type { 
  StudentMetrics, 
  PaginatedInteractions, 
  ConceptosFrecuenciasResponse, 
  InteraccionContenidoResponse,
  AgentSummaryResponse,
  AgentFollowUpMessage,
  AgentFollowUpRequest,
  AgentFollowUpResponse
} from '../lib/api';
import { BookOpen, Activity, Search, MessageSquare, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Loader2, Send } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export const StudentProfile: React.FC = () => {
  const { courseId, studentId } = useParams();

  const [metrics, setMetrics] = useState<StudentMetrics | null>(null);
  const [conceptos, setConceptos] = useState<ConceptosFrecuenciasResponse | null>(null);
  
  // Timeline State
  const [interactions, setInteractions] = useState<PaginatedInteractions | null>(null);
  const [filtroTipo, setFiltroTipo] = useState<string>('');
  const [filtroConcepto, setFiltroConcepto] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedContent, setExpandedContent] = useState<Record<string, string>>({});
  const [contentLoading, setContentLoading] = useState<Record<string, boolean>>({});

  // Agent State
  const [agentSummary, setAgentSummary] = useState<AgentSummaryResponse | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState('');
  const [agent503, setAgent503] = useState(false);
  const [chatHistory, setChatHistory] = useState<AgentFollowUpMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

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
        const [mRes, cRes] = await Promise.all([
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}`),
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/conceptos`)
        ]);

        if (mRes.status === 403) throw new Error('Acceso denegado a métricas del alumno');
        if (mRes.status === 503) throw new Error('Servicio de métricas no disponible');
        if (!mRes.ok) throw new Error('Error al cargar métricas del alumno');

        const mData = await mRes.json();
        setMetrics(mData);
        
        if (cRes.ok) {
            const cData = await cRes.json();
            setConceptos(cData);
        }
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (courseId && studentId) fetchStudentData();
  }, [courseId, studentId]);

  // Fetch timeline whenever filters change
  useEffect(() => {
    const fetchTimeline = async () => {
      let url = `/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/interacciones?limit=50`;
      if (filtroTipo) url += `&tipo=${filtroTipo}`;
      if (filtroConcepto) url += `&concepto=${filtroConcepto}`;
      
      const res = await apiClient(url);
      if (res.ok) {
        setInteractions(await res.json());
      }
    };
    if (courseId && studentId) fetchTimeline();
  }, [courseId, studentId, filtroTipo, filtroConcepto]);

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
        setExpandedId(null);
        return;
    }
    setExpandedId(id);
    if (!expandedContent[id]) {
        try {
            setContentLoading(prev => ({ ...prev, [id]: true }));
            const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/interacciones/${id}/contenido`);
            if (res.ok) {
                const data: InteraccionContenidoResponse = await res.json();
                setExpandedContent(prev => ({ ...prev, [id]: data.contenido_redactado }));
            } else {
                setExpandedContent(prev => ({ ...prev, [id]: "Error al cargar contenido" }));
            }
        } catch (e) {
            setExpandedContent(prev => ({ ...prev, [id]: "Error de red" }));
        } finally {
            setContentLoading(prev => ({ ...prev, [id]: false }));
        }
    }
  };

  const handleGenerateSummary = async () => {
    try {
        setAgentLoading(true);
        setAgentError('');
        const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/resumen`, {
            method: 'POST'
        });
        
        if (res.status === 503) {
            setAgent503(true);
            return;
        }
        if (!res.ok) {
            throw new Error('Error al generar resumen');
        }
        
        const data: AgentSummaryResponse = await res.json();
        setAgentSummary(data);
    } catch (e: any) {
        setAgentError(e.message);
    } finally {
        setAgentLoading(false);
    }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || !agentSummary) return;
    
    try {
        setChatLoading(true);
        const reqPayload: AgentFollowUpRequest = {
            mensaje: chatInput,
            historial: chatHistory,
            resumen_hash: agentSummary.resumen_hash
        };
        
        const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/resumen/seguimiento`, {
            method: 'POST',
            body: JSON.stringify(reqPayload)
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Error en el seguimiento');
        }
        
        const data: AgentFollowUpResponse = await res.json();
        setChatHistory(data.historial_actualizado);
        setChatInput('');
    } catch (e: any) {
        setAgentError(e.message);
    } finally {
        setChatLoading(false);
    }
  };

  if (loading) return <div className="container mt-8" style={{ textAlign: 'center' }}>Cargando perfil del alumno...</div>;
  if (error) return <div className="container mt-8"><div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div></div>;
  if (!metrics) return null;

  // Conceptos Cubiertos Chart Data
  let chartData: any[] = [];
  if (conceptos && conceptos.conceptos) {
      chartData = Object.entries(conceptos.conceptos)
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value);
  }

  // Calculate meaningful total interactions
  const fueraDeAmbito = metrics.interactions_by_type['fuera_de_ambito'] || 0;
  const meaningfulInteractions = metrics.total_interactions - fueraDeAmbito;

  // Opciones de filtro
  const tiposDisponibles = Object.keys(metrics.interactions_by_type);
  const conceptosDisponibles = conceptos ? Object.keys(conceptos.conceptos) : [];

  return (
    <div className="container">
      <div className="flex items-center justify-between mb-8">
        <h2>Perfil de {studentName} ({courseName})</h2>
      </div>

      <div className="grid grid-cols-2 mb-8">
        {/* Métricas Principales */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Conceptos Cubiertos</h3>
          </div>
          <div className="mt-4" style={{ height: '240px' }}>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 40 }}>
                  <XAxis type="number" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis dataKey="name" type="category" stroke="var(--text-muted)" fontSize={12} />
                  <Tooltip cursor={{ fill: 'var(--bg-main)' }} contentStyle={{ borderRadius: 'var(--radius)' }} />
                  <Bar dataKey="value" fill="var(--primary)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: '2rem' }}>Sin conceptos registrados</p>
            )}
          </div>
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="flex items-center gap-2 mb-4">
            <Activity size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Total Interacciones</h3>
          </div>
          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)', marginBottom: '1rem' }}>
            <h2>{meaningfulInteractions}</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>relevantes (excluye {fueraDeAmbito} fuera de ámbito)</p>
          </div>
          
          {/* Agente de Evaluación */}
          <div style={{ flex: 1, borderTop: '1px solid var(--border)', paddingTop: '1rem', display: 'flex', flexDirection: 'column' }}>
            <h3 className="mb-4 flex items-center gap-2"><CheckCircle size={18} color="var(--primary)"/> Evaluación Asistida</h3>
            
            {agent503 ? (
                <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)', color: 'var(--text-muted)' }}>
                    El Agente de Evaluación está desactivado por configuración (HTTP 503).
                </div>
            ) : agentSummary ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {agentSummary.estado === 'sin_actividad' ? (
                        <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                            Este alumno no tiene suficiente actividad registrada para generar un resumen.
                        </div>
                    ) : (
                        <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                            <strong>Fortalezas:</strong>
                            <ul style={{ paddingLeft: '1.25rem', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                                {agentSummary.fortalezas.map((f, i) => <li key={i}>{f}</li>)}
                            </ul>
                            <strong>Señales de Alerta:</strong>
                            <ul style={{ paddingLeft: '1.25rem', fontSize: '0.875rem' }}>
                                {agentSummary.senales_alerta.map((f, i) => <li key={i} style={{ color: 'var(--danger)' }}>{f}</li>)}
                            </ul>
                        </div>
                    )}
                    
                    {/* Seguimiento */}
                    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-main)', borderBottom: '1px solid var(--border)', fontSize: '0.875rem', fontWeight: 500 }}>
                            Seguimiento (Basado en hechos)
                        </div>
                        <div style={{ padding: '0.5rem', flex: 1, overflowY: 'auto', maxHeight: '150px', fontSize: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {chatHistory.length === 0 && <p style={{ color: 'var(--text-muted)' }}>Pregunta al agente sobre la evaluación ("¿por qué...?")</p>}
                            {chatHistory.map((msg, i) => (
                                <div key={i} style={{ alignSelf: msg.rol === 'user' ? 'flex-end' : 'flex-start', backgroundColor: msg.rol === 'user' ? 'var(--primary)' : 'var(--bg-main)', color: msg.rol === 'user' ? '#fff' : 'var(--text-main)', padding: '0.5rem', borderRadius: '4px', maxWidth: '80%' }}>
                                    {msg.contenido}
                                </div>
                            ))}
                        </div>
                        <div style={{ display: 'flex', borderTop: '1px solid var(--border)' }}>
                            <input 
                                type="text" 
                                value={chatInput} 
                                onChange={e => setChatInput(e.target.value)} 
                                onKeyDown={e => e.key === 'Enter' && handleSendChat()}
                                placeholder="Preguntar al agente..." 
                                style={{ flex: 1, padding: '0.5rem', border: 'none', outline: 'none' }} 
                                disabled={chatLoading}
                            />
                            <button onClick={handleSendChat} disabled={chatLoading} style={{ padding: '0.5rem 1rem', backgroundColor: 'var(--bg-main)', border: 'none', cursor: 'pointer' }}>
                                {chatLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                            </button>
                        </div>
                    </div>
                    {agentError && <div style={{ color: 'var(--danger)', fontSize: '0.875rem' }}>{agentError}</div>}
                </div>
            ) : (
                <div>
                    <button className="button button-primary w-full" onClick={handleGenerateSummary} disabled={agentLoading}>
                        {agentLoading ? 'Generando...' : 'Generar resumen formativo'}
                    </button>
                    {agentError && <div style={{ color: 'var(--danger)', fontSize: '0.875rem', marginTop: '0.5rem' }}>{agentError}</div>}
                </div>
            )}
          </div>
        </div>
      </div>

      <div className="card mt-8">
        <div className="flex items-center justify-between mb-4">
            <h3 style={{ margin: 0 }}>Línea Temporal de Interacciones</h3>
            <div className="flex gap-4">
                <select value={filtroTipo} onChange={e => setFiltroTipo(e.target.value)} style={{ padding: '0.25rem', borderRadius: '4px', border: '1px solid var(--border)' }}>
                    <option value="">Todos los tipos</option>
                    {tiposDisponibles.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <select value={filtroConcepto} onChange={e => setFiltroConcepto(e.target.value)} style={{ padding: '0.25rem', borderRadius: '4px', border: '1px solid var(--border)' }}>
                    <option value="">Todos los conceptos</option>
                    {conceptosDisponibles.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
            </div>
        </div>
        
        {interactions && interactions.items.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {interactions.items.map(item => (
              <div key={item.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                  <div 
                    className="flex items-center justify-between" 
                    style={{ padding: '1rem', cursor: 'pointer', backgroundColor: expandedId === item.id ? 'var(--bg-main)' : 'transparent' }}
                    onClick={() => toggleExpand(item.id)}
                  >
                    <div className="flex items-center gap-4">
                      {expandedId === item.id ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                      <div style={{ backgroundColor: 'var(--bg-main)', padding: '0.5rem 1rem', borderRadius: '4px', fontWeight: 500 }}>
                        {item.tipo_interaccion}
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{new Date(item.timestamp).toLocaleString()}</div>
                        {item.referencia_evento && <div style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>Ref: {item.referencia_evento}</div>}
                      </div>
                    </div>
                  </div>
                  
                  {expandedId === item.id && (
                      <div style={{ padding: '1rem', borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-main)', fontSize: '0.875rem', whiteSpace: 'pre-wrap' }}>
                          <div style={{ marginBottom: '1rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <AlertTriangle size={16} /> Los datos sensibles detectados se muestran redactados.
                          </div>
                          {contentLoading[item.id] ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Loader2 size={16} className="animate-spin" /> Cargando contenido...</div>
                          ) : (
                              <div>{expandedContent[item.id]}</div>
                          )}
                      </div>
                  )}
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>No hay interacciones registradas que coincidan con los filtros.</p>
        )}
      </div>
    </div>
  );
};
