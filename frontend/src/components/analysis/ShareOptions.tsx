import React, { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
  Snackbar,
  Alert,
  IconButton,
  Tooltip,
  CircularProgress,
  Typography,
  Link,
  FormControl,
  FormControlLabel,
  Checkbox,
  Select,
  MenuItem,
  InputLabel,
} from '@mui/material';
import {
  Share as ShareIcon,
  Download as DownloadIcon,
  FileCopy as CopyIcon,
  Email as EmailIcon,
  Password as PasswordIcon,
} from '@mui/icons-material';
import { useAuthContext } from '../../contexts/AuthContext';
import { API_BASE_URL } from '../../config';

interface ShareOptionsProps {
  analysisId: number;
  githubUsername: string;
}

const ShareOptions: React.FC<ShareOptionsProps> = ({ analysisId, githubUsername }) => {
  const { user } = useAuthContext();
  const [shareDialogOpen, setShareDialogOpen] = useState<boolean>(false);
  const [downloadDialogOpen, setDownloadDialogOpen] = useState<boolean>(false);
  const [shareLink, setShareLink] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [snackbarOpen, setSnackbarOpen] = useState<boolean>(false);
  const [snackbarMessage, setSnackbarMessage] = useState<string>('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');
  const [expirationDays, setExpirationDays] = useState<number>(30);
  const [isPublic, setIsPublic] = useState<boolean>(true);
  const [requiresPasscode, setRequiresPasscode] = useState<boolean>(false);
  const [passcode, setPasscode] = useState<string>('');
  const [downloadFormat, setDownloadFormat] = useState<'pdf' | 'json'>('pdf');
  
  const handleShareOpen = () => {
    setShareDialogOpen(true);
  };
  
  const handleShareClose = () => {
    setShareDialogOpen(false);
  };
  
  const handleDownloadOpen = () => {
    setDownloadDialogOpen(true);
  };
  
  const handleDownloadClose = () => {
    setDownloadDialogOpen(false);
  };
  
  const handleShareCreate = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/share/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          analysis_id: analysisId,
          expires_in_days: expirationDays,
          is_public: isPublic,
          requires_passcode: requiresPasscode,
          passcode: requiresPasscode ? passcode : undefined,
          email: user?.email
        })
      });
      
      if (!response.ok) {
        throw new Error(`Error creating share link: ${response.statusText}`);
      }
      
      const data = await response.json();
      setShareLink(data.share_url);
      setSnackbarMessage('Share link created successfully!');
      setSnackbarSeverity('success');
      setSnackbarOpen(true);
    } catch (error) {
      console.error('Error creating share link:', error);
      setSnackbarMessage('Failed to create share link. Please try again.');
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleCopyToClipboard = () => {
    navigator.clipboard.writeText(shareLink)
      .then(() => {
        setSnackbarMessage('Link copied to clipboard!');
        setSnackbarSeverity('success');
        setSnackbarOpen(true);
      })
      .catch((error) => {
        console.error('Error copying to clipboard:', error);
        setSnackbarMessage('Failed to copy link. Please try again.');
        setSnackbarSeverity('error');
        setSnackbarOpen(true);
      });
  };
  
  const handleEmailShare = () => {
    const subject = encodeURIComponent(`CommitIQ Analysis for ${githubUsername}`);
    let body = encodeURIComponent(`Check out this GitHub analysis of ${githubUsername} conducted with CommitIQ:\n\n${shareLink}\n\nThis link ${expirationDays > 0 ? `will expire in ${expirationDays} days` : 'never expires'}.`);
    
    if (requiresPasscode) {
      body += encodeURIComponent(`\n\nThis link is protected with a passcode. Please use the following passcode to access it: ${passcode}`);
    }
    
    window.open(`mailto:?subject=${subject}&body=${body}`);
  };
  
  const handleDownload = () => {
    setIsLoading(true);
    try {
      // Using the new download endpoint
      window.open(`${API_BASE_URL}/api/download/report/${analysisId}?format=${downloadFormat}`, '_blank');
      setSnackbarMessage('Download initiated!');
      setSnackbarSeverity('success');
      setSnackbarOpen(true);
      setDownloadDialogOpen(false);
    } catch (error) {
      console.error('Error initiating download:', error);
      setSnackbarMessage('Failed to download. Please try again.');
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };

  // Generate a random passcode when the user toggles the option
  const handleRequiresPasscodeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    setRequiresPasscode(checked);
    
    // Generate a random passcode if checked and no passcode exists
    if (checked && !passcode) {
      const randomPasscode = Math.random().toString(36).substring(2, 8).toUpperCase();
      setPasscode(randomPasscode);
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, mt: 3, mb: 3 }}>
      <Button
        variant="outlined"
        startIcon={<ShareIcon />}
        onClick={handleShareOpen}
        color="primary"
      >
        Share Analysis
      </Button>
      
      <Button
        variant="outlined"
        startIcon={<DownloadIcon />}
        onClick={handleDownloadOpen}
        color="secondary"
      >
        Download Report
      </Button>
      
      {/* Share Dialog */}
      <Dialog open={shareDialogOpen} onClose={handleShareClose} maxWidth="md" fullWidth>
        <DialogTitle>Share GitHub Analysis</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 3 }}>
            Create a shareable link for the GitHub analysis of <strong>{githubUsername}</strong>. 
            You can set an expiration date for the link and share it with colleagues.
          </DialogContentText>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 2 }}>
            <FormControl fullWidth>
              <InputLabel id="expiration-days-label">Link Expiration</InputLabel>
              <Select
                labelId="expiration-days-label"
                value={expirationDays}
                label="Link Expiration"
                onChange={(e) => setExpirationDays(Number(e.target.value))}
              >
                <MenuItem value={7}>7 days</MenuItem>
                <MenuItem value={30}>30 days</MenuItem>
                <MenuItem value={90}>90 days</MenuItem>
                <MenuItem value={365}>1 year</MenuItem>
              </Select>
            </FormControl>
            
            <FormControlLabel
              control={
                <Checkbox 
                  checked={isPublic}
                  onChange={(e) => setIsPublic(e.target.checked)}
                  color="primary"
                />
              }
              label="Public link (anyone with the link can view)"
            />
            
            <FormControlLabel
              control={
                <Checkbox 
                  checked={requiresPasscode}
                  onChange={handleRequiresPasscodeChange}
                  color="primary"
                />
              }
              label="Require passcode to access"
            />
            
            {requiresPasscode && (
              <TextField
                fullWidth
                label="Passcode"
                value={passcode}
                onChange={(e) => setPasscode(e.target.value)}
                variant="outlined"
                helperText="Share this passcode separately for extra security"
                InputProps={{
                  startAdornment: <PasswordIcon color="action" sx={{ mr: 1 }} />,
                }}
              />
            )}
            
            {shareLink ? (
              <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>Share Link:</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
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
                <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                  {expirationDays > 0 
                    ? `This link will expire in ${expirationDays} days.` 
                    : 'This link never expires.'}
                  {requiresPasscode && ' A passcode is required to access this link.'}
                </Typography>
              </Box>
            ) : (
              <Button
                variant="contained"
                color="primary"
                onClick={handleShareCreate}
                disabled={isLoading}
                startIcon={isLoading ? <CircularProgress size={20} /> : <ShareIcon />}
              >
                Generate Share Link
              </Button>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleShareClose}>Close</Button>
        </DialogActions>
      </Dialog>
      
      {/* Download Dialog */}
      <Dialog open={downloadDialogOpen} onClose={handleDownloadClose}>
        <DialogTitle>Download GitHub Analysis</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Download the GitHub analysis for <strong>{githubUsername}</strong> in your preferred format.
          </DialogContentText>
          
          <FormControl fullWidth sx={{ mt: 3 }}>
            <InputLabel id="format-label">Download Format</InputLabel>
            <Select
              labelId="format-label"
              value={downloadFormat}
              label="Download Format"
              onChange={(e) => setDownloadFormat(e.target.value as 'pdf' | 'json')}
            >
              <MenuItem value="pdf">PDF Report</MenuItem>
              <MenuItem value="json">JSON Data</MenuItem>
            </Select>
          </FormControl>
          
          <Typography variant="caption" sx={{ mt: 2, display: 'block' }}>
            {downloadFormat === 'pdf' ? (
              <>PDF reports include formatted data, visualizations, and are perfect for sharing with stakeholders.</>
            ) : (
              <>JSON data contains the raw analysis results for further processing or integration.</>
            )}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDownloadClose}>Cancel</Button>
          <Button 
            onClick={handleDownload}
            variant="contained" 
            color="primary"
            disabled={isLoading}
            startIcon={isLoading ? <CircularProgress size={20} /> : <DownloadIcon />}
          >
            Download
          </Button>
        </DialogActions>
      </Dialog>
      
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