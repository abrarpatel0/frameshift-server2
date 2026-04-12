// IMPORTANT: 'dotenv/config' must be the very first import so that
// process.env is populated before any other module reads env vars.
import 'dotenv/config';

import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import logger from './utils/logger.js';
import errorHandler from './middleware/errorHandler.js';
import securityHeaders from './middleware/securityHeaders.js';
import { generalLimiter } from './middleware/rateLimiter.js';
import { setupWebSocket } from './websocket/wsServer.js';
import pool from './config/database.js';

import authRoutes from './routes/auth.routes.js';
import userRoutes from './routes/user.routes.js';
import projectRoutes from './routes/project.routes.js';
import githubRoutes from './routes/github.routes.js';
import conversionRoutes from './routes/conversion.routes.js';
import adminRoutes from './routes/admin.routes.js';

// Create Express app and HTTP server
const app = express();
const server = createServer(app);
const PORT = process.env.PORT || 3000;
let isShuttingDown = false;

const ignoreBrokenPipe = (error) => {
  if (error?.code === 'EPIPE') {
    logger.warn('Ignoring broken pipe on process output stream');
    return;
  }

  throw error;
};

process.stdout.on('error', ignoreBrokenPipe);
process.stderr.on('error', ignoreBrokenPipe);

// Trust first proxy (required for rate limiting behind Heroku, Nginx, Cloudflare, etc.)
app.set('trust proxy', 1);

// Create WebSocket server
const wss = new WebSocketServer({ server, path: '/ws' });

// Security middleware
app.use(helmet());
const allowedOrigins = new Set([
  'http://localhost:3001',
  'http://127.0.0.1:3001',
  process.env.FRONTEND_URL,
].filter(Boolean));

app.use(cors({
  origin: (origin, callback) => {
    // Allow non-browser requests (curl/postman) and known frontend origins.
    if (!origin || allowedOrigins.has(origin)) {
      return callback(null, true);
    }

    if (process.env.NODE_ENV !== 'production') {
      return callback(null, true);
    }

    return callback(new Error(`CORS blocked for origin: ${origin}`), false);
  },
  credentials: true,
}));
app.use(securityHeaders);

// Body parsers
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Cookie parser (for reading HttpOnly cookies from requests)
app.use(cookieParser());

// Rate limiting
app.use(generalLimiter);

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    success: true,
    status: 'ok',
    message: 'FrameShift API is running',
    db: {
      total: pool.totalCount,
      idle: pool.idleCount,
      waiting: pool.waitingCount
    },
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});

// API routes
app.use('/api/auth', authRoutes);
app.use('/api/users', userRoutes);
app.use('/api/projects', projectRoutes);
app.use('/api/github', githubRoutes);
app.use('/api/conversions', conversionRoutes);
app.use('/api/admin', adminRoutes);

// Setup WebSocket server
setupWebSocket(wss);

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: {
      message: 'Route not found',
    },
  });
});

// Global error handler
app.use(errorHandler);

// Start server
server.listen(PORT, () => {
  logger.info(`🚀 FrameShift server is running on port ${PORT}`);
  logger.info(`📡 WebSocket server is running on ws://localhost:${PORT}/ws`);
  logger.info(`Environment: ${process.env.NODE_ENV || 'development'}`);

  // Recover from interrupted conversions after server restart.
  import('./models/conversionJob.model.js')
    .then(({ default: ConversionJobModel }) =>
      ConversionJobModel.failOrphanedInProgressJobs()
    )
    .then((updatedCount) => {
      if (updatedCount > 0) {
        logger.warn(`Marked ${updatedCount} orphaned in-progress conversion job(s) as failed`);
      }
    })
    .catch((error) => {
      logger.error('Failed to recover orphaned conversion jobs:', error);
    });

  // Initialize cleanup service for periodic storage cleanup
  import('./services/cleanup.service.js')
    .then(({ default: CleanupService }) => {
      CleanupService.start();
    })
    .catch((error) => {
      logger.error('Failed to start cleanup service:', error);
    });
});

// Graceful shutdown handler
const gracefulShutdown = async (signal) => {
  if (isShuttingDown) {
    logger.warn(`Shutdown already in progress. Ignoring duplicate ${signal} signal.`);
    return;
  }

  isShuttingDown = true;
  logger.info(`${signal} received. Starting graceful shutdown...`);

  try {
    // Stop accepting new connections
    server.close(() => {
      logger.info('HTTP server closed');
    });

    // Cancel all active conversion processes
    const ConversionService = (await import('./services/conversion.service.js')).default;
    await ConversionService.cancelAllConversions();

    // Stop WebSocket periodic cleanup
    const { stopPeriodicCleanup } = await import('./services/websocket.service.js');
    stopPeriodicCleanup();

    // Close WebSocket server
    wss.close(() => {
      logger.info('WebSocket server closed');
    });

    logger.info('Graceful shutdown completed');
    process.exit(0);
  } catch (error) {
    logger.error('Error during graceful shutdown:', error);
    process.exit(1);
  }
};

// Handle shutdown signals
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception:', error);
  gracefulShutdown('uncaughtException');
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
  gracefulShutdown('unhandledRejection');
});

export default app;
