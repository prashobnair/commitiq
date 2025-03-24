/**
 * Logger utility that respects the production environment setting
 * Prevents console logs in production environment
 */

// Determine if we're in production mode
const isProduction = process.env.NODE_ENV === 'production';

/**
 * Logger utility that wraps console methods and disables them in production
 */
const logger = {
  /**
   * Log information - disabled in production
   */
  log: (...args: any[]): void => {
    if (!isProduction) {
      console.log(...args);
    }
  },
  
  /**
   * Log warnings - enabled in all environments but without data dumps
   */
  warn: (...args: any[]): void => {
    if (isProduction) {
      // In production, only log string messages, not data objects
      const safeArgs = args.map(arg => 
        typeof arg === 'string' ? arg : 
        (arg instanceof Error ? arg.message : '[data redacted in production]')
      );
      console.warn(...safeArgs);
    } else {
      console.warn(...args);
    }
  },
  
  /**
   * Log errors - enabled in all environments but without sensitive data
   */
  error: (...args: any[]): void => {
    if (isProduction) {
      // In production, only log string messages, not data objects
      const safeArgs = args.map(arg => 
        typeof arg === 'string' ? arg : 
        (arg instanceof Error ? arg.message : '[data redacted in production]')
      );
      console.error(...safeArgs);
    } else {
      console.error(...args);
    }
  },
  
  /**
   * Safely log JSON data - completely disabled in production
   */
  json: (label: string, data: any): void => {
    if (!isProduction) {
      console.log(label, JSON.stringify(data, null, 2));
    }
  }
};

export default logger; 