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
import { BookOpen, Activity, AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Loader2, Send, RefreshCw, User, Bot } from 'lucide-react';

export const StudentProfile: React.FC = () => {
  const { courseId, studentId } = useParams();

  const [metrics, setMetrics] = useState<StudentMetrics | null>(null);
  const [conceptos, setConceptos] = useState<ConceptosFrecuenciasResponse | null>(null);
  const [syncTrigger, setSyncTrigger] = useState(0);
  
  // Timeline State
  const [interactions, setInteractions] = useState<PaginatedInteractions | null>(null);
  const [filtroTipo, setFiltroTipo] = useState<string>('');
  const [filtroConcepto, setFiltroConcepto] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedContent, setExpandedContent] = useState<Record<string, {alumno: string, bot: string}>>({});
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
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}?_t=${Date.now()}`),
          apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/conceptos?_t=${Date.now()}`)
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
  }, [courseId, studentId, syncTrigger]);

  // Fetch timeline whenever filters change
  useEffect(() => {
    const fetchTimeline = async () => {
      let url = `/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/interacciones?limit=50&_t=${Date.now()}`;
      if (filtroTipo) url += `&tipo=${filtroTipo}`;
      if (filtroConcepto) url += `&concepto=${filtroConcepto}`;
      
      const res = await apiClient(url);
      if (res.ok) {
        setInteractions(await res.json());
      }
    };
    if (courseId && studentId) fetchTimeline();
  }, [courseId, studentId, filtroTipo, filtroConcepto, syncTrigger]);

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
        setExpandedId(null);
        return;
    }
    setExpandedId(id);
    if (!expandedContent[id] || expandedContent[id].alumno === "Error al cargar contenido" || expandedContent[id].alumno === "Error de red") {
        try {
            setContentLoading(prev => ({ ...prev, [id]: true }));
            const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/interacciones/${id}/contenido`);
            if (res.ok) {
                const data: InteraccionContenidoResponse = await res.json();
                setExpandedContent(prev => ({ ...prev, [id]: {alumno: data.mensaje_alumno, bot: data.respuesta_bot} }));
            } else {
                setExpandedContent(prev => ({ ...prev, [id]: {alumno: "Error al cargar contenido", bot: ""} }));
            }
        } catch (e) {
            setExpandedContent(prev => ({ ...prev, [id]: {alumno: "Error de red", bot: ""} }));
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

  if (loading) return <div className="container mt-8 flex justify-center"><div className="pill pill-neutral"><Loader2 className="animate-spin" size={16}/> Cargando perfil del alumno...</div></div>;
  if (error) return <div className="container mt-8"><div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}><AlertTriangle size={20}/> {error}</div></div>;
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
    <div className="container animate-slide-up">
      <div className="flex items-center justify-between mb-8 glass" style={{ padding: '1.5rem', borderRadius: 'var(--radius)' }}>
        <h2 style={{ fontSize: '1.5rem' }}>Perfil de <span style={{ color: 'var(--primary)' }}>{studentName}</span> <span style={{ opacity: 0.6, fontSize: '0.85em' }}>({courseName})</span></h2>
        <button 
            className="btn-primary"
            onClick={() => setSyncTrigger(prev => prev + 1)}
            title="Sincronizar manualmente los datos con GitHub"
        >
            <RefreshCw size={16} /> Sync
        </button>
      </div>

      <div className="grid grid-cols-2 mb-8">
        {/* Métricas Principales */}
        <div className="card hover-lift">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Conceptos Cubiertos</h3>
          </div>
          <div className="mt-4 flex flex-wrap gap-2" style={{ alignContent: 'flex-start', overflowY: 'auto' }}>
            {chartData.length > 0 ? (
                chartData.map(d => (
                  <button 
                    key={d.name} 
                    onClick={() => setFiltroConcepto(filtroConcepto === d.name ? "" : d.name)}
                    className={`pill interactive ${filtroConcepto === d.name ? 'active' : ''}`}
                  >
                    {d.name} <span style={{ opacity: 0.7, fontSize: '0.85em', marginLeft: '0.25rem' }}>{d.value}</span>
                  </button>
                ))
            ) : (
              <p className="empty-state w-100" style={{ padding: '2rem 1rem' }}>Sin conceptos registrados</p>
            )}
          </div>
        </div>

        <div className="card hover-lift flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Total Interacciones</h3>
          </div>
          <div className="flex items-center gap-4" style={{ padding: '1.25rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)', marginBottom: '1.5rem', border: '1px solid var(--border-subtle)' }}>
            <h2 style={{ fontSize: '2.5rem', color: 'var(--primary)' }}>{meaningfulInteractions}</h2>
            <div className="flex-col">
              <p style={{ fontWeight: 500, fontSize: '1rem' }}>Relevantes</p>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Excluye {fueraDeAmbito} consultas fuera de ámbito</p>
            </div>
          </div>
          
          {/* Agente de Evaluación */}
          <div className="flex-col flex-1" style={{ borderTop: '1px solid var(--border)', paddingTop: '1.5rem' }}>
            <h3 className="mb-4 flex items-center gap-2"><CheckCircle size={18} color="var(--success)"/> Evaluación Asistida por IA</h3>
            
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
                    <div className="flex-col" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', flex: 1, overflow: 'hidden' }}>
                        <div style={{ padding: '0.8rem 1rem', backgroundColor: 'var(--bg-main)', borderBottom: '1px solid var(--border)', fontSize: '0.875rem', fontWeight: 600 }}>
                            Seguimiento (Basado en hechos)
                        </div>
                        <div style={{ padding: '1rem', flex: 1, overflowY: 'auto', maxHeight: '180px', fontSize: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {chatHistory.length === 0 && <p style={{ color: 'var(--text-muted)' }}>Pregunta al agente sobre la evaluación ("¿por qué...?")</p>}
                            {chatHistory.map((msg, i) => (
                                <div key={i} className="animate-fade-in" style={{ alignSelf: msg.rol === 'user' ? 'flex-end' : 'flex-start', backgroundColor: msg.rol === 'user' ? 'var(--primary)' : 'var(--bg-main)', color: msg.rol === 'user' ? '#fff' : 'var(--text-main)', padding: '0.75rem 1rem', borderRadius: msg.rol === 'user' ? '1rem 1rem 0 1rem' : '1rem 1rem 1rem 0', maxWidth: '85%', boxShadow: 'var(--shadow-sm)' }}>
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
                                style={{ flex: 1, padding: '0.75rem 1rem', border: 'none', outline: 'none', backgroundColor: 'var(--bg-card)', color: 'var(--text-main)' }} 
                                disabled={chatLoading}
                            />
                            <button onClick={handleSendChat} disabled={chatLoading} style={{ padding: '0.75rem 1.25rem', backgroundColor: 'var(--bg-main)', border: 'none', cursor: 'pointer', borderLeft: '1px solid var(--border)' }}>
                                {chatLoading ? <Loader2 size={18} className="animate-spin" color="var(--primary)" /> : <Send size={18} color="var(--primary)" />}
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

      <div className="card mt-8 hover-lift" style={{ overflow: 'hidden' }}>
        <div className="flex items-center justify-between mb-6">
            <h3 style={{ margin: 0, fontSize: '1.25rem' }}>Línea Temporal de Interacciones</h3>
            <div className="flex gap-4">
                <select className="input" value={filtroTipo} onChange={e => setFiltroTipo(e.target.value)} style={{ padding: '0.5rem', width: 'auto' }}>
                    <option value="">Todos los tipos</option>
                    {tiposDisponibles.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <select className="input" value={filtroConcepto} onChange={e => setFiltroConcepto(e.target.value)} style={{ padding: '0.5rem', width: 'auto' }}>
                    <option value="">Todos los conceptos</option>
                    {conceptosDisponibles.map(c => <option key={c} value={c}>{c} ({conceptos?.conceptos[c] || 0})</option>)}
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
                        {item.referencia_evento && metrics?.repo_url && (
                            <div style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>
                                <a href={`${metrics.repo_url.replace(".git", "")}/commit/${item.referencia_evento}`} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} style={{ color: 'var(--primary)', textDecoration: 'underline', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h6v6M10 14L21 3M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"></path></svg>
                                    Ver en GitHub
                                </a>
                            </div>
                        )}
                        {item.concepto && item.concepto.length > 0 && (
                            <div style={{ display: 'flex', gap: '0.25rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
                                {item.concepto.map(c => (
                                    <span key={c} style={{ backgroundColor: 'var(--border)', padding: '0.1rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c}</span>
                                ))}
                            </div>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {expandedId === item.id && (
                      <div className="animate-slide-up" style={{ padding: '1.5rem', borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-main)', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
                          <div style={{ marginBottom: '1.5rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--bg-card)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', width: 'fit-content' }}>
                              <AlertTriangle size={16} /> Los datos sensibles detectados se muestran redactados.
                          </div>
                          {contentLoading[item.id] ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)' }}><Loader2 size={16} className="animate-spin" /> Cargando contenido...</div>
                          ) : expandedContent[item.id] ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                                {expandedContent[item.id].alumno === "Error al cargar contenido" || expandedContent[item.id].alumno === "Error de red" ? (
                                    <div style={{ color: 'var(--danger)', padding: '1rem', backgroundColor: 'var(--danger-light)', borderRadius: 'var(--radius)' }}>{expandedContent[item.id].alumno}</div>
                                ) : (
                                    <>
                                        <div style={{ display: 'flex', gap: '1rem', flexDirection: 'row' }}>
                                            <div style={{ backgroundColor: 'var(--bg-card)', padding: '0.75rem', borderRadius: '50%', height: 'fit-content', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}><User size={20} color="var(--text-muted)"/></div>
                                            <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', padding: '1rem 1.25rem', borderRadius: '0 1rem 1rem 1rem', flex: 1, boxShadow: 'var(--shadow-sm)', lineHeight: 1.6 }}>{expandedContent[item.id].alumno}</div>
                                        </div>
                                        {expandedContent[item.id].bot && (
                                            <div style={{ display: 'flex', gap: '1rem', flexDirection: 'row-reverse' }}>
                                                <div style={{ backgroundColor: 'var(--primary-light)', padding: '0.75rem', borderRadius: '50%', height: 'fit-content', border: '1px solid var(--primary-glow)' }}><Bot size={20} color="var(--primary)"/></div>
                                                <div style={{ backgroundColor: 'var(--primary)', color: 'white', padding: '1rem 1.25rem', borderRadius: '1rem 0 1rem 1rem', flex: 1, boxShadow: 'var(--shadow-glow)', lineHeight: 1.6 }}>{expandedContent[item.id].bot}</div>
                                            </div>
                                        )}
                                    </>
                                )}
                              </div>
                          ) : null}
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
