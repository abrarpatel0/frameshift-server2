import rateLimit, { ipKeyGenerator } from 'express-rate-limit';

const isDevelopment = process.env.NODE_ENV !== 'production';
const devOrProd = (devValue, prodValue) => (isDevelopment ? devValue : prodValue);

/**
 * Rate limiter for conversion endpoints
 * Development is intentionally looser to avoid blocking retry-heavy debugging.
 */
export const conversionLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: devOrProd(50, 5),
  message: 'Too many conversion requests from this IP, please try again later',
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: ipKeyGenerator, // Use proper IPv6 support
});

/**
 * Rate limiter for authentication endpoints — per-email basis
 * Max 5 login/register attempts per 15 minutes per email
 * This prevents brute force attacks on specific accounts
 */
export const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: devOrProd(50, 5), // 5 attempts in production
  message: 'Too many authentication attempts. Please try again in 15 minutes.',
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req, res) => {
    // Use email from request body as key (requires cookie-parser or body parsing first)
    // Fall back to IP (with IPv6 support) if no email
    if (req.body?.email) {
      return req.body.email;
    }
    // Use proper IPv6-aware IP keying as fallback
    return ipKeyGenerator(req, res);
  },
  skip: (req, res) => {
    // Only rate limit POST requests with email
    return req.method !== 'POST' || !req.body?.email;
  }
});

/**
 * Rate limiter for upload endpoints
 * Max 20 uploads per hour
 */
export const uploadLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: devOrProd(100, 20),
  message: 'Upload limit exceeded from this IP, please try again later',
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * General API rate limiter
 * Max 100 requests per 15 minutes
 */
export const generalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: devOrProd(1000, 100),
  message: 'Too many requests from this IP, please try again later',
  standardHeaders: true,
  legacyHeaders: false,
});
