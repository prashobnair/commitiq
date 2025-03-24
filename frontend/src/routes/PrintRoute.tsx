import React from 'react';
import { useParams, useLocation } from 'react-router-dom';
import PrintPage from '../pages/print/[username]';
import logger from '../utils/logger';

/**
 * Wrapper component for the Next.js style Print page
 * This adapts the Next.js page format to work with React Router
 */
const PrintRoute: React.FC = () => {
  // Extract route parameters for the print page
  const { username } = useParams<{ username: string }>();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const id = searchParams.get('id');
  
  // SECURITY: Console log removed to prevent data exposure
  // console.log(`Rendering print page for username: ${username}, id: ${id}`);
  //logger.log('Rendering print page', { username, id });
  
  // If we don't have both username and id, show an error
  if (!username || !id) {
    return (
      <div>
        <h2>Error: Missing Parameters</h2>
        <p>Both username and id are required to generate a PDF.</p>
      </div>
    );
  }
  
  // Render the actual print page
  return <PrintPage />;
};

export default PrintRoute; 