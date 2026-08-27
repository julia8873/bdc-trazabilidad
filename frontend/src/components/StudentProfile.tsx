import React, { useEffect, useState, useRef } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import type {
  StudentMetrics,
  PaginatedInteraccionesMetadatos,
  ConceptosFrecuenciasResponse,
  InteraccionContenidoResponse,
  AgentSummaryResponse,
  AgentFollowUpMessage,
  AgentFollowUpRequest,
  AgentFollowUpResponse
} from '../lib/api';
import {
  BookOpen, Activity, AlertTriangle, CheckCircle,
  ChevronDown, ChevronRight, Loader2, Send, RefreshCw,
  User, Bot, Search, BarChart2, Cpu, Check, ArrowUpDown
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
type TabId = 'stats' | 'concepts' | 'ai';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'stats',    label: 'Estadísticas',  icon: <BarChart2 size={16} /> },
  { id: 'concepts', label: 'Conceptos',     icon: <BookOpen  size={16} /> },
  { id: 'ai',       label: 'Evaluación IA', icon: <Cpu       size={16} /> },
];

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
const COURSE_NAMES: Record<string, string> = {
  '3': 'Ecuaciones Diferenciales II'
};

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────
export const StudentProfile: React.FC = () => {
  const { courseId, studentId } = useParams();
  const location = useLocation();
  const studentName = location.state?.studentName || `Alumno ${studentId}`;
  const courseName = courseId ? COURSE_NAMES[courseId] || `Curso ${courseId}` : `Curso ${courseId}`;

  // ── Data ────────────────────────────────────────────────────────────────────
  const [metrics, setMetrics]       = useState<StudentMetrics | null>(null);
  const [conceptos, setConceptos]   = useState<ConceptosFrecuenciasResponse | null>(null);
  const [syncTrigger, setSyncTrigger] = useState(0);
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(true);

  // ── Tab ─────────────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<TabId>('stats');

  // ── Timeline State ──────────────────────────────────────────────────────────
  const [interactions, setInteractions] = useState<PaginatedInteraccionesMetadatos | null>(null);
  const [filtroTipo, setFiltroTipo]     = useState('');
  const [filtroConceptos, setFiltroConceptos] = useState<string[]>([]);
  const [searchText, setSearchText]     = useState('');
  const [sortBy, setSortBy]             = useState<'fecha' | 'tipo'>('fecha');
  const [sortDir, setSortDir]           = useState<'asc' | 'desc'>('desc');
  const [expandedId, setExpandedId]     = useState<string | null>(null);
  const [expandedContent, setExpandedContent] = useState<Record<string, { alumno: string; bot: string }>>({});
  const [contentLoading, setContentLoading]   = useState<Record<string, boolean>>({});

  // Debounce search
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // ── Agent State ─────────────────────────────────────────────────────────────
  const [agentSummary, setAgentSummary] = useState<AgentSummaryResponse | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError]     = useState('');
  const [agent503, setAgent503]         = useState(false);
  const [chatHistory, setChatHistory]   = useState<AgentFollowUpMessage[]>([]);
  const [chatInput, setChatInput]       = useState('');
  const [chatLoading, setChatLoading]   = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // ── Fetch student base data ─────────────────────────────────────────────────
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

        setMetrics(await mRes.json());
        if (cRes.ok) setConceptos(await cRes.json());
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    if (courseId && studentId) fetchStudentData();
  }, [courseId, studentId, syncTrigger]);

  // ── Debounce search input ───────────────────────────────────────────────────
  useEffect(() => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => setDebouncedSearch(searchText), 400);
    return () => { if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current); };
  }, [searchText]);

  // ── Fetch timeline ──────────────────────────────────────────────────────────
  useEffect(() => {
    const fetchTimeline = async () => {
      const params = new URLSearchParams({
        limit: '50',
        _t: String(Date.now()),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (filtroTipo)              params.set('tipo', filtroTipo);
      if (filtroConceptos.length)  params.set('concepto', filtroConceptos.join(','));
      if (debouncedSearch)         params.set('search', debouncedSearch);

      const res = await apiClient(
        `/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/interacciones?${params.toString()}`
      );
      if (res.ok) setInteractions(await res.json());
    };
    if (courseId && studentId) fetchTimeline();
  }, [courseId, studentId, filtroTipo, filtroConceptos, debouncedSearch, sortBy, sortDir, syncTrigger]);

  // ── Auto-scroll chat ────────────────────────────────────────────────────────
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // ── Handlers ────────────────────────────────────────────────────────────────
  const toggleConcepto = (name: string) => {
    setFiltroConceptos(prev =>
      prev.includes(name) ? prev.filter(c => c !== name) : [...prev, name]
    );
  };

  const toggleSortDir = () => setSortDir(d => d === 'asc' ? 'desc' : 'asc');

  const toggleExpand = async (id: string) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (!expandedContent[id] || expandedContent[id].alumno === 'Error al cargar contenido' || expandedContent[id].alumno === 'Error de red') {
      try {
        setContentLoading(prev => ({ ...prev, [id]: true }));
        const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/interacciones/${id}/contenido`);
        if (res.ok) {
          const data: InteraccionContenidoResponse = await res.json();
          setExpandedContent(prev => ({ ...prev, [id]: { alumno: data.mensaje_alumno, bot: data.respuesta_bot } }));
        } else {
          setExpandedContent(prev => ({ ...prev, [id]: { alumno: 'Error al cargar contenido', bot: '' } }));
        }
      } catch {
        setExpandedContent(prev => ({ ...prev, [id]: { alumno: 'Error de red', bot: '' } }));
      } finally {
        setContentLoading(prev => ({ ...prev, [id]: false }));
      }
    }
  };

  const handleGenerateSummary = async () => {
    try {
      setAgentLoading(true); setAgentError('');
      const res = await apiClient(`/v1/metrics/cursos/${courseId}/estudiantes/${studentId}/resumen`, { method: 'POST' });
      if (res.status === 503) { setAgent503(true); return; }
      if (!res.ok) throw new Error('Error al generar resumen');
      setAgentSummary(await res.json());
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
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Error en el seguimiento'); }
      const data: AgentFollowUpResponse = await res.json();
      setChatHistory(data.historial_actualizado);
      setChatInput('');
    } catch (e: any) {
      setAgentError(e.message);
    } finally {
      setChatLoading(false);
    }
  };

  // ── Guard clauses ───────────────────────────────────────────────────────────
  if (loading) return (
    <div className="container mt-8 flex justify-center">
      <div className="pill pill-neutral"><Loader2 className="animate-spin" size={16} /> Cargando perfil del alumno...</div>
    </div>
  );
  if (error) return (
    <div className="container mt-8">
      <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <AlertTriangle size={20} /> {error}
      </div>
    </div>
  );
  if (!metrics) return null;

  // ── Derived data ────────────────────────────────────────────────────────────
  const chartData = conceptos?.conceptos
    ? Object.entries(conceptos.conceptos).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
    : [];
  const fueraDeAmbito = metrics.interactions_by_type['fuera_de_ambito'] || 0;
  const meaningfulInteractions = metrics.total_interactions - fueraDeAmbito;
  const tiposDisponibles = Object.keys(metrics.interactions_by_type);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="container animate-slide-up" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between glass" style={{ padding: '1.25rem 1.5rem', borderRadius: 'var(--radius)' }}>
        <h2 style={{ fontSize: '1.5rem', margin: 0 }}>
          Perfil de <span style={{ color: 'var(--primary)' }}>{studentName}</span>{' '}
          <span style={{ opacity: 0.6, fontSize: '0.85em' }}>({courseName})</span>
        </h2>
        <button className="btn-primary" onClick={() => setSyncTrigger(prev => prev + 1)} title="Sincronizar datos con GitHub">
          <RefreshCw size={16} /> Sync
        </button>
      </div>

      {/* ── Tab Bar ───────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '2px solid var(--border)', paddingBottom: '0' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            id={`tab-btn-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.65rem 1.25rem',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--primary)' : '2px solid transparent',
              marginBottom: '-2px',
              background: 'transparent',
              color: activeTab === tab.id ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: 'pointer',
              fontSize: '0.9rem',
              transition: 'color 0.2s, border-color 0.2s',
              borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
            }}
          >
            {tab.icon} {tab.label}
            {tab.id === 'concepts' && filtroConceptos.length > 0 && (
              <span style={{
                backgroundColor: 'var(--primary)', color: 'white',
                borderRadius: '999px', fontSize: '0.7rem',
                padding: '0.1rem 0.5rem', fontWeight: 700
              }}>
                {filtroConceptos.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab Panels ────────────────────────────────────────────────────── */}

      {/* Panel 1: Estadísticas Globales */}
      {activeTab === 'stats' && (
        <div id="tab-panel-stats" className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          {/* Total Interacciones */}
          <div className="card hover-lift" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="flex items-center gap-2">
              <Activity size={20} color="var(--primary)" />
              <h3 style={{ margin: 0 }}>Total Interacciones</h3>
            </div>
            <div style={{
              padding: '1.5rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)',
              border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '1.5rem'
            }}>
              <h2 style={{ fontSize: '3rem', color: 'var(--primary)', margin: 0, lineHeight: 1 }}>{meaningfulInteractions}</h2>
              <div>
                <p style={{ fontWeight: 600, fontSize: '1rem', margin: '0 0 0.25rem' }}>Relevantes</p>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0 }}>
                  Excluye {fueraDeAmbito} consultas fuera de ámbito
                </p>
              </div>
            </div>
          </div>

          {/* Distribución por Tipo */}
          <div className="card hover-lift" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="flex items-center gap-2">
              <BarChart2 size={20} color="var(--primary)" />
              <h3 style={{ margin: 0 }}>Distribución por Tipo</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {tiposDisponibles.length === 0
                ? <p style={{ color: 'var(--text-muted)' }}>Sin datos</p>
                : tiposDisponibles.map(t => {
                    const count = metrics.interactions_by_type[t] || 0;
                    const pct = metrics.total_interactions > 0
                      ? Math.round((count / metrics.total_interactions) * 100) : 0;
                    return (
                      <div key={t}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                          <span style={{ color: 'var(--text-muted)' }}>{t}</span>
                          <span style={{ fontWeight: 600 }}>{count} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({pct}%)</span></span>
                        </div>
                        <div style={{ height: '6px', borderRadius: '3px', backgroundColor: 'var(--border)' }}>
                          <div style={{ height: '100%', width: `${pct}%`, borderRadius: '3px', backgroundColor: 'var(--primary)', transition: 'width 0.6s ease' }} />
                        </div>
                      </div>
                    );
                  })
              }
            </div>
          </div>
        </div>
      )}

      {/* Panel 2: Conceptos */}
      {activeTab === 'concepts' && (
        <div id="tab-panel-concepts" className="card animate-fade-in hover-lift">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Conceptos Cubiertos</h3>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
            Haz clic para filtrar la línea temporal (varios — lógica <strong>OR</strong>).
            {filtroConceptos.length > 0 && (
              <button
                onClick={() => setFiltroConceptos([])}
                style={{ marginLeft: '0.75rem', color: 'var(--danger)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.875rem' }}
              >
                ✕ Limpiar selección
              </button>
            )}
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', alignContent: 'flex-start' }}>
            {chartData.length > 0 ? chartData.map(d => {
              const selected = filtroConceptos.includes(d.name);
              return (
                <button
                  key={d.name}
                  onClick={() => toggleConcepto(d.name)}
                  className={`pill interactive ${selected ? 'active' : ''}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.35rem',
                    paddingLeft: selected ? '0.6rem' : undefined,
                    outline: selected ? '2px solid var(--primary)' : undefined,
                    outlineOffset: '2px',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {selected && <Check size={12} strokeWidth={3} />}
                  {d.name}
                  <span style={{ opacity: 0.7, fontSize: '0.82em', marginLeft: '0.15rem' }}>{d.value}</span>
                </button>
              );
            }) : (
              <p className="empty-state w-100" style={{ padding: '2rem 1rem' }}>Sin conceptos registrados</p>
            )}
          </div>
        </div>
      )}

      {/* Panel 3: Evaluación IA */}
      {activeTab === 'ai' && (
        <div id="tab-panel-ai" className="card animate-fade-in hover-lift" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="flex items-center gap-2">
            <Cpu size={20} color="var(--primary)" />
            <h3 style={{ margin: 0 }}>Evaluación Asistida por IA</h3>
          </div>

          {agent503 ? (
            <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)', color: 'var(--text-muted)' }}>
              El Agente de Evaluación está desactivado por configuración (HTTP 503).
            </div>
          ) : agentSummary ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {agentSummary.estado === 'sin_actividad' ? (
                <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                  Este alumno no tiene suficiente actividad registrada para generar un resumen.
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <CheckCircle size={16} color="var(--success)" />
                      <strong>Fortalezas</strong>
                    </div>
                    <ul style={{ paddingLeft: '1.25rem', fontSize: '0.875rem', margin: 0 }}>
                      {agentSummary.fortalezas.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  </div>
                  <div style={{ padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <AlertTriangle size={16} color="var(--danger)" />
                      <strong>Señales de Alerta</strong>
                    </div>
                    <ul style={{ paddingLeft: '1.25rem', fontSize: '0.875rem', margin: 0 }}>
                      {agentSummary.senales_alerta.map((f, i) => <li key={i} style={{ color: 'var(--danger)' }}>{f}</li>)}
                    </ul>
                  </div>
                </div>
              )}

              {/* Chat de seguimiento */}
              <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                <div style={{ padding: '0.75rem 1rem', backgroundColor: 'var(--bg-main)', borderBottom: '1px solid var(--border)', fontSize: '0.875rem', fontWeight: 600 }}>
                  Seguimiento (Basado en hechos)
                </div>
                <div
                  ref={chatScrollRef}
                  style={{ padding: '1rem', overflowY: 'auto', maxHeight: '250px', fontSize: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
                >
                  {chatHistory.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', margin: 0 }}>Pregunta al agente sobre la evaluación ("¿por qué...?")</p>
                  )}
                  {chatHistory.map((msg, i) => (
                    <div
                      key={i}
                      className="animate-fade-in"
                      style={{
                        alignSelf: msg.rol === 'user' ? 'flex-end' : 'flex-start',
                        backgroundColor: msg.rol === 'user' ? 'var(--primary)' : 'var(--bg-main)',
                        color: msg.rol === 'user' ? '#fff' : 'var(--text-main)',
                        padding: '0.75rem 1rem',
                        borderRadius: msg.rol === 'user' ? '1rem 1rem 0 1rem' : '1rem 1rem 1rem 0',
                        maxWidth: '85%', boxShadow: 'var(--shadow-sm)'
                      }}
                    >
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
      )}

      {/* ── Línea Temporal (siempre visible) ─────────────────────────────── */}
      <div className="card hover-lift" style={{ overflow: 'hidden' }}>
        {/* Cabecera con controles */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 style={{ margin: 0, fontSize: '1.1rem' }}>
              Línea Temporal de Interacciones
              {interactions && (
                <span style={{ marginLeft: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                  ({interactions.total} {interactions.total === 1 ? 'resultado' : 'resultados'})
                </span>
              )}
            </h3>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Buscador */}
            <div style={{ position: 'relative', flex: 1, minWidth: '180px' }}>
              <Search size={15} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
              <input
                id="timeline-search-input"
                type="text"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                placeholder="Buscar por tipo o concepto..."
                className="input"
                style={{ paddingLeft: '2.25rem', width: '100%' }}
              />
            </div>

            {/* Filtro Tipo */}
            <select
              id="timeline-filter-tipo"
              className="input"
              value={filtroTipo}
              onChange={e => setFiltroTipo(e.target.value)}
              style={{ padding: '0.5rem', width: 'auto' }}
            >
              <option value="">Todos los tipos</option>
              {tiposDisponibles.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            {/* Sort By */}
            <select
              id="timeline-sort-by"
              className="input"
              value={sortBy}
              onChange={e => setSortBy(e.target.value as 'fecha' | 'tipo')}
              style={{ padding: '0.5rem', width: 'auto' }}
            >
              <option value="fecha">Ordenar: Fecha</option>
              <option value="tipo">Ordenar: Tipo</option>
            </select>

            {/* Sort Direction */}
            <button
              id="timeline-sort-dir"
              onClick={toggleSortDir}
              title={sortDir === 'desc' ? 'Más recientes primero' : 'Más antiguos primero'}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.35rem',
                padding: '0.5rem 0.9rem', cursor: 'pointer',
                border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--bg-card)', color: 'var(--text-muted)',
                fontSize: '0.85rem', transition: 'all 0.15s ease',
              }}
            >
              <ArrowUpDown size={14} />
              {sortDir === 'desc' ? 'Desc' : 'Asc'}
            </button>
          </div>

          {/* Chips de conceptos activos */}
          {filtroConceptos.length > 0 && (
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', alignSelf: 'center' }}>Conceptos:</span>
              {filtroConceptos.map(c => (
                <button
                  key={c}
                  onClick={() => toggleConcepto(c)}
                  className="pill active"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.78rem', padding: '0.2rem 0.6rem' }}
                >
                  {c} <span style={{ fontSize: '1em', lineHeight: 1 }}>×</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Lista de interacciones */}
        {interactions && interactions.items.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {interactions.items.map(item => (
              <div key={item.id} style={
                {
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  overflow: 'hidden',
                  opacity: item.tipo_interaccion ? 1 : 0.55,
                }
              }>
                <div
                  className="flex items-center justify-between"
                  style={{
                    padding: '0.875rem 1rem',
                    cursor: item.tipo_interaccion ? 'pointer' : 'default',
                    backgroundColor: expandedId === item.id ? 'var(--bg-main)' : 'transparent',
                    transition: 'background-color 0.15s'
                  }}
                  onClick={() => item.tipo_interaccion && toggleExpand(item.id)}
                >
                  <div className="flex items-center gap-3">
                    {item.tipo_interaccion
                      ? (expandedId === item.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />)
                      : <span style={{ width: 18 }} />}
                    <div style={{
                      backgroundColor: item.tipo_interaccion ? 'var(--bg-main)' : 'var(--border)',
                      padding: '0.35rem 0.75rem', borderRadius: '4px',
                      fontWeight: 500, fontSize: '0.875rem',
                      color: item.tipo_interaccion ? 'var(--text-main)' : 'var(--text-muted)',
                      fontStyle: item.tipo_interaccion ? 'normal' : 'italic',
                    }}>
                      {item.tipo_interaccion || 'Sin clasificar'}
                    </div>
                    <div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(item.timestamp).toLocaleString()}</div>
                      {item.concepto.length > 0 && (
                        <div style={{ display: 'flex', gap: '0.25rem', marginTop: '0.35rem', flexWrap: 'wrap' }}>
                          {item.concepto.map(c => (
                            <span key={c} style={{
                              backgroundColor: filtroConceptos.includes(c) ? 'var(--primary-light)' : 'var(--border)',
                              color: filtroConceptos.includes(c) ? 'var(--primary)' : 'var(--text-muted)',
                              padding: '0.1rem 0.4rem', borderRadius: '4px', fontSize: '0.72rem',
                              border: filtroConceptos.includes(c) ? '1px solid var(--primary-glow)' : '1px solid transparent',
                              fontWeight: filtroConceptos.includes(c) ? 600 : 400,
                            }}>
                              {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {expandedId === item.id && (
                  <div className="animate-slide-up" style={{ padding: '1.5rem', borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-main)', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
                    <div style={{ marginBottom: '1.5rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--bg-card)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', width: 'fit-content' }}>
                      <AlertTriangle size={14} /> Los datos sensibles detectados se muestran redactados.
                    </div>
                    {contentLoading[item.id] ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)' }}>
                        <Loader2 size={16} className="animate-spin" /> Cargando contenido...
                      </div>
                    ) : expandedContent[item.id] ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        {expandedContent[item.id].alumno === 'Error al cargar contenido' || expandedContent[item.id].alumno === 'Error de red' ? (
                          <div style={{ color: 'var(--danger)', padding: '1rem', backgroundColor: 'var(--danger-light)', borderRadius: 'var(--radius)' }}>{expandedContent[item.id].alumno}</div>
                        ) : (
                          <>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                              <div style={{ backgroundColor: 'var(--bg-card)', padding: '0.75rem', borderRadius: '50%', height: 'fit-content', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}><User size={20} color="var(--text-muted)" /></div>
                              <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', padding: '1rem 1.25rem', borderRadius: '0 1rem 1rem 1rem', flex: 1, boxShadow: 'var(--shadow-sm)', lineHeight: 1.6 }}>{expandedContent[item.id].alumno}</div>
                            </div>
                            {expandedContent[item.id].bot && (
                              <div style={{ display: 'flex', gap: '1rem', flexDirection: 'row-reverse' }}>
                                <div style={{ backgroundColor: 'var(--primary-light)', padding: '0.75rem', borderRadius: '50%', height: 'fit-content', border: '1px solid var(--primary-glow)' }}><Bot size={20} color="var(--primary)" /></div>
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
          <p style={{ color: 'var(--text-muted)' }}>
            {searchText || filtroConceptos.length || filtroTipo
              ? 'No hay interacciones que coincidan con los filtros activos.'
              : 'No hay interacciones registradas.'}
          </p>
        )}
      </div>
    </div>
  );
};
