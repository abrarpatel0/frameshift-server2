import { query } from '../config/database.js';
import UserModel from '../models/user.model.js';
import ProjectModel from '../models/project.model.js';
import ConversionJobModel from '../models/conversionJob.model.js';
import asyncHandler from '../utils/asyncHandler.js';
import logger from '../utils/logger.js';
import { toPositiveInt } from '../utils/helpers.js';



// USER MANAGEMENT

/**
 * List all users with pagination and search
 * GET /api/admin/users
 */
export const listUsers = asyncHandler(async (req, res) => {
  const page = toPositiveInt(req.query.page, 1, 1000000);
  const pageSize = toPositiveInt(req.query.pageSize, 20, 100);
  const search = req.query.search || '';
  const role = req.query.role || null;
  const offset = (page - 1) * pageSize;

  let queryText = `
    SELECT id, email, full_name, role, email_verified, auth_provider,
           github_username, avatar_url, created_at, updated_at, last_login
    FROM users WHERE 1=1
  `;
  let countQuery = 'SELECT COUNT(*) FROM users WHERE 1=1';
  const params = [];
  const countParams = [];

  if (search) {
    params.push(`%${search}%`);
    countParams.push(`%${search}%`);
    queryText += ` AND (email ILIKE $${params.length} OR full_name ILIKE $${params.length})`;
    countQuery += ` AND (email ILIKE $${countParams.length} OR full_name ILIKE $${countParams.length})`;
  }

  if (role) {
    params.push(role);
    countParams.push(role);
    queryText += ` AND role = $${params.length}`;
    countQuery += ` AND role = $${countParams.length}`;
  }

  queryText += ' ORDER BY created_at DESC';
  params.push(pageSize);
  queryText += ` LIMIT $${params.length}`;
  params.push(offset);
  queryText += ` OFFSET $${params.length}`;

  const [usersResult, countResult] = await Promise.all([
    query(queryText, params),
    query(countQuery, countParams),
  ]);

  const total = parseInt(countResult.rows[0].count, 10);

  res.json({
    success: true,
    data: {
      users: usersResult.rows,
      pagination: {
        page,
        pageSize,
        total,
        totalPages: Math.ceil(total / pageSize),
      },
    },
  });
});

/**
 * Get single user details
 * GET /api/admin/users/:id
 */
export const getUserById = asyncHandler(async (req, res) => {
  const { id } = req.params;

  const result = await query(
    `SELECT id, email, full_name, role, email_verified, auth_provider,
            github_username, avatar_url, created_at, updated_at, last_login
     FROM users WHERE id = $1`,
    [id]
  );

  if (!result.rows[0]) {
    return res.status(404).json({ success: false, error: { message: 'User not found' } });
  }

  const projectCount = await ProjectModel.countByUserId(id);
  const conversionCount = await ConversionJobModel.countByUserId(id);

  res.json({
    success: true,
    data: {
      user: result.rows[0],
      stats: { projectCount, conversionCount },
    },
  });
});

/**
 * Update user (role, status, etc.)
 * PATCH /api/admin/users/:id
 */
export const updateUser = asyncHandler(async (req, res) => {
  const { id } = req.params;
  const { role, full_name, email_verified } = req.body;

  const validRoles = ['user', 'admin', 'superuser'];
  if (role && !validRoles.includes(role)) {
    return res.status(400).json({
      success: false,
      error: { message: `Invalid role. Must be one of: ${validRoles.join(', ')}` },
    });
  }

  // Only superusers can change roles
  if (role && req.adminUser.role !== 'superuser') {
      return res.status(403).json({
          success: false,
          error: { message: 'Only superusers can change user roles' }
      });
  }

  if (id === req.user.userId && role && role !== req.adminUser.role) {
    return res.status(400).json({
      success: false,
      error: { message: 'Cannot change your own role' },
    });
  }

  const updateData = {};
  if (role !== undefined) updateData.role = role;
  if (full_name !== undefined) updateData.full_name = full_name;
  if (email_verified !== undefined) updateData.email_verified = email_verified;

  if (Object.keys(updateData).length === 0) {
    return res.status(400).json({ success: false, error: { message: 'No update data provided' } });
  }

  const user = await UserModel.update(id, updateData);

  logger.info(`Admin ${req.user.userId} updated user ${id}: ${JSON.stringify(updateData)}`);

  res.json({ success: true, data: { user } });
});

/**
 * Delete user
 * DELETE /api/admin/users/:id
 */
export const deleteUser = asyncHandler(async (req, res) => {
  const { id } = req.params;

  if (id === req.user.userId) {
    return res.status(400).json({
      success: false,
      error: { message: 'Cannot delete your own account from admin panel' },
    });
  }

  const user = await UserModel.findById(id);
  if (!user) {
    return res.status(404).json({ success: false, error: { message: 'User not found' } });
  }

  await UserModel.delete(id);

  logger.info(`Admin ${req.user.userId} deleted user ${id} (${user.email})`);

  res.json({ success: true, message: 'User deleted successfully' });
});

// PROJECT MANAGEMENT

/**
 * List all projects (across all users)
 * GET /api/admin/projects
 */
