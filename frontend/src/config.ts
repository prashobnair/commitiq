/**
 * Configuration settings for the CommitIQ frontend application
 */

// Base URL for API endpoints
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

// Feature flags
export const FEATURES = {
  SHARING_ENABLED: true,
  DOWNLOAD_ENABLED: true,
  DASHBOARD_ENABLED: false, // Set to true when dashboard is ready
};

// Analytics settings
export const ANALYTICS = {
  ENABLED: process.env.REACT_APP_ANALYTICS_ENABLED === 'true',
  TRACKING_ID: process.env.REACT_APP_ANALYTICS_TRACKING_ID || '',
};

// Application info
export const APP_INFO = {
  VERSION: process.env.REACT_APP_VERSION || '1.0.0',
  BUILD_DATE: process.env.REACT_APP_BUILD_DATE || new Date().toISOString(),
  ENVIRONMENT: process.env.NODE_ENV || 'development',
}; 