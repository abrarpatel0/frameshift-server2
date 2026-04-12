import AuthService from '../services/auth.service.js';
import asyncHandler from '../utils/asyncHandler.js';

// Import GitHub OAuth functions
export { initiateGithubAuth, githubCallback } from './github.controller.js';

/**
 * Register new user
 * POST /api/auth/register
 */
export const register = asyncHandler(async (req, res) => {
  const { email, password, full_name } = req.body;

  // Validate input
  if (!email || !password) {
    return res.status(400).json({
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Email and password are required',
      },
    });
  }

  // Register user with email verification
  const result = await AuthService.registerWithVerification({ email, password, full_name });

  // Set JWT as HttpOnly cookie (token NOT returned in JSON)
  const isProduction = process.env.NODE_ENV === 'production';
  res.cookie('token', result.token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: isProduction ? 'none' : 'strict',
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
  });

  res.status(201).json({
    success: true,
    data: {
      user: result.user,
    },
    message: 'Registration successful. Please check your email to verify your account.',
  });
});

/**
 * Login user
 * POST /api/auth/login
 */
export const login = asyncHandler(async (req, res) => {
  const { email, password } = req.body;

  // Validate input
  if (!email || !password) {
    return res.status(400).json({
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Email and password are required',
      },
    });
  }

  // Login user
  const result = await AuthService.login(email, password);

  // Set JWT as HttpOnly cookie (token NOT returned in JSON)
  const isProduction = process.env.NODE_ENV === 'production';
  res.cookie('token', result.token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: isProduction ? 'none' : 'strict',
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
  });

  res.json({
    success: true,
    data: {
      user: result.user,
    },
  });
});

/**
 * Logout user
 * POST /api/auth/logout
 */
export const logout = asyncHandler(async (req, res) => {
  // Clear the httpOnly cookie
  const isProduction = process.env.NODE_ENV === 'production';
  res.clearCookie('token', {
    httpOnly: true,
    secure: isProduction,
    sameSite: isProduction ? 'none' : 'strict',
  });

  res.json({
    success: true,
    message: 'Logged out successfully',
  });
});

/**
 * Refresh token
 * POST /api/auth/refresh
 */
export const refreshToken = asyncHandler(async (req, res) => {
  const { userId, email } = req.user;

  // Check if token expires within 30 minutes
  const tokenData = req.cookies?.token ? req.parsedToken : null;
  if (tokenData && tokenData.exp) {
    const expiresIn = (tokenData.exp * 1000) - Date.now();
    if (expiresIn > 30 * 60 * 1000) {
      // Token still valid for more than 30 minutes
      return res.json({ success: true, message: 'Token still valid' });
    }
  }

  // Generate new token
  const newToken = AuthService.generateToken({ userId, email });

  // Set new JWT as HttpOnly cookie
  const isProduction = process.env.NODE_ENV === 'production';
  res.cookie('token', newToken, {
    httpOnly: true,
    secure: isProduction,
    sameSite: isProduction ? 'none' : 'strict',
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
  });

  res.json({
    success: true,
    message: 'Token refreshed',
  });
});

/**
 * Get current user
 * GET /api/auth/me
 */
export const getCurrentUser = asyncHandler(async (req, res) => {
  const UserModel = (await import('../models/user.model.js')).default;
  const user = await UserModel.findById(req.user.userId);

  if (!user) {
    return res.status(404).json({
      success: false,
      error: {
        message: 'User not found',
      },
    });
  }

  res.json({
    success: true,
    data: {
      user,
    },
  });
});

/**
 * Check current auth status (optional auth - doesn't fail if unauthenticated)
 * GET /api/auth/check
 */
export const checkAuth = asyncHandler(async (req, res) => {
  // If req.user is null, user is not authenticated (but we still return 200)
  if (!req.user) {
    return res.json({
      success: true,
      data: {
        authenticated: false,
        user: null,
      },
    });
  }

  // User is authenticated, fetch full user data
  const UserModel = (await import('../models/user.model.js')).default;
  const user = await UserModel.findById(req.user.userId);

  if (!user) {
    return res.json({
      success: true,
      data: {
        authenticated: false,
        user: null,
      },
    });
  }

  res.json({
    success: true,
    data: {
      authenticated: true,
      user,
    },
  });
});

/**
 * Verify email
 * POST /api/auth/verify-email
 */
export const verifyEmail = asyncHandler(async (req, res) => {
  const { token } = req.body;

  if (!token) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Verification token is required',
      },
    });
  }

  const user = await AuthService.verifyEmail(token);

  res.json({
    success: true,
    data: {
      user,
    },
    message: 'Email verified successfully',
  });
});

/**
 * Resend verification email
 * POST /api/auth/resend-verification
 */
export const resendVerification = asyncHandler(async (req, res) => {
  const { userId } = req.user;

  await AuthService.resendVerification(userId);

  res.json({
    success: true,
    message: 'Verification email sent successfully',
  });
});

/**
 * Request password reset
 * POST /api/auth/forgot-password
 */
export const forgotPassword = asyncHandler(async (req, res) => {
  const { email } = req.body;

  if (!email) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Email is required',
      },
    });
  }

  await AuthService.requestPasswordReset(email);

  // Always return success (don't reveal if email exists)
  res.json({
    success: true,
    message: 'If the email exists, a password reset link has been sent',
  });
});

/**
 * Reset password with token
 * POST /api/auth/reset-password
 */
export const resetPassword = asyncHandler(async (req, res) => {
  const { token, password } = req.body;

  if (!token || !password) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Token and password are required',
      },
    });
  }

  // Validate password strength
  if (password.length < 8) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Password must be at least 8 characters long',
      },
    });
  }

  const user = await AuthService.resetPassword(token, password);

  res.json({
    success: true,
    data: {
      user,
    },
    message: 'Password reset successfully',
  });
});

/**
 * Change password (when logged in)
 * POST /api/auth/change-password
 */
export const changePassword = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const { currentPassword, newPassword } = req.body;

  if (!currentPassword || !newPassword) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Current password and new password are required',
      },
    });
  }

  // Validate password strength
  if (newPassword.length < 8) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'New password must be at least 8 characters long',
      },
    });
  }

  const user = await AuthService.changePassword(userId, currentPassword, newPassword);

  res.json({
    success: true,
    data: {
      user,
    },
    message: 'Password changed successfully',
  });
});
