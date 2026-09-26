import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { login as apiLogin, register as apiRegister } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('veritas_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(() => localStorage.getItem('veritas_token') || null);
  const [loading, setLoading] = useState(false);

  const isAuthenticated = Boolean(token && user);

  const _saveAuth = (data) => {
    localStorage.setItem('veritas_token', data.access_token);
    localStorage.setItem('veritas_user', JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
  };

  const login = useCallback(async (email, password) => {
    setLoading(true);
    try {
      const data = await apiLogin({ email, password });
      _saveAuth(data);
      return { success: true };
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed. Please try again.';
      return { success: false, error: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (name, email, password) => {
    setLoading(true);
    try {
      const data = await apiRegister({ name, email, password });
      _saveAuth(data);
      return { success: true };
    } catch (err) {
      const msg = err.response?.data?.detail || 'Registration failed. Please try again.';
      return { success: false, error: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('veritas_token');
    localStorage.removeItem('veritas_user');
    setToken(null);
    setUser(null);
  }, []);

  const updateUser = useCallback((updatedUser) => {
    localStorage.setItem('veritas_user', JSON.stringify(updatedUser));
    setUser(updatedUser);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, loading, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
