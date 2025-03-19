import React, { ReactNode, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

// Implementation of Next.js useRouter hook for React Router
export function useRouter() {
  const location = useLocation();
  const [query, setQuery] = useState<Record<string, string | string[]>>({});
  
  useEffect(() => {
    // Parse query parameters from URL
    const searchParams = new URLSearchParams(location.search);
    const params: Record<string, string | string[]> = {};
    
    // Extract path parameters too (for [username].tsx style pages)
    const pathParts = location.pathname.split('/');
    const username = pathParts[pathParts.length - 1];
    if (username) {
      params.username = username;
    }
    
    // Extract search parameters
    searchParams.forEach((value, key) => {
      if (params[key]) {
        if (Array.isArray(params[key])) {
          (params[key] as string[]).push(value);
        } else {
          params[key] = [params[key] as string, value];
        }
      } else {
        params[key] = value;
      }
    });
    
    setQuery(params);
  }, [location]);
  
  return {
    query,
    pathname: location.pathname,
    asPath: location.pathname + location.search,
    push: (url: string) => {
      window.history.pushState({}, '', url);
      return Promise.resolve(true);
    },
    replace: (url: string) => {
      window.history.replaceState({}, '', url);
      return Promise.resolve(true);
    },
    prefetch: () => Promise.resolve(),
    back: () => window.history.back(),
    events: {
      on: () => {},
      off: () => {}
    }
  };
}

// Implementation of Next.js Head component
export function Head({ children }: { children: ReactNode }) {
  useEffect(() => {
    // Extract title and meta tags from children
    React.Children.forEach(children, (child) => {
      if (!React.isValidElement(child)) return;
      
      if (child.type === 'title') {
        document.title = child.props.children;
      }
      
      if (child.type === 'meta') {
        const meta = document.createElement('meta');
        Object.entries(child.props).forEach(([key, value]) => {
          meta.setAttribute(key, value as string);
        });
        document.head.appendChild(meta);
        
        return () => {
          document.head.removeChild(meta);
        };
      }
      
      if (child.type === 'style') {
        const style = document.createElement('style');
        style.innerHTML = child.props.children;
        document.head.appendChild(style);
        
        return () => {
          document.head.removeChild(style);
        };
      }
    });
  }, [children]);
  
  return null;
}

export default {
  useRouter,
  Head
}; 