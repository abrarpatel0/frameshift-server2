import express from 'express';
import {
  startConversion,
  getConversionStatus,
  getUserConversions,
  downloadConversion,
  cancelConversion,
  getConversionReport,
  retryConversion
} from '../controllers/conversion.controller.js';
import { validateApiKey } from '../controllers/apiKeyValidation.controller.js';
import {
  getAllDiffs,
  getFileDiff,
  getFileContent,
  getDiffSummary,
} from '../controllers/diff.controller.js';
import { authenticateToken } from '../middleware/auth.js';
import { conversionLimiter } from '../middleware/rateLimiter.js';
import { validateRequest } from '../middleware/validate.js';
import { conversionSchemas } from '../validation/schemas.js';

const router = express.Router();

// All routes require authentication
router.use(authenticateToken);

// Validate custom API key (must be before /:id routes)
router.post('/validate-api-key', validateRequest(conversionSchemas.validateApiKey), validateApiKey);

// Start new conversion (with rate limiting)
router.post('/', conversionLimiter, validateRequest(conversionSchemas.start), startConversion);

// Get all user's conversions
router.get('/', getUserConversions);

// Get specific conversion status
router.get('/:id', validateRequest(conversionSchemas.conversionIdParam), getConversionStatus);

// Get conversion report
router.get('/:id/report', validateRequest(conversionSchemas.conversionIdParam), getConversionReport);

// Download converted project
router.get('/:id/download', validateRequest(conversionSchemas.conversionIdParam), downloadConversion);

// Retry failed conversion
router.post('/:id/retry', conversionLimiter, validateRequest(conversionSchemas.conversionIdParam), retryConversion);

// Cancel conversion
router.delete('/:id', validateRequest(conversionSchemas.conversionIdParam), cancelConversion);

// Get all diffs for a conversion
router.get('/:id/diffs', validateRequest(conversionSchemas.conversionIdParam), getAllDiffs);

// Get diff summary statistics
router.get('/:id/diffs/summary', validateRequest(conversionSchemas.conversionIdParam), getDiffSummary);

// Get specific file diff
router.get('/:id/diffs/:fileId', validateRequest(conversionSchemas.fileContentParams), getFileDiff);

// Get file content (original/converted)
router.get('/:id/files/:fileId/content', validateRequest(conversionSchemas.fileContentParams), getFileContent);

export default router;
