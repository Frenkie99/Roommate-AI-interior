import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import authService from '../services/authService';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [quota, setQuota] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const applyAuth = useCallback((data) => {
    setUser(data.user || null);
    setQuota(data.quota || null);
  }, []);

  useEffect(() => {
    authService.me().then(applyAuth).catch(() => applyAuth({})).finally(() => setLoading(false));
  }, [applyAuth]);

  const login = useCallback(async (username, password) => {
    const data = await authService.login(username, password);
    applyAuth(data);
    setAuthModalOpen(false);
  }, [applyAuth]);

  const register = useCallback(async (username, password) => {
    const data = await authService.register(username, password);
    applyAuth(data);
    setAuthModalOpen(false);
  }, [applyAuth]);

  const logout = useCallback(async () => {
    await authService.logout().catch(() => {});
    applyAuth({});
  }, [applyAuth]);

  const value = useMemo(() => ({
    user, quota, setQuota, loading, login, register, logout,
    authModalOpen, openAuth: () => setAuthModalOpen(true), closeAuth: () => setAuthModalOpen(false),
  }), [user, quota, loading, login, register, logout, authModalOpen]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
