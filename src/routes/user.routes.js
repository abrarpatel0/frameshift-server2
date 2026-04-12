import express from 'express';
import {
  getCurrentUser,
  updateUserProfile,
  deleteUserAccount,
  getUserProjects,
  getUserConversions,
  getUserStats
} from '../controllers/user.controller.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

// All routes require authentication
router.use(authenticateToken);

// User profile endpoints
router.get('/me', getCurrentUser);
router.patch('/me', updateUserProfile);
router.delete('/me', deleteUserAccount);

// User's projects
router.get('/me/projects', getUserProjects);

// User's conversion history
router.get('/me/conversions', getUserConversions);

// User statistics
router.get('/me/stats', getUserStats);

export default router;
