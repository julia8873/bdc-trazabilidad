import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import type { UserToken } from '../lib/api';
import { API_URL } from '../lib/api';
import { setApiToken } from '../lib/apiClient';

interface AuthContextType {
  token: string | null;
  user: UserToken | null;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [user, setUser] = useState<UserToken | null>(null);

  // Initialize from API /refresh on startup
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const response = await fetch(`${API_URL}/refresh`, {
          method: 'POST',
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setApiToken(data.access_token);
          setToken(data.access_token);
          setUser(jwtDecode<UserToken>(data.access_token));
        }
      } catch (e) {
        console.error("Initialization refresh failed", e);
      } finally {
        setIsInitializing(false);
      }
    };
    initializeAuth();
  }, []);

  const login = (newToken: string) => {
    try {
      // NOTA DE SEGURIDAD: El payload decodificado en cliente es para UX únicamente
      // (decidir qué menús mostrar). Toda decisión de autorización real se revalida
      // en el backend (verify_token) validando la firma del JWT en cada request.
      const decoded = jwtDecode<UserToken>(newToken);
      setApiToken(newToken);
      setToken(newToken);
      setUser(decoded);
    } catch (e) {
      console.error("Invalid token", e);
    }
  };

  const logout = () => {
    // Si el usuario es expulsado mid-session (por ej. 401), preservamos la ruta actual
    // para que pueda regresar tras loguearse de nuevo.
    sessionStorage.setItem('returnPath', window.location.pathname);
    
    // Attempt to notify server to revoke token
    fetch(`${API_URL}/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
    
    setApiToken(null);
    setToken(null);
    setUser(null);
  };

  // Monitor expiration
  useEffect(() => {
    if (user) {
      const expTime = user.exp * 1000;
      const timeToExpire = expTime - Date.now();
      
      if (timeToExpire <= 0) {
        logout();
      } else {
        const timer = setTimeout(async () => {
          try {
            const response = await fetch(`${API_URL}/refresh`, { method: 'POST', credentials: 'include' });
            if (response.ok) {
              const data = await response.json();
              setApiToken(data.access_token);
              setToken(data.access_token);
              setUser(jwtDecode<UserToken>(data.access_token));
            } else {
              logout();
            }
          } catch (e) {
            logout();
          }
        }, Math.max(0, timeToExpire - 5000)); // Refresh 5 seconds before expiration
        return () => clearTimeout(timer);
      }
    }
  }, [user]);

  // Listen for global unauthorized events from apiClient
  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    
    window.addEventListener('auth-unauthorized', handleUnauthorized);
    
    return () => {
      window.removeEventListener('auth-unauthorized', handleUnauthorized);
    };
  }, []);

  if (isInitializing) return null;

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
