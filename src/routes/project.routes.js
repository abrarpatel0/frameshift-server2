import express from 'express';
import {
  uploadProject,
  importFromGithub,
  getUserProjects,
  getProjectById,
  updateProject,
  deleteProject,
  analyzeProject
} from '../controllers/project.controller.js';
import { authenticateToken } from '../middleware/auth.js';
import { uploadMiddleware, handleUploadError } from '../middleware/upload.js';
import { uploadLimiter } from '../middleware/rateLimiter.js';
import { validateRequest } from '../middleware/validate.js';
import { projectSchemas } from '../validation/schemas.js';

const router = express.Router();

// All routes require authentication
router.use(authenticateToken);

// Upload project (ZIP file)
router.post(
  '/upload',
  uploadLimiter,
  uploadMiddleware.single('file'),
  handleUploadError,
  uploadProject
);

// Import from GitHub
router.post('/github', validateRequest(projectSchemas.importGithub), importFromGithub);

// Get all user projects (with pagination)
router.get('/', getUserProjects);

// Get specific project
router.get('/:id', validateRequest(projectSchemas.projectIdParam), getProjectById);

// Update project
router.patch('/:id', validateRequest(projectSchemas.update), updateProject);

// Delete project
router.delete('/:id', validateRequest(projectSchemas.projectIdParam), deleteProject);

// Analyze project structure
router.get('/:id/analyze', validateRequest(projectSchemas.projectIdParam), analyzeProject);

export default router;
