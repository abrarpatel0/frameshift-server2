import ProjectModel from '../models/project.model.js';
import storageService from '../services/storage.service.js';
import FileValidator from '../utils/fileValidator.js';
import asyncHandler from '../utils/asyncHandler.js';
import { toPositiveInt } from '../utils/helpers.js';
import path from 'path';
import fs from 'fs/promises';
import fsSync from 'fs';
import logger from '../utils/logger.js';
import { getClient } from '../config/database.js';

const SKIP_DIRS = new Set(['node_modules', '.git', '__pycache__', 'venv', '.venv']);

/**
 * Validate that uploaded ZIP contains a valid Django project
 * @param {string} projectPath - Extracted project path
 * @throws {Error} If not a valid Django project
 */
const validateDjangoProject = async (projectPath) => {
  const hasManagePy = await fs.access(path.join(projectPath, 'manage.py')).then(() => true).catch(() => false);
  
  const settingsFiles = [];
  const urlFiles = [];
  const modelFiles = [];
  const pythonFiles = [];
  
  const walkDir = async (dir, depth = 0) => {
    try {
      // Only search up to 3 levels deep to avoid searching node_modules-like dirs
      if (depth > 3) return;
      
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (SKIP_DIRS.has(entry.name)) continue;
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await walkDir(fullPath, depth + 1);
        } else {
          if (entry.name === 'settings.py') settingsFiles.push(fullPath);
          if (entry.name === 'urls.py') urlFiles.push(fullPath);
          if (entry.name === 'models.py') modelFiles.push(fullPath);
          if (entry.name.endsWith('.py')) pythonFiles.push(fullPath);
        }
      }
    } catch (error) {
      logger.debug(`Error walking directory ${dir}:`, error.message);
    }
  };
  
  await walkDir(projectPath);
  
  // More lenient validation: 
  // - Must have either manage.py OR at least a settings.py and urls.py
  // - Should have Python files to indicate it's a real project
  const hasValidStructure = (hasManagePy && settingsFiles.length > 0 && urlFiles.length > 0) ||
                           (!hasManagePy && settingsFiles.length > 0 && urlFiles.length > 0 && pythonFiles.length > 5);
  
  if (!hasValidStructure) {
    const details = {
      hasManagePy,
      settingsCount: settingsFiles.length,
      urlsCount: urlFiles.length,
      modelsCount: modelFiles.length,
      pythonFilesCount: pythonFiles.length
    };
    const message = `Invalid Django project structure. Found: manager.py=${hasManagePy}, settings.py=${settingsFiles.length}, urls.py=${urlFiles.length}, Python files=${pythonFiles.length}. This doesn't match a typical Django project layout.`;
    logger.error('Validation failed:', details);
    throw { status: 422, message };
  }
};

