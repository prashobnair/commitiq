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
import { trackEvent } from '../../utils/analytics';

// API URL - should be in an environment variable in production
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

interface WaitingListModalProps {
  open: boolean;
  onClose: () => void;
}

interface WaitlistResponse {
  status: 'success' | 'already_joined' | 'error';
  message: string;
  error?: string;
}

const WaitingListModal: React.FC<WaitingListModalProps> = ({ open, onClose }) => {
  const theme = useTheme();
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // Form validation for email
  const validateEmail = (email: string): boolean => {
    const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return re.test(email.toLowerCase());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email.trim()) {
      setError('Email is required');
      return;
    }

    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch(`${API_URL}/waitlist/join`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email.trim(),
          company: company.trim() || null,
          feedback: feedback.trim() || null,
        }),
      });

      const data: WaitlistResponse = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to join waiting list');
      }

      // Track successful waitlist signup in Google Analytics
      trackEvent(
        'Waitlist',
        'Signup',
        company ? `Company: ${company}` : 'Individual'
      );

      // Handle different response statuses
      if (data.status === 'already_joined') {
        setMessage(data.message);
      } else {
        setMessage('Thank you for joining our waiting list! We\'ll notify you when we\'re ready.');
      }

      setSuccess(true);
      
      // Reset form after successful submission
      setEmail('');
      setCompany('');
      setFeedback('');
    } catch (err) {
      // Track errors in Google Analytics
      trackEvent(
        'Error',
        'Waitlist Signup Failed',
        err instanceof Error ? err.message : 'Unknown error'
      );
      
      setError(err instanceof Error ? err.message : 'Failed to join waiting list. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setSuccess(false);
      setError('');
      setMessage('');
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
              {message}
            </Alert>
            <Typography variant="body1" sx={{ mb: 2 }}>
              Thank you for your interest in CommitIQ. We're working hard to build a platform that revolutionizes technical recruiting.
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
              sx={{ mb: 2 }}
            />

            <TextField
              margin="dense"
              label="Feature Requests or Feedback (Optional)"
              type="text"
              fullWidth
              multiline
              rows={3}
              variant="outlined"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              disabled={loading}
              placeholder="Let us know what features you'd like to see in CommitIQ"
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