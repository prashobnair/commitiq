import axios, { AxiosError } from 'axios';
import { AnalysisResponse } from '../types/analysis';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';
console.log('[API] Using API base URL:', API_BASE_URL);

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
  const endpoint = `/analyze/${encodeURIComponent(username)}`;
  console.log('[API] Making request to:', API_BASE_URL + endpoint);
  
  try {
    //const response = await api.get<AnalysisResponse>(`/analyze/${encodeURIComponent(username)}`);
    console.log('[API] Sending analyze request for username:', username);
    const response = await api.get<AnalysisResponse>(endpoint);
    console.log('[API] Received response:', response.status, response.statusText);
    
    // Validate the response data structure
    if (!response.data || !response.data.analysis) {
      console.error('[API] Invalid response format:', response.data);
      return { error: 'Invalid response format from server' };
    }
    
    console.log('[API] Analysis successful');
    return { data: response.data };
  } catch (err) {
    const error = err as AxiosError;
    console.error('[API] Request failed:', error);
    
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.error('[API] Server responded with error:', {
        status: error.response.status,
        statusText: error.response.statusText,
        data: error.response.data
      });
      
      // Handle common GitHub API error scenarios
      const statusCode = error.response.status;
      const responseData = error.response.data as { error?: string };
      
      if (statusCode === 400) {
        return { 
          error: 'Invalid username format. Please try again.'
        };
      } else if (statusCode === 404) {
        return { 
          error: 'Username not found. Please check and try again.'
        };
      } else if (statusCode === 403) {
        return { 
          error: 'Too many requests. Please try again later.'
        };
      } else {
        return {
          error: 'Unable to analyze profile at this time. Please try again later.'
        };
      }
    } else if (error.request) {
      // The request was made but no response was received
      console.error('[API] No response received:', error.request);
      return { error: 'Connection issue. Please check your internet and try again.' };
    } else {
      // Something happened in setting up the request
      console.error('[API] Request setup error:', error.message);
      return { error: 'An unexpected issue occurred. Please try again.' };
    }
  }
};

export default api; 