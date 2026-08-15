import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import type { UserToken } from '../lib/api';
import { API_URL } from '../lib/api';

interface AuthContextType {
  token: string | null;
  user: UserToken | null;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<UserToken | null>(() => {
    const savedToken = localStorage.getItem('token');
    if (savedToken) {
      try {
        return jwtDecode<UserToken>(savedToken);
      } catch (e) {
        localStorage.removeItem('token');
        return null;
      }
    }
    return null;
  });

  const login = (newToken: string) => {
    try {
      // NOTA DE SEGURIDAD: El payload decodificado en cliente es para UX únicamente
      // (decidir qué menús mostrar). Toda decisión de autorización real se revalida
      // en el backend (verify_token) validando la firma del JWT en cada request.
      const decoded = jwtDecode<UserToken>(newToken);
      localStorage.setItem('token', newToken);
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
    localStorage.removeItem('token');
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
        const timer = setTimeout(() => {
          logout();
        }, timeToExpire);
        return () => clearTimeout(timer);
      }
    }
  }, [user]);

  // Global fetch interceptor for adding token and handling 401
  useEffect(() => {
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      let [resource, config] = args;
      
      if (typeof resource === 'string' && resource.startsWith(API_URL)) {
        config = config || {};
        config.headers = {
          ...config.headers,
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
      }
      
      const response = await originalFetch(resource, config);
      
      if (response.status === 401 && resource.toString().startsWith(API_URL) && !resource.toString().includes('/token')) {
        // Token is invalid/expired
        logout();
      }
      
      return response;
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, [token]);

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
