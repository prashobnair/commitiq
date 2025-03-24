import React, { createContext, useState, useContext, ReactNode, useCallback } from 'react';
import { AnalysisResponse } from '../types/analysis';
import { analyzeGitHubProfile } from '../utils/api';

interface AnalysisContextType {
  loading: boolean;
  error: string | null;
  analysisData: AnalysisResponse | null;
  analyzeProfile: (username: string) => Promise<void>;
  resetAnalysis: () => void;
}

// Create context with default values
const AnalysisContext = createContext<AnalysisContextType>({
  loading: false,
  error: null,
  analysisData: null,
  analyzeProfile: async () => {},
  resetAnalysis: () => {},
});

// Provider component that wraps the app
export const AnalysisProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisResponse | null>(null);

  const analyzeProfile = useCallback(async (username: string) => {
    console.log('[AnalysisContext] Starting analysis for:', username);
    if (!username.trim()) return;

    console.log('[AnalysisContext] Setting loading state');
    setLoading(true);
    setError(null);
    
    const { data, error: apiError } = await analyzeGitHubProfile(username.trim());
    console.log('[AnalysisContext] API response received:', { data: !!data, error: apiError });
    
    if (apiError) {
      console.log('[AnalysisContext] Setting error state:', apiError);
      setError(apiError);
      setAnalysisData(null);
    } else if (data) {
      console.log('[AnalysisContext] Setting analysis data');
      setAnalysisData(data);
      setError(null);
    }
    
    console.log('[AnalysisContext] Analysis complete, clearing loading state');
    setLoading(false);
  }, []);

  const resetAnalysis = useCallback(() => {
    console.log('[AnalysisContext] Resetting analysis state');
    setAnalysisData(null);
    setError(null);
  }, []);

  const value = {
    loading,
    error,
    analysisData,
    analyzeProfile,
    resetAnalysis,
  };

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
};

// Custom hook to use the analysis context
//export const useAnalysisContext = () => useContext(AnalysisContext); 
export const useAnalysisContext = () => {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error('useAnalysisContext must be used within an AnalysisProvider');
  }
  return context;
}; 