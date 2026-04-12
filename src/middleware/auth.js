import AuthService from '../services/auth.service.js';
import logger from '../utils/logger.js';

/**
 * Middleware to authenticate JWT token from HttpOnly cookie
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next function
 */
export const authenticateToken = async (req, res, next) => {
  try {
    // Get token from HttpOnly cookie (not Authorization header)
    const token = req.cookies?.token;

    if (!token) {
      return res.status(401).json({
        success: false,
        error: {
          code: 'UNAUTHORIZED',
          message: 'Access token required',
        },
      });
    }

    // Verify token
    const decoded = AuthService.verifyToken(token);

    // Attach user info and parsed token to request
    req.user = {
      userId: decoded.userId,
      email: decoded.email,
    };
    req.parsedToken = decoded;

    next();
  } catch (error) {
    logger.error('JWT authentication failed:', error);
    return res.status(401).json({
      success: false,
      error: {
        code: 'UNAUTHORIZED',
        message: 'Invalid or expired token',
      },
    });
  }
};

/**
 * Middleware for optional authentication (doesn't fail if token is missing)
 * Tries to authenticate but continues even if token is absent
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next function
 */
export const authenticateTokenOptional = async (req, res, next) => {
  try {
    // Get token from HttpOnly cookie
    const token = req.cookies?.token;

    if (!token) {
      // No token, but continue anyway (don't fail)
      req.user = null;
      req.parsedToken = null;
      return next();
    }

    // Verify token
    const decoded = AuthService.verifyToken(token);

    // Attach user info and parsed token to request
    req.user = {
      userId: decoded.userId,
      email: decoded.email,
    };
    req.parsedToken = decoded;

    next();
  } catch (error) {
    // Token exists but is invalid, fail silently and continue without user data
    logger.debug('Optional JWT authentication failed:', error.message);
    req.user = null;
    req.parsedToken = null;
    next();
  }
};

export default authenticateToken;
