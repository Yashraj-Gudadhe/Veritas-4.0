/**
 * Centralized Axios instance with auth token injection and error handling.
 */
import axios from 'axios';

// Determine the base URL. If VITE_API_URL is provided (e.g., in production), append '/api'.
// Otherwise, default to '/api' for local development.
const baseURL = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL}/api` 
  : '/api';

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('veritas_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear local auth state and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('veritas_token');
      localStorage.removeItem('veritas_user');
      // Redirect to login (avoid circular import — use window directly)
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export default api;
