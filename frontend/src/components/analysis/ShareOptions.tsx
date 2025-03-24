import React, { useState } from 'react';
import {
  Box,
  Button,
  Snackbar,
  Alert,
  IconButton,
  Tooltip,
  CircularProgress,
  TextField,
} from '@mui/material';
import {
  Share as ShareIcon,
  Download as DownloadIcon,
  FileCopy as CopyIcon,
  Email as EmailIcon,
} from '@mui/icons-material';
import { API_BASE_URL } from '../../config';
import logger from '../../utils/logger';
import { trackEvent } from '../../utils/analytics';

interface ShareOptionsProps {
  analysisId: number;
  githubUsername: string;
}

const ShareOptions: React.FC<ShareOptionsProps> = ({ analysisId, githubUsername }) => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [snackbarOpen, setSnackbarOpen] = useState<boolean>(false);
  const [snackbarMessage, setSnackbarMessage] = useState<string>('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'info' | 'warning'>('success');
  const [shareLink, setShareLink] = useState<string>('');
  const [shareLinkDialogOpen, setShareLinkDialogOpen] = useState<boolean>(false);
  
  const handleShareClick = async () => {
    setIsLoading(true);
    try {
      // Create a direct frontend URL that will analyze this username
      const host = window.location.origin;
      const shareUrl = `${host}/shared/${githubUsername}`;
      
      // Track share action in Google Analytics
      trackEvent(
        'Sharing',
        'Created Share Link',
        githubUsername
      );
      
      setShareLink(shareUrl);
      setShareLinkDialogOpen(true);
      setSnackbarMessage('Share link created successfully!');
      setSnackbarSeverity('success');
      setSnackbarOpen(true);
    } catch (error) {
      logger.error('Error creating share link:', error);
      
      // Track error in Google Analytics
      trackEvent(
        'Error',
        'Share Link Creation Failed',
        githubUsername
      );
      
      setSnackbarMessage('Failed to create share link. Please try again.');
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleDownload = () => {
    // Track PDF download in Google Analytics
    trackEvent(
      'Analysis',
      'PDF Download',
      githubUsername
    );
    
    // Use username-based approach instead of analysis ID to handle placeholder IDs
    // This ensures downloads work even if the analysis hasn't been fully stored in the database yet
    window.open(`${API_BASE_URL}/download/report?username=${encodeURIComponent(githubUsername)}&format=pdf`, '_blank');
  };
  
  const handleCopyToClipboard = () => {
    navigator.clipboard.writeText(shareLink)
      .then(() => {
        // Track copy action in Google Analytics
        trackEvent(
          'Sharing',
          'Copied Share Link',
          githubUsername
        );
        
        setSnackbarMessage('Link copied to clipboard!');
        setSnackbarSeverity('success');
        setSnackbarOpen(true);
      })
      .catch((error) => {
        logger.error('Error copying to clipboard:', error);
        
        // Track error in Google Analytics
        trackEvent(
          'Error',
          'Copy Link Failed',
          githubUsername
        );
        
        setSnackbarMessage('Failed to copy link. Please try again.');
        setSnackbarSeverity('error');
        setSnackbarOpen(true);
      });
  };
  
  const handleEmailShare = () => {
    // Track email share action in Google Analytics
    trackEvent(
      'Sharing',
      'Email Share',
      githubUsername
    );
    
    const subject = encodeURIComponent(`CommitIQ Analysis for ${githubUsername}`);
    const body = encodeURIComponent(`Check out this GitHub analysis of ${githubUsername} conducted with CommitIQ:\n\n${shareLink}`);
    window.open(`mailto:?subject=${subject}&body=${body}`);
  };

  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };

  const handleCloseLinkDialog = () => {
    setShareLinkDialogOpen(false);
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, mt: 3, mb: 3 }}>
      <Button
        variant="outlined"
        startIcon={isLoading ? <CircularProgress size={20} /> : <ShareIcon />}
        onClick={handleShareClick}
        color="primary"
        disabled={isLoading}
      >
        Share Analysis
      </Button>
      
      <Button
        variant="outlined"
        startIcon={<DownloadIcon />}
        onClick={handleDownload}
        color="secondary"
        disabled={isLoading}
      >
        Download PDF
      </Button>
      
      {/* Share Link Dialog */}
      {shareLinkDialogOpen && (
        <Box 
          sx={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            bgcolor: 'rgba(0,0,0,0.5)', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={handleCloseLinkDialog}
        >
          <Box 
            sx={{ 
              bgcolor: 'background.paper', 
              p: 3, 
              borderRadius: 2, 
              maxWidth: '600px',
              width: '90%',
              boxShadow: 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Share GitHub Analysis</h3>
            <p>Share this link with others to view the GitHub analysis of <strong>{githubUsername}</strong>.</p>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
              <TextField
                fullWidth
                value={shareLink}
                InputProps={{
                  readOnly: true,
                }}
              />
              <Tooltip title="Copy to clipboard">
                <IconButton onClick={handleCopyToClipboard} color="primary">
                  <CopyIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Share via email">
                <IconButton onClick={handleEmailShare} color="primary">
                  <EmailIcon />
                </IconButton>
              </Tooltip>
            </Box>
            
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
              <Button variant="contained" onClick={handleCloseLinkDialog}>
                Close
              </Button>
            </Box>
          </Box>
        </Box>
      )}
      
      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
      >
        <Alert 
          onClose={handleSnackbarClose} 
          severity={snackbarSeverity}
          sx={{ width: '100%' }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ShareOptions; 