const analyzeProjectDirectory = async (rootPath) => {
  const summary = {
    djangoVersion: 'unknown',
    appCount: 0,
    modelCount: 0,
    viewCount: 0,
    urlPatternCount: 0,
    hasRestFramework: false,
    hasCelery: false,
    hasCustomUserModel: false,
    hasMiddleware: false,
    ormRelationships: 0,
    totalFiles: 0,
    pythonFiles: 0,
    templateFiles: 0,
    staticFiles: 0,
    detectedFramework: 'unknown',
    warnings: []
  };

  const requirementsPath = path.join(rootPath, 'requirements.txt');
  const setupPath = path.join(rootPath, 'setup.py');
  
  // Parse Django and package versions
  try {
    if (fsSync.existsSync(requirementsPath)) {
      const requirementsContent = fsSync.readFileSync(requirementsPath, 'utf-8');
      const djangoMatch = requirementsContent.match(/Django[=><]*([0-9.]+)/i);
      if (djangoMatch) summary.djangoVersion = djangoMatch[1];
      summary.hasRestFramework = /djangorestframework/i.test(requirementsContent);
      summary.hasCelery = /celery/i.test(requirementsContent);
    }
  } catch (e) {
    logger.debug('Could not parse requirements.txt');
  }

  const walk = async (currentPath, depth = 0) => {
    if (depth > 10) return; // Prevent infinite recursion
    
    const entries = await fs.readdir(currentPath, { withFileTypes: true });

    for (const entry of entries) {
      if (SKIP_DIRS.has(entry.name)) continue;
      
      if (entry.isDirectory()) {
        // Count Django apps (directories with apps.py)
        const appsFilePath = path.join(currentPath, entry.name, 'apps.py');
        if (fsSync.existsSync(appsFilePath)) {
          summary.appCount++;
        }
        await walk(path.join(currentPath, entry.name), depth + 1);
        continue;
      }

      summary.totalFiles += 1;
      const fullPath = path.join(currentPath, entry.name);
      const relativePath = path.relative(rootPath, fullPath).replace(/\\/g, '/');

      if (entry.name.endsWith('.py')) {
        summary.pythonFiles += 1;
        
        // Count models, views, URLs
        if (entry.name === 'models.py') {
          try {
            const content = fsSync.readFileSync(fullPath, 'utf-8');
            const classMatches = content.match(/^class\s+[\w]+.*\(.*Model\)/gm) || [];
            summary.modelCount += classMatches.length;
            
            // Count ORM relationships
            const fkMatches = content.match(/ForeignKey|ManyToManyField|OneToOneField/g) || [];
            summary.ormRelationships += fkMatches.length;
            
            // Check for custom user
            if (/AUTH_USER_MODEL|AbstractUser|AbstractBaseUser/i.test(content)) {
              summary.hasCustomUserModel = true;
            }
          } catch (e) {
            logger.debug(`Error parsing models.py: ${e.message}`);
          }
        }
        
        if (entry.name === 'views.py') {
          try {
            const content = fsSync.readFileSync(fullPath, 'utf-8');
            const defMatches = content.match(/^(def|class)\s+\w+/gm) || [];
            summary.viewCount += defMatches.length;
          } catch (e) {
            logger.debug(`Error parsing views.py: ${e.message}`);
          }
        }
        
        if (entry.name === 'urls.py') {
          try {
            const content = fsSync.readFileSync(fullPath, 'utf-8');
            const pathMatches = content.match(/\bpath\(|re_path\(|url\(/g) || [];
            summary.urlPatternCount += pathMatches.length;
          } catch (e) {
            logger.debug(`Error parsing urls.py: ${e.message}`);
          }
        }
        
        if (entry.name === 'settings.py') {
          try {
            const content = fsSync.readFileSync(fullPath, 'utf-8');
            const middlewareMatch = content.match(/MIDDLEWARE\s*=\s*\[/);
            if (middlewareMatch) {
              const customMW = (content.match(/MIDDLEWARE\s*=\s*\[([\s\S]*?)\]/)[1] || '').split(',').filter(
                m => !m.includes('django.') && m.trim()
              ).length;
              summary.hasMiddleware = customMW > 0;
            }
          } catch (e) {
            logger.debug(`Error parsing settings.py: ${e.message}`);
          }
        }
      }

      if (entry.name.endsWith('.html')) {
        summary.templateFiles += 1;
      }

      if (/\.(css|js|png|jpg|jpeg|svg)$/i.test(entry.name)) {
        summary.staticFiles += 1;
      }

      if (relativePath === 'manage.py') {
        summary.detectedFramework = 'django';
      }
    }
  };

  await walk(rootPath);

  // Add warnings based on analysis
  if (summary.hasCelery) {
    summary.warnings.push('Uses Celery for async tasks — requires additional Flask-Celery setup');
  }
  if (summary.hasCustomUserModel) {
    summary.warnings.push('Custom user model — may require Flask-Login customization');
  }
  if (summary.hasMiddleware) {
    summary.warnings.push('Custom middleware detected — will need Flask blueprints and before_request handlers');
  }
  if (summary.hasRestFramework) {
    summary.warnings.push('Uses Django REST Framework — convert to Flask-RESTful or API blueprints');
  }

  // Compute Flask equivalents and effort
  const flaskEquivalents = {
    blueprintCount: Math.max(summary.appCount, 1),
    sqlalchemyModels: summary.modelCount,
    estimatedEffort: 'medium' // default
  };

  // Estimate effort based on complexity
  const complexity = summary.modelCount + summary.viewCount + (summary.hasCelery ? 50 : 0) + (summary.hasRestFramework ? 30 : 0);
  if (complexity < 10) flaskEquivalents.estimatedEffort = 'low';
  else if (complexity < 50) flaskEquivalents.estimatedEffort = 'medium';
  else if (complexity < 150) flaskEquivalents.estimatedEffort = 'high';
  else flaskEquivalents.estimatedEffort = 'very-high';

  return {
    djangoVersion: summary.djangoVersion,
    appCount: summary.appCount,
    modelCount: summary.modelCount,
    viewCount: summary.viewCount,
    urlPatternCount: summary.urlPatternCount,
    hasRestFramework: summary.hasRestFramework,
    hasCelery: summary.hasCelery,
    hasCustomUserModel: summary.hasCustomUserModel,
    hasMiddleware: summary.hasMiddleware,
    ormRelationships: summary.ormRelationships,
    flaskEquivalents,
    warnings: summary.warnings,
    fileStats: {
      totalFiles: summary.totalFiles,
      pythonFiles: summary.pythonFiles,
      templateFiles: summary.templateFiles,
      staticFiles: summary.staticFiles
    }
  };
};

/**
 * Upload project (ZIP file)
 * POST /api/projects/upload
 */
export const uploadProject = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const file = req.file;
  const { name } = req.body;

  logger.info('Upload project request', { userId, hasFile: !!file, fileName: file?.originalname, hasName: !!name });

  if (!file) {
    logger.warn('Upload rejected: No file provided');
    return res.status(400).json({
      success: false,
      error: {
        message: 'No file uploaded'
      }
    });
  }

  // Additional validation
  const validation = FileValidator.validate(file);
  if (!validation.valid) {
    // Delete uploaded file
    await storageService.deleteFile(file.path);

    return res.status(400).json({
      success: false,
      error: {
        message: validation.error
      }
    });
  }

  // Create project directory
  const projectPath = await storageService.createProjectDirectory(userId);
  
  let uploadedZipPath = file.path;
  let client = null;

  try {
    // Start database transaction
    client = await getClient();
    await client.query('BEGIN');

    // Extract ZIP file
    try {
      await storageService.extractZip(uploadedZipPath, projectPath);
    } catch (extractError) {
      if (client) await client.query('ROLLBACK');
      
      // Check if this is a timeout error
      if (extractError.message.includes('timed out')) {
        throw { status: 408, message: extractError.message };
      }
      
      throw extractError;
    }
    
    // Handle common case: ZIP contains a single top-level folder with the actual project
    // (e.g., when user zips the project folder itself)
    let actualProjectPath = projectPath;
    try {
      const entries = await fs.readdir(projectPath);
      if (entries.length === 1) {
        const singleEntry = path.join(projectPath, entries[0]);
        const stat = await fs.stat(singleEntry);
        if (stat.isDirectory()) {
          // Verify this directory contains Django project files
          const possibleManagePy = path.join(singleEntry, 'manage.py');
          const possibleSettings = await fs.access(possibleManagePy).then(() => true).catch(() => false);
          if (possibleSettings || (await fs.readdir(singleEntry)).some(f => f === 'manage.py')) {
            actualProjectPath = singleEntry;
            logger.info(`Detected nested project structure, using: ${actualProjectPath}`);
          }
        }
      }
    } catch (error) {
      logger.debug('Could not detect nested project structure:', error.message);
    }
    
    // Validate that extracted project is a Django project
    try {
      await validateDjangoProject(actualProjectPath);
    } catch (validateError) {
      if (client) await client.query('ROLLBACK');
      throw validateError;
    }

    // Get project size
    const size_bytes = await storageService.getDirectorySize(actualProjectPath);
    const requestedName = name || path.parse(file.originalname).name;
    const uniqueName = await ProjectModel.generateUniqueActiveName(userId, requestedName);

    // Create project record within transaction
    const result = await client.query(
      `INSERT INTO projects (user_id, name, source_type, file_path, size_bytes, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
       RETURNING *`,
      [userId, uniqueName, 'upload', projectPath, size_bytes]
    );
    
    const project = result.rows[0];
    
    // Commit transaction
    await client.query('COMMIT');
    
    // Release the database client
    if (client) {
      client.release();
    }

    // Delete uploaded ZIP file (success path - no longer needed)
    try {
      await storageService.deleteFile(uploadedZipPath);
    } catch (deleteError) {
      logger.warn(`Failed to delete uploaded ZIP file ${uploadedZipPath}:`, deleteError);
    }

    logger.info(`Project uploaded: ${project.id} by user ${userId}`);

    res.status(201).json({
      success: true,
      data: {
        project
      }
    });
  } catch (error) {
    // Rollback on any error
    if (client) {
      try {
        await client.query('ROLLBACK');
        client.release();
      } catch (rollbackError) {
        logger.error('Transaction rollback failed:', rollbackError);
      }
    }
    
    // Cleanup files
    try {
      await storageService.deleteFile(uploadedZipPath);
    } catch (e) {
      logger.warn(`Failed to delete ZIP: ${uploadedZipPath}`, e.message);
    }
    
    try {
      await storageService.deleteDirectory(projectPath);
    } catch (e) {
      logger.warn(`Failed to delete project dir: ${projectPath}`, e.message);
    }

    logger.error('Project upload failed:', error);
    
    // Return appropriate error response based on status
    if (error.status === 408) {
      return res.status(408).json({
        success: false,
        error: {
          code: 'EXTRACTION_TIMEOUT',
          message: error.message
        }
      });
    }

    if (error.status === 422) {
      return res.status(422).json({
        success: false,
        error: {
          code: 'INVALID_DJANGO_PROJECT',
          message: error.message
        }
      });
    }

    // Handle unique constraint violation (duplicate project name)
    if (error.code === '23505') { // Postgres unique_violation error code
      return res.status(409).json({
        success: false,
        error: {
          code: 'DUPLICATE_PROJECT_NAME',
          message: `You already have a project named '${requestedName}'. Please choose a different name.`
        }
      });
    }
    
    throw error;
  } finally {
    if (client) {
      client.release();
    }
  }
});

/**
 * Import project from GitHub
 * POST /api/projects/github
 */
export const importFromGithub = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const { repoUrl, name, description } = req.body;

  if (!repoUrl) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Repository URL is required'
      }
    });
  }

  // Create project record
  const requestedName = name || path.basename(repoUrl, '.git');
  const uniqueName = await ProjectModel.generateUniqueActiveName(userId, requestedName);

  const project = await ProjectModel.create({
    user_id: userId,
    name: uniqueName,
    description,
    source_type: 'github',
    source_url: repoUrl
  });

  logger.info(`GitHub project created: ${project.id} by user ${userId}`);

  res.status(201).json({
    success: true,
    data: {
      project
    },
    message: 'Project created. Use GitHub service to clone the repository.'
  });
});

