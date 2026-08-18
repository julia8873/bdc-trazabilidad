import { API_URL } from './api';

// In-memory token storage (never touches localStorage or sessionStorage)
let currentAccessToken: string | null = null;

export const setApiToken = (token: string | null) => {
  currentAccessToken = token;
};

export const apiClient = async (endpoint: string, options: RequestInit = {}) => {
  // Use absolute URL if starting with http, else prepend API_URL
  let url = endpoint;
  if (!endpoint.startsWith('http')) {
    // Make sure we handle slashes correctly
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    url = `${API_URL}${path}`;
  }

  const token = currentAccessToken;
  
  const config = {
    ...options,
    credentials: 'include' as RequestCredentials,
    headers: {
      ...options.headers,
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    }
  };

  const response = await fetch(url, config);
  
  if (response.status === 401 && !url.includes('/v1/token') && !url.includes('/v1/refresh')) {
    window.dispatchEvent(new CustomEvent('auth-unauthorized'));
  }
  
  return response;
};
