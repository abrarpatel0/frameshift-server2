import express from 'express';
import {
  register,
  login,
  logout,
  refreshToken,
  getCurrentUser,
  checkAuth,
  verifyEmail,
  resendVerification,
  forgotPassword,
  resetPassword,
  changePassword,
  initiateGithubAuth,
  githubCallback
} from '../controllers/auth.controller.js';
import { authenticateToken, authenticateTokenOptional } from '../middleware/auth.js';
import { authLimiter } from '../middleware/rateLimiter.js';
import { validateRequest } from '../middleware/validate.js';
import { authSchemas } from '../validation/schemas.js';

const router = express.Router();

// Public routes (with rate limiting)
router.post('/register', authLimiter, validateRequest(authSchemas.register), register);
router.post('/login', authLimiter, validateRequest(authSchemas.login), login);

// Auth check route (optional auth - always returns 200)
router.get('/check', authenticateTokenOptional, checkAuth);

// Email verification routes (public)
router.post('/verify-email', validateRequest(authSchemas.verifyEmail), verifyEmail);
router.post('/forgot-password', authLimiter, validateRequest(authSchemas.forgotPassword), forgotPassword);
router.post('/reset-password', authLimiter, validateRequest(authSchemas.resetPassword), resetPassword);

// GitHub OAuth routes
router.get('/github', initiateGithubAuth);
router.get('/github/callback', githubCallback);

// Protected routes (require authentication)
router.post('/logout', authenticateToken, logout);
router.post('/refresh', authenticateToken, refreshToken);
router.get('/me', authenticateToken, getCurrentUser);
router.post('/resend-verification', authenticateToken, resendVerification);
router.post('/change-password', authenticateToken, validateRequest(authSchemas.changePassword), changePassword);

export default router;
