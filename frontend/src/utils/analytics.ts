import ReactGA from 'react-ga4';

// Initialize Google Analytics
export const initAnalytics = () => {
  ReactGA.initialize('G-C7JDD3X9EW', {
    gaOptions: {
      anonymizeIp: true, // GDPR compliance
      cookieFlags: 'SameSite=None; Secure'
    }
  });
};

// Track page views
export const trackPageView = (path: string) => {
  ReactGA.send({ hitType: 'pageview', page: path });
};

// Track custom events
export const trackEvent = (
  category: string,
  action: string,
  label?: string,
  value?: number
) => {
  ReactGA.event({
    category,
    action,
    label,
    value
  });
};

// Track user engagement
export const trackEngagement = (
  eventName: string,
  params: Record<string, any>
) => {
  ReactGA.gtag('event', eventName, params);
};

// Track errors
export const trackError = (
  errorMessage: string,
  errorSource?: string
) => {
  ReactGA.event({
    category: 'Error',
    action: errorMessage,
    label: errorSource
  });
}; 