// Type declarations for Next.js modules in a non-Next.js project

declare module 'next/router' {
  export function useRouter(): {
    query: Record<string, string | string[] | undefined>;
    push: (url: string) => Promise<boolean>;
    replace: (url: string) => Promise<boolean>;
    prefetch: (url: string) => Promise<void>;
    back: () => void;
    pathname: string;
    asPath: string;
    events: {
      on: (event: string, callback: (...args: any[]) => void) => void;
      off: (event: string, callback: (...args: any[]) => void) => void;
    };
  };
}

declare module 'next/head' {
  import { ReactNode } from 'react';
  
  export default function Head({ children }: { children: ReactNode }): JSX.Element;
} 