import { useState, useCallback } from 'react';
import { AnalysisResponse } from '../types/analysis';
import { analyzeGitHubProfile } from '../utils/api';

interface UseGitHubAnalysis {
  loading: boolean;
  error: string | null;
  analysisData: AnalysisResponse | null;
  analyzeProfile: (username: string) => Promise<void>;
  resetAnalysis: () => void;
}

export const useGitHubAnalysis = (): UseGitHubAnalysis => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisResponse | null>(null);

  const analyzeProfile = useCallback(async (username: string) => {
    if (!username.trim()) return;

    setLoading(true);
    setError(null);
    
    const { data, error: apiError } = await analyzeGitHubProfile(username.trim());
    
    if (apiError) {
      setError(apiError);
      setAnalysisData(null);
    } else if (data) {
      setAnalysisData(data);
      setError(null);
    }
    
    setLoading(false);
  }, []);

  const resetAnalysis = useCallback(() => {
    setAnalysisData(null);
    setError(null);
  }, []);

  return {
    loading,
    error,
    analysisData,
    analyzeProfile,
    resetAnalysis,
  };
};

export default useGitHubAnalysis; 