export const listProjects = asyncHandler(async (req, res) => {
  const page = toPositiveInt(req.query.page, 1, 1000000);
  const pageSize = toPositiveInt(req.query.pageSize, 20, 100);
  const offset = (page - 1) * pageSize;

  const [projectsResult, countResult] = await Promise.all([
    query(
      `SELECT p.*, u.email as user_email, u.full_name as user_name
       FROM projects p
       LEFT JOIN users u ON p.user_id = u.id
       ORDER BY p.created_at DESC
       LIMIT $1 OFFSET $2`,
      [pageSize, offset]
    ),
    query('SELECT COUNT(*) FROM projects'),
  ]);

  const total = parseInt(countResult.rows[0].count, 10);

  res.json({
    success: true,
    data: {
      projects: projectsResult.rows,
      pagination: {
        page,
        pageSize,
        total,
        totalPages: Math.ceil(total / pageSize),
      },
    },
  });
});

/**
 * Delete project (admin)
 * DELETE /api/admin/projects/:id
 */
export const deleteProject = asyncHandler(async (req, res) => {
  const { id } = req.params;

  const project = await ProjectModel.findById(id);
  if (!project) {
    return res.status(404).json({ success: false, error: { message: 'Project not found' } });
  }

  await ProjectModel.delete(id);

  logger.info(`Admin ${req.user.userId} deleted project ${id}`);

  res.json({ success: true, message: 'Project deleted successfully' });
});

// CONVERSION MANAGEMENT

/**
 * List all conversions (across all users)
 * GET /api/admin/conversions
 */
export const listConversions = asyncHandler(async (req, res) => {
  const page = toPositiveInt(req.query.page, 1, 1000000);
  const pageSize = toPositiveInt(req.query.pageSize, 20, 100);
  const status = req.query.status || null;
  const offset = (page - 1) * pageSize;

  let queryText = `
    SELECT cj.*, p.name as project_name, u.email as user_email, u.full_name as user_name
    FROM conversion_jobs cj
    LEFT JOIN projects p ON cj.project_id = p.id
    LEFT JOIN users u ON cj.user_id = u.id
    WHERE 1=1
  `;
  let countQuery = 'SELECT COUNT(*) FROM conversion_jobs WHERE 1=1';
  const params = [];
  const countParams = [];

  if (status) {
    if (status === 'completed') {
      params.push(['completed', 'validated']);
      countParams.push(['completed', 'validated']);
      queryText += ` AND cj.status = ANY($${params.length}::text[])`;
      countQuery += ` AND status = ANY($${countParams.length}::text[])`;
    } else {
      params.push(status);
      countParams.push(status);
      queryText += ` AND cj.status = $${params.length}`;
      countQuery += ` AND status = $${countParams.length}`;
    }
  }

  queryText += ' ORDER BY cj.created_at DESC';
  params.push(pageSize);
  queryText += ` LIMIT $${params.length}`;
  params.push(offset);
  queryText += ` OFFSET $${params.length}`;

  const [jobsResult, countResult] = await Promise.all([
    query(queryText, params),
    query(countQuery, countParams),
  ]);

  const total = parseInt(countResult.rows[0].count, 10);

  res.json({
    success: true,
    data: {
      conversions: jobsResult.rows,
      pagination: {
        page,
        pageSize,
        total,
        totalPages: Math.ceil(total / pageSize),
      },
    },
  });
});

// SYSTEM STATISTICS

/**
 * Get system-wide statistics
 * GET /api/admin/stats
 */
export const getSystemStats = asyncHandler(async (req, res) => {
  const [
    usersCount,
    projectsCount,
    totalConversions,
    completedConversions,
    failedConversions,
    activeConversions,
  ] = await Promise.all([
    query('SELECT COUNT(*) FROM users'),
    query('SELECT COUNT(*) FROM projects'),
    query('SELECT COUNT(*) FROM conversion_jobs'),
    query("SELECT COUNT(*) FROM conversion_jobs WHERE status IN ('completed', 'validated')"),
    query("SELECT COUNT(*) FROM conversion_jobs WHERE status = 'failed'"),
    query("SELECT COUNT(*) FROM conversion_jobs WHERE status IN ('pending', 'analyzing', 'converting', 'verifying')"),
  ]);

  const total = parseInt(totalConversions.rows[0].count, 10);
  const completed = parseInt(completedConversions.rows[0].count, 10);
  const successRate = total > 0 ? ((completed / total) * 100).toFixed(1) : 0;

  res.json({
    success: true,
    data: {
      stats: {
        totalUsers: parseInt(usersCount.rows[0].count, 10),
        totalProjects: parseInt(projectsCount.rows[0].count, 10),
        totalConversions: total,
        completedConversions: completed,
        failedConversions: parseInt(failedConversions.rows[0].count, 10),
        activeConversions: parseInt(activeConversions.rows[0].count, 10),
        successRate: parseFloat(successRate),
      },
    },
  });
});

// MIGRATION RULES (Master Table)

/**
 * List migration rules
 * GET /api/admin/migration-rules
 */
export const listMigrationRules = asyncHandler(async (req, res) => {
  const rules = [
    {
      id: 'django-to-flask',
      source: 'Django',
      target: 'Flask',
      status: 'Active',
      components: ['Models (ORM -> SQLAlchemy)', 'Views -> Routes', 'URLs -> Flask routes', 'Templates -> Jinja2'],
      ai_supported: true,
      last_updated: new Date().toISOString(),
    },
  ];

  res.json({
    success: true,
    data: { rules },
  });
});
