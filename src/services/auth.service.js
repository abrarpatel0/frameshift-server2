import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import UserModel from '../models/user.model.js';
import VerificationTokenModel from '../models/verificationToken.model.js';
import { query } from '../config/database.js';
import emailService from './email.service.js';
import logger from '../utils/logger.js';

const JWT_SECRET = process.env.JWT_SECRET;
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '7d';
const BCRYPT_ROUNDS = 10;

class AuthService {
  /**
   * Sanitize user object for returning to client
   * @param {Object} user - User object
   * @returns {Object} Sanitized user
   */
  static sanitizeUser(user) {
    if (!user) return null;
    const { password_hash, github_access_token, ...sanitizedUser } = user;
    return sanitizedUser;
  }

  /**
   * Hash password
   * @param {string} password - Plain text password
   * @returns {Promise<string>} Hashed password
   */
  static async hashPassword(password) {
    const salt = await bcrypt.genSalt(BCRYPT_ROUNDS);
    return bcrypt.hash(password, salt);
  }

  /**
   * Compare password
   * @param {string} password - Plain text password
   * @param {string} hash - Hashed password
   * @returns {Promise<boolean>} True if match
   */
  static async comparePassword(password, hash) {
    if (!password || !hash) return false;
    return bcrypt.compare(password, hash);
  }

  /**
   * Generate JWT token
   * @param {Object} payload - Token payload
   * @returns {string} JWT token
   */
  static generateToken(payload) {
    return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
  }

  /**
   * Verify JWT token
   * @param {string} token - JWT token
   * @returns {Object} Decoded token
   */
  static verifyToken(token) {
    try {
      return jwt.verify(token, JWT_SECRET);
    } catch (error) {
      throw new Error('Invalid or expired token');
    }
  }

  /**
   * Register new user with email/password and send verification email
   * @param {Object} userData - User registration data
   * @returns {Promise<Object>} User and token
   */
  static async registerWithVerification(userData) {
    const { email, password, full_name } = userData;

    // Check if user already exists
    const existingUser = await UserModel.findByEmail(email);
    if (existingUser) {
      const error = new Error('User with this email already exists');
      error.statusCode = 400;
      throw error;
    }

    // Hash password
    const password_hash = await this.hashPassword(password);

    // Create user with email auth provider
    const user = await UserModel.create({
      email,
      password_hash,
      full_name,
      auth_provider: 'email',
      email_verified: false,
    });

    // Generate verification token (24 hours)
    const verificationToken = await VerificationTokenModel.create(
      user.id,
      'email_verification',
      60 * 24
    );

    // Send welcome email with verification link
    try {
      await emailService.sendWelcomeEmail(this.sanitizeUser(user), verificationToken.token);
      logger.info(`Welcome email sent to user: ${user.id}`);
    } catch (error) {
      logger.error(`Failed to send welcome email to ${email} (User ID: ${user.id}):`, error);
      // We don't throw here to avoid failing registration if only email fails
    }

    // Generate JWT token
    const token = this.generateToken({
      userId: user.id,
      email: user.email,
    });

    logger.info(`New user registered and verification email sent: ${email}`);

    return {
      user: this.sanitizeUser(user),
      token,
    };
  }



  /**
   * Login user with email/password
   * @param {string} email - User email
   * @param {string} password - User password
   * @returns {Promise<Object>} User and token
   */
  static async login(email, password) {
    // Find user using method that returns password_hash
    const user = await UserModel.findByEmailWithPassword(email);
    if (!user) {
      const error = new Error('Invalid email or password');
      error.statusCode = 401;
      throw error;
    }

    // Check if user has password (not OAuth-only user)
    if (!user.password_hash) {
      const error = new Error('Please login using GitHub OAuth');
      error.statusCode = 401;
      throw error;
    }

    // Verify password
    const isPasswordValid = await this.comparePassword(password, user.password_hash);
    if (!isPasswordValid) {
      const error = new Error('Invalid email or password');
      error.statusCode = 401;
      throw error;
    }

    // Update last login
    await UserModel.updateLastLogin(user.id);

    // Generate token
    const token = this.generateToken({
      userId: user.id,
      email: user.email,
    });

    logger.info(`User logged in: ${email}`);

    return {
      user: this.sanitizeUser(user),
      token,
    };
  }

  /**
   * Request password reset
   * @param {string} email - User email
   * @returns {Promise<boolean>} Success indicator
   */
  static async requestPasswordReset(email) {
    const user = await UserModel.findByEmail(email);

    // To prevent email enumeration, we return true even if user not found
    if (!user) {
      logger.warn(`Password reset requested for non-existent email: ${email}`);
      return true;
    }

    // Only allow password reset for users with password_hash
    if (user.auth_provider !== 'email') {
      logger.warn(`Password reset requested for OAuth user: ${email}`);
      return true; // Still return true for security
    }

    // Generate reset token (15 mins)
    const resetToken = await VerificationTokenModel.create(
      user.id,
      'password_reset',
      15
    );

    // Send reset email
    try {
      await emailService.sendPasswordResetEmail(this.sanitizeUser(user), resetToken.token);
      logger.info(`Password reset email sent to user: ${user.id}`);
    } catch (error) {
      logger.error(`Failed to send password reset email to ${email}:`, error);
      throw new Error('Failed to send reset email. Please try again later.');
    }

    return true;
  }