/**
 * Get all projects for current user
 * GET /api/projects
 */
export const getUserProjects = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const page = toPositiveInt(req.query.page, 1, 1000000);
  const pageSize = toPositiveInt(req.query.pageSize, 10, 100);

  const result = await ProjectModel.getPaginated(userId, page, pageSize);

  res.json({
    success: true,
    data: result
  });
});

/**
 * Get project by ID
 * GET /api/projects/:id
 */
export const getProjectById = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const { id } = req.params;

  const project = await ProjectModel.findByIdAndUserId(id, userId);

  if (!project) {
    return res.status(404).json({
      success: false,
      error: {
        message: 'Project not found'
      }
    });
  }

  res.json({
    success: true,
    data: {
      project
    }
  });
});

/**
 * Update project
 * PATCH /api/projects/:id
 */
export const updateProject = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const { id } = req.params;
  const { name, description } = req.body;

  // Check if project exists and belongs to user
  const existingProject = await ProjectModel.findByIdAndUserId(id, userId);

  if (!existingProject) {
    return res.status(404).json({
      success: false,
      error: {
        message: 'Project not found'
      }
    });
  }

  // Update project
  const updateData = {};
  if (name) updateData.name = name;
  if (description !== undefined) updateData.description = description;

  if (Object.keys(updateData).length === 0) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'No valid fields provided for update'
      }
    });
  }

  const project = await ProjectModel.update(id, updateData);

  logger.info(`Project updated: ${id} by user ${userId}`);

  res.json({
    success: true,
    data: {
      project
    }
  });
});

