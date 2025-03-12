import axios, { AxiosError } from 'axios';
import { AnalysisResponse } from '../types/analysis';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

export const analyzeGitHubProfile = async (
  username: string
): Promise<{ data?: AnalysisResponse; error?: string }> => {
  try {
    const response = await api.get<AnalysisResponse>(`/analyze/${username}`);
    
    // Validate the response data structure
    if (!response.data || !response.data.analysis) {
      return { error: 'Invalid response format from server' };
    }
    
    return { data: response.data };
  } catch (err) {
    const error = err as AxiosError;
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      return {
        error:
          (error.response.data as { error?: string })?.error ||
          'Failed to analyze GitHub profile',
      };
    } else if (error.request) {
      // The request was made but no response was received
      return { error: 'No response from server. Please try again later.' };
    } else {
      // Something happened in setting up the request
      return { error: 'An unexpected error occurred. Please try again.' };
    }
  }
};

export default api; 