  /**
   * Reset password using token
   * @param {string} token - Reset token
   * @param {string} newPassword - New password
   * @returns {Promise<boolean>} Success indicator
   */
  static async resetPassword(token, newPassword) {
    // Find valid token
    const verificationToken = await VerificationTokenModel.findByToken(token, 'password_reset');

    if (!verificationToken) {
      const error = new Error('Invalid or expired reset token');
      error.statusCode = 400;
      throw error;
    }

    if (new Date(verificationToken.expires_at) < new Date()) {
      const error = new Error('Reset token has expired');
      error.statusCode = 400;
      throw error;
    }

    // Hash new password
    const password_hash = await this.hashPassword(newPassword);

    // Update user password
    await UserModel.update(verificationToken.user_id, {
      password_hash
    });

    // Mark token as used
    await VerificationTokenModel.markAsUsed(verificationToken.id);

    logger.info(`Password reset completed for user ID: ${verificationToken.user_id}`);

    return true;
  }

  /**
   * Verify email address
   * @param {string} token - Verification token
   * @returns {Promise<boolean>} Success indicator
   */
  static async verifyEmail(token) {
    const verificationToken = await VerificationTokenModel.findByToken(token, 'email_verification');

    if (!verificationToken) {
      const error = new Error('Invalid or expired verification token');
      error.statusCode = 400;
      throw error;
    }

    if (new Date(verificationToken.expires_at) < new Date()) {
      const error = new Error('Verification token has expired');
      error.statusCode = 400;
      throw error;
    }

    // Update user email_verified status
    await UserModel.update(verificationToken.user_id, {
      email_verified: true
    });

    // Mark token as used
    await VerificationTokenModel.markAsUsed(verificationToken.id);

    logger.info(`Email verified for user ID: ${verificationToken.user_id}`);

    return true;
  }

  /**
   * Resend verification email
   * @param {string} email - User email
   * @returns {Promise<boolean>} Success indicator
   */
  static async resendVerification(userId) {
    const user = await UserModel.findById(userId);

    if (!user) {
      const error = new Error('User not found');
      error.statusCode = 404;
      throw error;
    }

    if (user.email_verified) {
      const error = new Error('Email is already verified');
      error.statusCode = 400;
      throw error;
    }

    // Check if there's a recent active token to prevent spam
    const existingTokens = await query(
      `SELECT COUNT(*) FROM verification_tokens
       WHERE user_id = $1 AND type = 'email_verification'
       AND used = false AND expires_at > NOW()
       AND created_at > NOW() - INTERVAL '15 minutes'`,
      [user.id]
    );

    if (parseInt(existingTokens.rows[0].count) > 0) {
      const error = new Error('Please wait 15 minutes before requesting another verification email');
      error.statusCode = 429;
      throw error;
    }

    // Generate new verification token (24 hours)
    const verificationToken = await VerificationTokenModel.create(
      user.id,
      'email_verification',
      60 * 24
    );

    // Send email
    try {
      await emailService.sendVerificationEmail(this.sanitizeUser(user), verificationToken.token);
      logger.info(`Resent verification email to user: ${user.id}`);
    } catch (error) {
      logger.error(`Failed to resend verification email to ${user.email}:`, error);
      throw new Error('Failed to send verification email. Please try again later.');
    }

    return true;
  }

  /**
   * Handle GitHub OAuth login/registration
   * @param {Object} githubProfile - GitHub user profile data
   * @returns {Promise<Object>} User and token
   */
  static async handleGithubAuth(githubProfile) {
    const { id: githubId, username, email, name, avatarUrl, accessToken } = githubProfile;

    // First try to find user by GitHub ID
    let user = await UserModel.findByGithubId(githubId);

    if (user) {
      // User exists, update token and last login
      await UserModel.update(user.id, {
        github_access_token: accessToken,
        github_username: username,
        avatar_url: user.avatar_url || avatarUrl,
        last_login: new Date()
      });
      user = await UserModel.findById(user.id);
      logger.info(`User logged in via GitHub: ${user.id}`);
    } else {
      // Check if user exists with this email
      if (email) {
        user = await UserModel.findByEmail(email);

        if (user) {
          // Link GitHub to existing account
          user = await UserModel.linkGithubAccount(user.id, githubProfile);
          logger.info(`GitHub linked to existing account: ${user.id}`);
        } else {
          // Create new user
          user = await UserModel.create({
            email: email || `${username}@users.noreply.github.com`,
            full_name: name || username,
            github_id: githubId,
            github_username: username,
            github_access_token: accessToken,
            avatar_url: avatarUrl,
            auth_provider: 'github'
          });
          logger.info(`New user created via GitHub: ${user.id}`);
        }
      } else {
        // Create new user without email (rare from GitHub if scopes are right)
        user = await UserModel.create({
          email: `${username}@users.noreply.github.com`,
          full_name: name || username,
          github_id: githubId,
          github_username: username,
          github_access_token: accessToken,
          avatar_url: avatarUrl,
          auth_provider: 'github'
        });
        logger.info(`New user created via GitHub (no email): ${user.id}`);
      }
    }

    // Generate token
    const token = this.generateToken({
      userId: user.id,
      email: user.email,
    });

    return {
      user: this.sanitizeUser(user),
      token,
    };
  }

  /**
   * Ensure JWT_SECRET is configured
   */
  static validateConfig() {
    if (!JWT_SECRET) {
      logger.error('CRITICAL: JWT_SECRET environment variable is not set!');
      throw new Error('Server configuration error: JWT_SECRET is missing');
    }
  }
}

// Ensure config is valid at startup
AuthService.validateConfig();

export default AuthService;
