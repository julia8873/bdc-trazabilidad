import React, { useState, useEffect } from 'react';
import { apiClient } from '../lib/apiClient';
import { Edit3, Save, X, Plus, Trash2 } from 'lucide-react';

interface Criterio {
  nombre: string;
  observacion: string;
}

interface Rubrica {
  version: number;
  instrucciones_agente: string;
  criterios: Criterio[];
}

export const RubricEditor: React.FC<{ courseId: string }> = ({ courseId }) => {
  const [rubrica, setRubrica] = useState<Rubrica | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState(false);

  // Draft state
  const [instrucciones, setInstrucciones] = useState('');
  const [criterios, setCriterios] = useState<Criterio[]>([]);

  useEffect(() => {
    fetchRubric();
  }, [courseId]);

  const fetchRubric = async () => {
    setLoading(true);
    try {
      const res = await apiClient(`/v1/metrics/cursos/${courseId}/rubrica`);
      if (res.ok) {
        const data = await res.json();
        setRubrica(data);
      } else {
        // If 404, we just have a null rubric
        if (res.status !== 404) {
           setError('No se pudo cargar la rúbrica.');
        }
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    if (rubrica) {
      setInstrucciones(rubrica.instrucciones_agente || '');
      setCriterios(rubrica.criterios || []);
    } else {
      setInstrucciones(`Eres un asistente de evaluación para el curso NBT. Debes evaluar el desempeño de los alumnos basándote en los criterios definidos a continuación.`);
      setCriterios([]);
    }
    setIsEditing(true);
    setError('');
    setSuccess(false);
  };

  const handleCancel = () => {
    setIsEditing(false);
  };

  const handleSave = async () => {
    setLoading(true);
    setError('');
    setSuccess(false);
    try {
      const res = await apiClient(`/v1/metrics/cursos/${courseId}/rubrica`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          instrucciones_agente: instrucciones,
          criterios: criterios
        })
      });
      if (res.ok) {
        const data = await res.json();
        setRubrica(data);
        setIsEditing(false);
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        throw new Error('Error guardando rúbrica');
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const addCriterio = () => setCriterios([...criterios, { nombre: '', observacion: '' }]);
  const removeCriterio = (index: number) => setCriterios(criterios.filter((_, i) => i !== index));
  const updateCriterio = (index: number, field: keyof Criterio, value: string) => {
    const newC = [...criterios];
    newC[index][field] = value;
    setCriterios(newC);
  };

  if (!rubrica && !loading && !error && !isEditing) {
    return (
      <div className="card mt-8">
         <div className="flex justify-between items-center mb-4">
            <h3 style={{ margin: 0 }}>Rúbrica de Evaluación</h3>
            <button className="btn-ghost flex items-center gap-2" onClick={handleEdit}>
              <Edit3 size={16} /> Crear Rúbrica
            </button>
         </div>
         <p style={{ color: 'var(--text-muted)' }}>Este curso utiliza la rúbrica global por defecto. Crea una personalizada para este curso.</p>
      </div>
    );
  }

  return (
    <div className="card mt-8">
      <div className="flex justify-between items-center mb-4">
        <h3 style={{ margin: 0 }}>{rubrica?.version ? `Rúbrica de Evaluación (Versión ${rubrica.version})` : 'Rúbrica de Evaluación'}</h3>
        {!isEditing ? (
          <button className="btn-ghost flex items-center gap-2" onClick={handleEdit}>
            <Edit3 size={16} /> Editar
          </button>
        ) : (
          <div className="flex gap-2">
            <button className="btn-ghost flex items-center gap-2" onClick={handleCancel}>
              <X size={16} /> Cancelar
            </button>
            <button className="btn-primary flex items-center gap-2" onClick={handleSave} disabled={loading}>
              <Save size={16} /> Guardar
            </button>
          </div>
        )}
      </div>

      {error && <div style={{ color: 'var(--danger)', marginBottom: '1rem' }}>{error}</div>}
      {success && <div style={{ color: 'var(--success)', marginBottom: '1rem' }}>Rúbrica actualizada.</div>}

      {!isEditing ? (
        <div>
          <div className="mb-4">
            <h4 style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Instrucciones Adicionales (Agente)</h4>
            <p style={{ whiteSpace: 'pre-wrap' }}>{rubrica?.instrucciones_agente || 'Sin instrucciones adicionales.'}</p>
          </div>
          <div>
            <h4 style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Criterios ({rubrica?.criterios?.length || 0})</h4>
            <ul style={{ listStyleType: 'disc', paddingLeft: '1.25rem' }}>
              {rubrica?.criterios?.map((c, i) => {
                const name = c.nombre?.trim();
                const obs = c.observacion?.trim();
                
                if (!name && obs) {
                  return (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>
                      <strong>Criterio {i + 1}:</strong> {obs}
                    </li>
                  );
                } else if (name && !obs) {
                  return (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>
                      <strong>Criterio {i + 1}:</strong> {name}
                    </li>
                  );
                } else if (!name && !obs) {
                  return (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>
                      <strong>Criterio {i + 1}</strong>
                    </li>
                  );
                } else {
                  return (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>
                      <strong>{name}:</strong> {obs}
                    </li>
                  );
                }
              })}
            </ul>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: '0.25rem' }}>Instrucciones Adicionales</label>
            <textarea
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--bg-main)', color: 'var(--text-main)', minHeight: '100px' }}
              value={instrucciones}
              onChange={(e) => setInstrucciones(e.target.value)}
            />
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500 }}>Criterios</label>
              <button className="btn-ghost flex items-center gap-1" style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }} onClick={addCriterio}>
                <Plus size={14} /> Añadir Criterio
              </button>
            </div>
            {criterios.map((c, i) => (
              <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'flex-start' }}>
                <input
                  type="text"
                  placeholder="Nombre"
                  value={c.nombre}
                  onChange={(e) => updateCriterio(i, 'nombre', e.target.value)}
                  style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--bg-main)', color: 'var(--text-main)', width: '30%' }}
                />
                <textarea
                  placeholder="Observación"
                  value={c.observacion}
                  onChange={(e) => updateCriterio(i, 'observacion', e.target.value)}
                  style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--bg-main)', color: 'var(--text-main)', width: '60%' }}
                />
                <button className="btn-ghost" style={{ padding: '0.5rem', color: 'var(--danger)' }} onClick={() => removeCriterio(i)}>
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
