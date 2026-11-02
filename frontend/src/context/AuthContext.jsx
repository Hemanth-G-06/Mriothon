import React, { createContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/authService';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [isLoading, setIsLoading] = useState(true);
  const [isMockMode, setIsMockMode] = useState(false);

  useEffect(() => {
    const initializeAuth = async () => {
      if (authService.isAuthenticated()) {
        try {
          const profile = await authService.getCurrentUser();
          setUser(profile);
        } catch {
          setUser(null);
        }
      } else {
        setUser(null);
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = useCallback(async (usernameOrEmail, password) => {
    setIsLoading(true);
    try {
      const res = await authService.login(usernameOrEmail, password);
      setUser(res.user);
      setIsMockMode(res.isMock);
      return res;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setIsMockMode(false);
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (data) => {
    return await authService.register(data);
  }, []);

  const value = {
    user,
    role: user?.role ? user.role.toLowerCase() : null,
    isAuthenticated: !!user,
    isLoading,
    isMockMode,
    login,
    register,
    logout
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
