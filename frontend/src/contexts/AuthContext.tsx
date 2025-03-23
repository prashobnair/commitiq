import React, { createContext, useContext, useState, ReactNode } from 'react';
import logger from '../utils/logger';

interface User {
  email: string | null;
  name?: string | null;
  isAuthenticated: boolean;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, name?: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    // Check if we have user data in localStorage
    const savedUser = localStorage.getItem('commitiq_user');
    if (savedUser) {
      try {
        return JSON.parse(savedUser);
      } catch (error) {
        logger.error('Error parsing saved user data:', error);
        return null;
      }
    }
    return null;
  });

  const login = (email: string, name?: string) => {
    const newUser = {
      email,
      name: name || null,
      isAuthenticated: true
    };
    
    setUser(newUser);
    
    // Save to localStorage
    localStorage.setItem('commitiq_user', JSON.stringify(newUser));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('commitiq_user');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuthContext = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext; 