/**
 * Delete project
 * DELETE /api/projects/:id
 */
export const deleteProject = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const { id } = req.params;

  // Check if project exists and belongs to user
  const project = await ProjectModel.findByIdAndUserId(id, userId);
  if (!project) {
    return res.status(404).json({
      success: false,
      error: {
        message: 'Project not found'
      }
    });
  }

  // Delete project files
  if (project.file_path) {
    await storageService.deleteDirectory(project.file_path);
  }

  // Delete project record
  await ProjectModel.delete(id);

  logger.info(`Project deleted: ${id} by user ${userId}`);

  res.json({
    success: true,
    message: 'Project deleted successfully'
  });
});

/**
 * Analyze project structure
 * GET /api/projects/:id/analyze
 */
export const analyzeProject = asyncHandler(async (req, res) => {
  const { userId } = req.user;
  const { id } = req.params;

  // Check if project exists and belongs to user
  const project = await ProjectModel.findByIdAndUserId(id, userId);

  if (!project) {
    return res.status(404).json({
      success: false,
      error: {
        message: 'Project not found'
      }
    });
  }

  if (!project.file_path) {
    return res.status(400).json({
      success: false,
      error: {
        message: 'Project does not have a local file path to analyze'
      }
    });
  }

  const analysis = await analyzeProjectDirectory(project.file_path);

  res.json({
    success: true,
    message: 'Project analysis completed',
    data: {
      projectId: id,
      projectPath: project.file_path,
      analysis
    }
  });
});
