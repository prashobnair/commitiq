import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  IconButton,
  useTheme,
  alpha,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';

interface WaitingListModalProps {
  open: boolean;
  onClose: () => void;
}

const WaitingListModal: React.FC<WaitingListModalProps> = ({ open, onClose }) => {
  const theme = useTheme();
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email.trim()) {
      setError('Email is required');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      // In a real implementation, this would be an API call to your backend
      // For MVP, we'll simulate a successful submission
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setSuccess(true);
      // Reset form after successful submission
      setEmail('');
      setCompany('');
    } catch (err) {
      setError('Failed to join waiting list. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setSuccess(false);
      setError('');
      onClose();
    }
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          boxShadow: '0 10px 40px rgba(0,0,0,0.1)',
        }
      }}
    >
      <DialogTitle sx={{ 
        pb: 1,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <Typography variant="h5" fontWeight="bold">
          Join the CommitIQ Waiting List
        </Typography>
        <IconButton 
          edge="end" 
          color="inherit" 
          onClick={handleClose} 
          disabled={loading}
          aria-label="close"
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <DialogContent>
        {success ? (
          <Box sx={{ py: 3, textAlign: 'center' }}>
            <Alert severity="success" sx={{ mb: 2 }}>
              You've been added to our waiting list!
            </Alert>
            <Typography variant="body1" sx={{ mb: 2 }}>
              Thank you for your interest in CommitIQ. We'll notify you as soon as we're ready to onboard new users.
            </Typography>
            <Typography variant="body2" color="textSecondary">
              In the meantime, feel free to try our GitHub profile analyzer to see what insights we can provide.
            </Typography>
          </Box>
        ) : (
          <Box component="form" onSubmit={handleSubmit} sx={{ pt: 1 }}>
            <Typography variant="body1" sx={{ mb: 3 }}>
              Get early access to CommitIQ and revolutionize your technical recruiting process with data-driven developer insights.
            </Typography>
            
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            
            <TextField
              autoFocus
              margin="dense"
              label="Email Address"
              type="email"
              fullWidth
              variant="outlined"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              sx={{ mb: 2 }}
            />
            
            <TextField
              margin="dense"
              label="Company (Optional)"
              type="text"
              fullWidth
              variant="outlined"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              disabled={loading}
              sx={{ mb: 1 }}
            />
            
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1, mb: 2 }}>
              We'll notify you when we're ready to onboard new users. No spam, we promise!
            </Typography>
          </Box>
        )}
      </DialogContent>
      
      {!success && (
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button 
            onClick={handleClose} 
            color="inherit"
            disabled={loading}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit}
            variant="contained" 
            color="primary"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null}
          >
            {loading ? 'Submitting...' : 'Join Waiting List'}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
};

export default WaitingListModal; 