import express from 'express';
import {
  listUserRepos,
  cloneRepository,
  createRepository,
  pushConvertedProject,
  linkGithubAccount,
  unlinkGithubAccount,
  getGithubStatus
} from '../controllers/github.controller.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

// All routes require authentication
router.use(authenticateToken);

// GitHub account linking
router.post('/link', linkGithubAccount);
router.delete('/unlink', unlinkGithubAccount);
router.get('/status', getGithubStatus);

// List user's GitHub repositories
router.get('/repos', listUserRepos);

// Clone repository to create project
router.post('/clone', cloneRepository);

// Create new GitHub repository
router.post('/create-repo', createRepository);

// Push converted project to GitHub
router.post('/push/:conversionId', pushConvertedProject);

export default router;
