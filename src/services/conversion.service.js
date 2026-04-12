import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import fsSync from 'fs';
import ConversionJobModel from '../models/conversionJob.model.js';
import ReportModel from '../models/report.model.js';
import UserModel from '../models/user.model.js';
import storageService from './storage.service.js';
import emailService from './email.service.js';
import DiffService from './diff.service.js';
import { broadcastToUser } from './websocket.service.js';
import conversionCache from './conversion_cache.js';
import AIDecisionEngine from './ai_decision.js';
import logger from '../utils/logger.js';
import { decrypt } from '../utils/encryption.js';
import { normalizeConversionMode } from '../utils/customApiConfig.js';

/**
 * Map to track active Python conversion processes
 * Key: jobId, Value: ChildProcess
 */
const activeProcesses = new Map();

/**
 * Sanitize error messages before sending to client
 * In production, hide implementation details; in development, show truncated paths
 * @param {Error|string} rawError - Raw error object or message
 * @returns {string} Sanitized error message
 */
function sanitizeError(rawError) {
  const errorStr = String(rawError?.message || rawError);
  
  if (process.env.NODE_ENV === 'production') {
    // Production: generic message only
    return 'Conversion failed. Check your project structure and try again.';
  }
  
  // Development: show truncated error with paths masked
  const truncated = errorStr.slice(0, 300);
  return truncated.replace(/\/[\w/\\.-]+/g, '[path]');
}

/**
 * Conversion service - Node-Python bridge
 * Manages Python child processes for Django-to-Flask conversion
 */
export class ConversionService {
  /**
   * Start conversion process
   * @param {string} jobId - Conversion job ID
   * @param {string} projectPath - Path to Django project
   * @param {string} userId - User ID
   * @returns {Promise<Object>} Conversion result
   */
  static async startConversion(
    jobId,
    projectPath,
    userId,
    useAI = true,
    conversionMode = 'default',
    customApiConfig = null,
    geminiApiKey = null
  ) {
    const resolvedMode = normalizeConversionMode(conversionMode);
    logger.info(`Starting conversion job ${jobId} (AI: ${useAI ? 'enabled' : 'disabled'}, mode: ${resolvedMode})`);

    try {
      // Create output directory
      const outputPath = await storageService.createConvertedDirectory(userId, jobId);

      // Mark job as started
      await ConversionJobModel.markAsStarted(jobId);

      const job = await ConversionJobModel.findById(jobId);
      const effectiveCustomConfig = customApiConfig || job?.custom_api_config || null;
      const effectiveMode = normalizeConversionMode(job?.conversion_mode || resolvedMode);

      // Spawn Python process with AI mode/config
      const result = await this.runPythonConversion(
        jobId,
        projectPath,
        outputPath,
        useAI,
        effectiveMode,
        effectiveCustomConfig,
        geminiApiKey
      );

      const latestJob = await ConversionJobModel.findById(jobId);
      const reportWithRuntimeSignals = this.enrichReportWithRuntimeSignals(
        result.report,
        useAI,
        latestJob?.ai_enhancements
      );

      // Mark job as completed
      await ConversionJobModel.markAsCompleted(jobId, outputPath);

      // Save report to database
      await this.saveReport(jobId, reportWithRuntimeSignals);

      // Generate diffs for code preview
      try {
        await this.generateDiffs(jobId, projectPath, outputPath, reportWithRuntimeSignals);
      } catch (diffError) {
        logger.error(`Failed to generate diffs for job ${jobId}:`, diffError);
        // Don't fail the conversion if diff generation fails
      }

      const validation = await this.validateConvertedOutput(outputPath);
      await this.applyValidationResult(jobId, validation, reportWithRuntimeSignals);
      await ConversionJobModel.markAsValidated(jobId);

      // Send success email
      try {
        const user = await UserModel.findById(userId);
        const job = await ConversionJobModel.findById(jobId);
        await emailService.sendConversionCompleteEmail(user, job, reportWithRuntimeSignals);
      } catch (emailError) {
        logger.error(`Failed to send completion email for job ${jobId}:`, emailError);
        // Don't fail the conversion if email fails
      }

      logger.info(`Conversion job ${jobId} completed successfully and passed validation`);

      return {
        success: true,
        jobId,
        outputPath,
        status: 'validated',
        report: reportWithRuntimeSignals,
        validation
      };
    } catch (error) {
      logger.error(`Conversion job ${jobId} failed:`, error);

      // Mark job as failed with sanitized error message
      const failureMessage = error.message === 'DecryptionFailure'
        ? 'API key decryption failed — please re-enter your key in project settings'
        : sanitizeError(error);
      
      await ConversionJobModel.markAsFailed(jobId, failureMessage);

      // Emit websocket error event for decryption failures
      if (error.message === 'DecryptionFailure') {
        broadcastToUser(userId, {
          type: 'conversion:error',
          jobId,
          message: 'Could not decrypt API key'
        });
      }

      // Send failure email
      try {
        const user = await UserModel.findById(userId);
        const job = await ConversionJobModel.findById(jobId);
        await emailService.sendConversionFailedEmail(user, job, failureMessage);
      } catch (emailError) {
        logger.error(`Failed to send failure email for job ${jobId}:`, emailError);
        // Don't fail further if email fails
      }

      throw error;
    }
  }

  /**
   * Detect Python executable on the system
   * @returns {string} Python executable path
   */
  static detectPython() {
    // If explicitly set in env, use it
    if (process.env.PYTHON_PATH) {
      return process.env.PYTHON_PATH;
    }

    // Prefer project-local virtual environment when available
    const localVenvPython = process.platform === 'win32'
      ? path.join(process.cwd(), 'python', '.venv', 'Scripts', 'python.exe')
      : path.join(process.cwd(), 'python', '.venv', 'bin', 'python');

    if (fsSync.existsSync(localVenvPython)) {
      return localVenvPython;
    }

    // On Windows, prefer 'python' over 'python3' (python3 is often the MS Store stub)
    if (process.platform === 'win32') {
      return 'python';
    }

    // On Unix-like systems, prefer python3
    return 'python3';
  }

  /**
   * Run Python conversion process
   * @param {string} jobId - Conversion job ID
   * @param {string} projectPath - Input Django project path
   * @param {string} outputPath - Output Flask project path
   * @param {boolean} useAI - Whether to use AI enhancement
   * @returns {Promise<Object>} Conversion result from Python
   */
  static runPythonConversion(
    jobId,
    projectPath,
    outputPath,
    useAI = true,
    conversionMode = 'default',
    customApiConfig = null,
    geminiApiKey = null
  ) {
    return new Promise(async (resolve, reject) => {
      const pythonPath = this.detectPython();
      const scriptPath = path.join(process.cwd(), 'python', 'main.py');

      const args = [
        scriptPath,
        '--job-id', jobId,
        '--project-path', projectPath,
        '--output-path', outputPath,
        '--use-ai', useAI.toString(),
        '--conversion-mode', normalizeConversionMode(conversionMode)
      ];

      // Add Gemini API key if available (prefer user-provided key over environment variable)
      const apiKeyToUse = geminiApiKey || process.env.GEMINI_API_KEY;
      if (apiKeyToUse) {
        args.push('--gemini-api-key', apiKeyToUse);
      }

      const pythonEnv = { ...process.env };
      
      // Handle custom API config with decryption error handling
      if (normalizeConversionMode(conversionMode) === 'custom' && customApiConfig) {
        try {
          pythonEnv.CUSTOM_API_PROVIDER = customApiConfig.provider || '';
          // Wrap decrypt in try/catch to handle decryption failures gracefully
          pythonEnv.CUSTOM_API_KEY = customApiConfig.api_key ? decrypt(customApiConfig.api_key) : '';
          pythonEnv.CUSTOM_API_ENDPOINT = customApiConfig.endpoint || '';
          pythonEnv.CUSTOM_API_MODEL = customApiConfig.model || '';
        } catch (decryptError) {
          logger.error(`Decryption failed for job ${jobId}:`, decryptError);
          
          // Mark job as failed
          try {
            await ConversionJobModel.markAsFailed(jobId, 'API key decryption failed — please re-enter your key in project settings');
          } catch (markError) {
            logger.error(`Failed to mark job as failed:`, markError);
          }
          
          // Emit websocket error event
          const wss = nodeGlobal.wss;
          if (wss) {
            wss.clients.forEach((client) => {
              client.send(JSON.stringify({
                type: 'conversion:error',
                jobId,
                message: 'Could not decrypt API key'
              }));
            });
          }
          
          // Reject the promise and return early
          reject(new Error('DecryptionFailure'));
          return;
        }
      } else {
        delete pythonEnv.CUSTOM_API_PROVIDER;
        delete pythonEnv.CUSTOM_API_KEY;
        delete pythonEnv.CUSTOM_API_ENDPOINT;
        delete pythonEnv.CUSTOM_API_MODEL;
      }

      logger.info(`Spawning Python process for job ${jobId} in ${normalizeConversionMode(conversionMode)} mode`);

      const pythonProcess = spawn(pythonPath, args, {
        cwd: process.cwd(),
        env: pythonEnv
      });

      // Store process in activeProcesses map for cancellation support
      activeProcesses.set(jobId, pythonProcess);
      logger.info(`Stored active process for job ${jobId} (PID: ${pythonProcess.pid})`);

      let result = null;
      let errorOutput = '';
      let isResolved = false;

      // Set a hard timeout for the conversion process (60 minutes)
      const killTimer = setTimeout(() => {
        if (!isResolved) {
          logger.error(`Conversion job ${jobId} exceeded 60 minute time limit. Terminating process.`);
          pythonProcess.kill('SIGTERM');
          // Give it 5 seconds to gracefully shutdown, then force kill
          setTimeout(() => {
            if (!isResolved && pythonProcess.exitCode === null) {
              logger.error(`Conversion job ${jobId} did not exit after SIGTERM. Force killing.`);
              pythonProcess.kill('SIGKILL');
            }
          }, 5000);
        }
      }, 60 * 60 * 1000); // 60 minutes

      // Handle stdout (progress updates and result)
      pythonProcess.stdout.on('data', async (data) => {
        const lines = data.toString().split('\n');

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const message = JSON.parse(line);

            if (message.type === 'progress') {
              // Update database with progress
              await this.handleProgressUpdate(jobId, message);
            } else if (message.type === 'result') {
              // Store final result
              result = message.data;
              logger.info(`Conversion result received for job ${jobId}`);
            } else if (message.type === 'ai_enhancements_result') {
              // Store AI enhancements directly to database
              await this.handleAIEnhancementsResult(jobId, message.data);
              logger.info(`AI enhancements recorded for job ${jobId}`);
            } else if (message.type === 'error') {
              errorOutput = message.error;
              logger.error(`Python error for job ${jobId}: ${message.error}`);
            }
          } catch (parseError) {
            // Non-JSON output - log but don't crash
            logger.warn(`Non-JSON stdout from Python [job ${jobId}]: ${line.slice(0, 200)}`);
          }
        }
      });

      // Handle stderr
      pythonProcess.stderr.on('data', (data) => {
        const errorText = data.toString();
        errorOutput += errorText;
        logger.error(`Python stderr: ${errorText}`);
      });

      // Handle process exit
      pythonProcess.on('close', (code) => {
        // Clear the timeout timer
        clearTimeout(killTimer);

        // Remove from active processes
        activeProcesses.delete(jobId);
        logger.info(`Removed process for job ${jobId} from active processes (exit code: ${code})`);

        // Prevent multiple resolve/reject calls
        if (isResolved) return;

        // Give a small delay to ensure all stdout has been processed
        setTimeout(() => {
          if (isResolved) return;
          isResolved = true;

          if (code === 0) {
            if (result) {
              logger.info(`Python process exited successfully for job ${jobId}`);
              resolve(result);
            } else {
              const error = new Error('Python process completed but no result was received');
              logger.error(`Python process failed for job ${jobId}: ${error.message}`);
              reject(error);
            }
          } else {
            // Non-zero exit code - check if still converting
            if (code !== null) {
              const error = new Error(errorOutput || `Conversion process terminated unexpectedly (exit code ${code})`);
              logger.error(`Python process failed for job ${jobId}: ${error.message}`);
              reject(error);
            }
          }
        }, 100);
      });

      // Handle process error
      pythonProcess.on('error', (error) => {
        if (isResolved) return;
        isResolved = true;
        logger.error(`Failed to spawn Python process for job ${jobId}:`, error);
        reject(new Error(`Failed to start Python conversion: ${error.message}`));
      });
    });
  }

  /**
   * Handle progress update from Python
   * @param {string} jobId - Conversion job ID
   * @param {Object} message - Progress message
   */
  static async handleProgressUpdate(jobId, message) {
    try {
      // Update database
      await ConversionJobModel.updateProgress(
        jobId,
        message.progress,
        message.step
      );

      // Broadcast via WebSocket (imported dynamically to avoid circular dependency)
      const { broadcastProgress } = await import('./websocket.service.js');
      broadcastProgress(jobId, message);

      logger.debug(`Progress updated for job ${jobId}: ${message.progress}% - ${message.step}`);
    } catch (error) {
      logger.error(`Failed to handle progress update for job ${jobId}:`, error);
    }
  }

  /**
   * Handle AI enhancement results from Python
   * @param {string} jobId - Conversion job ID
   * @param {Object} aiData - AI enhancement data
   */
  static async handleAIEnhancementsResult(jobId, aiData) {
    try {
      // Update report with initial AI data if report exists, otherwise store for later
      // In this architecture, it's safer to update the job model directly if possible,
      // or store in a temporary way. Assuming we might want to attach this to the eventual report.

      // Since the report is created AT THE END, we can't update it yet.
      // But we can update the ConversionJob to store this metadata temporarily or permanently.
      await ConversionJobModel.update(jobId, {
        ai_enhancements: aiData
      });

      logger.debug(`AI enhancements stored for job ${jobId}: ${aiData.length} items`);
    } catch (error) {
      logger.error(`Failed to handle AI enhancements for job ${jobId}:`, error);
    }
  }

  static enrichReportWithRuntimeSignals(report = {}, useAI, aiEnhancements = []) {
    const warnings = Array.isArray(report.warnings) ? [...report.warnings] : [];
    const summaryParts = [report.summary].filter(Boolean);

    if (useAI && (!Array.isArray(aiEnhancements) || aiEnhancements.length === 0)) {
      warnings.push('AI enhancement was enabled, but no verified AI fixes were recorded for this run.');
      summaryParts.push('AI enhancement did not contribute any recorded fixes in this run.');
    }

    return {
      ...report,
      warnings,
      summary: summaryParts.join(' ').trim()
    };
  }

  static async applyValidationResult(jobId, validation, report = {}) {
    const issues = Array.isArray(report.issues) ? [...report.issues] : [];
    const warnings = Array.isArray(report.warnings) ? [...report.warnings] : [];
    const suggestions = Array.isArray(report.suggestions) ? [...report.suggestions] : [];
    const summaryParts = [report.summary].filter(Boolean);

    if (Array.isArray(validation.warnings)) {
      warnings.push(...validation.warnings);
    }

    if (validation.passed) {
      summaryParts.push(
        `Post-conversion validation passed after checking ${validation.filesChecked} Python files.`
      );
      await ReportModel.updateByConversionId(jobId, {
        warnings,
        summary: summaryParts.join(' ').trim()
      });
      return;
    }

    if (Array.isArray(validation.issues)) {
      issues.push(...validation.issues);
    }

    suggestions.push('Review generated Flask entry points, route registration, and syntax errors before trusting this conversion output.');
    summaryParts.push('Post-conversion validation failed. The conversion output is not considered reliable.');

    await ReportModel.updateByConversionId(jobId, {
      issues,
      warnings,
      suggestions,
      summary: summaryParts.join(' ').trim()
    });

    const error = new Error(validation.issues?.[0] || 'Post-conversion validation failed');
    error.code = 'VALIDATION_FAILED';
    throw error;
  }

  static async validateConvertedOutput(outputPath) {
    const projectPath = await this.resolveConvertedProjectPath(outputPath);
    const issues = [];
    const warnings = [];

    if (!projectPath) {
      return {
        passed: false,
        issues: ['Converted project directory could not be located.'],
        warnings,
        filesChecked: 0
      };
    }

    const pythonFiles = await this.collectPythonFiles(projectPath);

    if (pythonFiles.length === 0) {
      issues.push('No Python files were generated in the converted project.');
    }

    const hasFlaskEntry = await this.hasFlaskEntryPoint(pythonFiles);
    if (!hasFlaskEntry) {
      issues.push('Converted output does not contain a detectable Flask app or Blueprint entry point.');
    }

    const compileResult = await this.runPythonCompileCheck(pythonFiles);
    if (!compileResult.success) {
      issues.push(...compileResult.errors);
    }

    return {
      passed: issues.length === 0,
      issues,
      warnings,
      filesChecked: pythonFiles.length
    };
  }

  static async resolveConvertedProjectPath(outputPath) {
    try {
      const entries = await fs.readdir(outputPath, { withFileTypes: true });
      const subdirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
      return subdirs.length > 0 ? path.join(outputPath, subdirs[0]) : outputPath;
    } catch (error) {
      logger.error(`Failed to resolve converted project path for ${outputPath}:`, error);
      return null;
    }
  }

  static async collectPythonFiles(dir) {
    const files = [];
    const skipDirs = new Set(['venv', 'node_modules', '__pycache__', '.git', 'migrations', 'instance', 'logs']);

    const walk = async (currentDir) => {
      const entries = await fs.readdir(currentDir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(currentDir, entry.name);
        if (entry.isDirectory()) {
          if (!skipDirs.has(entry.name)) {
            await walk(fullPath);
          }
          continue;
        }

        if (entry.isFile() && entry.name.endsWith('.py')) {
          files.push(fullPath);
        }
      }
    };

    await walk(dir);
    return files;
  }

  static async hasFlaskEntryPoint(pythonFiles) {
    for (const filePath of pythonFiles) {
      try {
        const content = await fs.readFile(filePath, 'utf-8');
        if (content.includes('Flask(') || content.includes('Blueprint(') || content.includes('Blueprint (')) {
          return true;
        }
      } catch (error) {
        logger.warn(`Failed to inspect generated file ${filePath}:`, error.message);
      }
    }

    return false;
  }

  static async runPythonCompileCheck(pythonFiles) {
    if (!pythonFiles.length) {
      return { success: false, errors: ['Converted output does not contain any Python files to validate.'] };
    }

    const pythonPath = this.detectPython();
    const chunkSize = 50;
    const errors = [];

    for (let index = 0; index < pythonFiles.length; index += chunkSize) {
      const fileChunk = pythonFiles.slice(index, index + chunkSize);
      const chunkResult = await new Promise((resolve) => {
        const compileProcess = spawn(pythonPath, ['-m', 'py_compile', ...fileChunk], {
          cwd: process.cwd(),
          env: process.env
        });

        let stderr = '';

        compileProcess.stderr.on('data', (data) => {
          stderr += data.toString();
        });

        compileProcess.on('close', (code) => {
          resolve({ success: code === 0, stderr });
        });

        compileProcess.on('error', (error) => {
          resolve({ success: false, stderr: error.message });
        });
      });

      if (!chunkResult.success) {
        errors.push(`Python syntax validation failed: ${chunkResult.stderr.trim() || 'Unknown compile error'}`);
        break;
      }
    }

    return {
      success: errors.length === 0,
      errors
    };
  }

  /**
   * Save conversion report to database
   * @param {string} jobId - Conversion job ID
   * @param {Object} report - Report data from Python
   * @returns {Promise<Object>} Saved report
   */
  static async saveReport(jobId, report) {
    try {
      const reportData = {
        conversion_job_id: jobId,
        accuracy_score: report.accuracy_score || 0,
        total_files_converted: report.total_files_converted || 0,
        models_converted: report.models_converted || 0,
        views_converted: report.views_converted || 0,
        urls_converted: report.urls_converted || 0,
        forms_converted: report.forms_converted || 0,
        templates_converted: report.templates_converted || 0,
        issues: report.issues || [],
        warnings: report.warnings || [],
        suggestions: report.suggestions || [],
        gemini_verification: report.gemini_verification || null,
        summary: report.summary || '',
        manual_changes: report.manual_changes || null
      };

      const savedReport = await ReportModel.create(reportData);

      // Log cache stats for optimization monitoring
      const cacheStats = conversionCache.getStats();
      logger.info(`Report saved for job ${jobId} | Cache stats: ${cacheStats.hitRate} hit rate, ${cacheStats.size} entries`);

      return savedReport;
    } catch (error) {
      logger.error(`Failed to save report for job ${jobId}:`, error);
      throw error;
    }
  }

  /**
   * Generate diffs for converted files
   * @param {string} jobId - Conversion job ID
   * @param {string} projectPath - Path to original Django project
   * @param {string} outputPath - Path to converted Flask project
   * @param {Object} report - Conversion report
   * @returns {Promise<void>}
   */
  static async generateDiffs(jobId, projectPath, outputPath, report) {
    try {
      logger.info(`Generating diffs for job ${jobId}`);

      const fileDiffs = [];

      // Find actual project directory inside the upload directory
      // The upload path may contain a single project directory (e.g., "Job Portal")
      let projectName;
      try {
        const entries = await fs.readdir(projectPath, { withFileTypes: true });
        const subdirs = entries.filter(entry => entry.isDirectory()).map(entry => entry.name);

        // Use the first subdirectory as project name, or fall back to the directory name
        projectName = subdirs.length > 0 ? subdirs[0] : path.basename(projectPath);
        logger.info(`Using project name for diffs: ${projectName}`);
      } catch (err) {
        logger.warn(`Error reading project directory ${projectPath}, using basename:`, err.message);
        projectName = path.basename(projectPath);
      }

      const convertedProjectPath = path.join(outputPath, projectName);

      // Recursively find all Python files in converted directory
      const findPythonFiles = async (dir, baseDir) => {
        const files = [];
        try {
          const entries = await fs.readdir(dir, { withFileTypes: true });

          for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);

            if (entry.isDirectory()) {
              // Skip common directories
              if (!['venv', 'node_modules', '__pycache__', '.git', 'migrations', 'instance', 'logs'].includes(entry.name)) {
                const subFiles = await findPythonFiles(fullPath, baseDir);
                files.push(...subFiles);
              }
            } else if (entry.isFile() && entry.name.endsWith('.py')) {
              const relativePath = path.relative(baseDir, fullPath);
              files.push(relativePath);
            }
          }
        } catch (err) {
          logger.warn(`Error reading directory ${dir}:`, err.message);
        }

        return files;
      };

      // Find all Python files in the converted project
      const convertedFiles = await findPythonFiles(convertedProjectPath, convertedProjectPath);

      logger.info(`Found ${convertedFiles.length} Python files in converted project`);

      // Original project path includes the project directory
      const originalProjectPath = path.join(projectPath, projectName);

      // Generate diff for each file
      for (const relativeFilePath of convertedFiles) {
        try {
          const convertedFile = path.join(convertedProjectPath, relativeFilePath);
          const originalFile = path.join(originalProjectPath, relativeFilePath);

          // Check if original file exists
          const originalExists = await fs.access(originalFile).then(() => true).catch(() => false);

          if (!originalExists) {
            logger.debug(`Skipping diff for ${relativeFilePath}: original file not found (new file)`);
            continue;
          }

          // Determine category from file path
          const category = relativeFilePath.includes('models') ? 'models' :
            relativeFilePath.includes('views') ? 'views' :
              relativeFilePath.includes('urls') || relativeFilePath.includes('routes') ? 'urls' :
                relativeFilePath.includes('forms') ? 'forms' :
                  'other';

          // Generate diff
          const diffData = await DiffService.generateFileDiff(originalFile, convertedFile, {
            originalPath: relativeFilePath,
            convertedPath: relativeFilePath,
            category: category,
            confidence: null
          });

          // Add unique ID
          const safeFileId = Buffer
            .from(relativeFilePath)
            .toString('base64url');
          diffData.id = `${jobId}-${safeFileId}`;

          fileDiffs.push(diffData);
          logger.debug(`Generated diff for ${relativeFilePath}`);
        } catch (fileError) {
          logger.warn(`Failed to generate diff for ${relativeFilePath}:`, fileError.message);
        }
      }

      // Update report with file_diffs
      await ReportModel.updateByConversionId(jobId, {
        file_diffs: fileDiffs
      });

      logger.info(`Generated ${fileDiffs.length} file diffs for job ${jobId}`);
    } catch (error) {
      logger.error(`Error generating diffs for job ${jobId}:`, error);
      throw error;
    }
  }

  /**
   * Get conversion status
   * @param {string} jobId - Conversion job ID
   * @returns {Promise<Object>} Job status
   */
  static async getStatus(jobId) {
    const job = await ConversionJobModel.findById(jobId);

    if (!job) {
      throw new Error('Conversion job not found');
    }

    return {
      id: job.id,
      status: job.status,
      progress: job.progress_percentage,
      currentStep: job.current_step,
      startedAt: job.started_at,
      completedAt: job.completed_at,
      error: job.error_message
    };
  }

  /**
   * Cancel conversion job
   * @param {string} jobId - Conversion job ID
   * @returns {Promise<boolean>} Success status
   */
  static async cancelConversion(jobId) {
    logger.info(`Attempting to cancel conversion job ${jobId}`);

    try {
      // Get the active process
      const pythonProcess = activeProcesses.get(jobId);

      if (pythonProcess && !pythonProcess.killed) {
        logger.info(`Found active process for job ${jobId} (PID: ${pythonProcess.pid}), terminating...`);

        // Send SIGTERM for graceful shutdown
        pythonProcess.kill('SIGTERM');

        // Force kill after 5 seconds if still running
        const forceKillTimeout = setTimeout(() => {
          if (!pythonProcess.killed) {
            logger.warn(`Force killing process for job ${jobId} after 5 second timeout`);
            pythonProcess.kill('SIGKILL');
          }
        }, 5000);

        // Wait for process to exit
        await new Promise((resolve) => {
          pythonProcess.once('close', () => {
            clearTimeout(forceKillTimeout);
            resolve();
          });

          // Ensure we don't wait forever
          setTimeout(resolve, 6000);
        });

        logger.info(`Process for job ${jobId} terminated successfully`);
      } else {
        logger.info(`No active process found for job ${jobId}, marking as cancelled in database`);
      }

      // Get the job to find converted file path
      const job = await ConversionJobModel.findById(jobId);
      
      // Delete any partial Flask output directory
      if (job && job.converted_file_path) {
        try {
          const exists = await fs.stat(job.converted_file_path).then(() => true).catch(() => false);
          if (exists) {
            await storageService.deleteDirectory(job.converted_file_path);
            logger.info(`Deleted partial output directory for cancelled job ${jobId}`);
          }
        } catch (cleanupError) {
          logger.warn(`Failed to cleanup output for cancelled job ${jobId}:`, cleanupError.message);
        }
      }

      // Mark as cancelled in database (use new 'cancelled' status instead of 'failed')
      await ConversionJobModel.markAsFailed(jobId, 'Cancelled by user'); // TODO: need markAsCancelled method

      // Remove from active processes if still there
      activeProcesses.delete(jobId);

      // Broadcast cancellation via WebSocket
      try {
        const message = {
          type: 'conversion:cancelled',
          jobId,
          timestamp: Date.now()
        };
        broadcastToUser(job.user_id, message);
      } catch (wsError) {
        logger.error(`Failed to broadcast cancellation for job ${jobId}:`, wsError);
        // Don't fail the cancellation if WebSocket broadcast fails
      }

      logger.info(`Conversion job ${jobId} cancelled successfully`);
      return true;
    } catch (error) {
      logger.error(`Error cancelling conversion job ${jobId}:`, error);
      throw error;
    }
  }

  /**
   * Get all active conversion processes
   * @returns {Array} Array of job IDs with active processes
   */
  static getActiveProcesses() {
    return Array.from(activeProcesses.keys());
  }

  /**
   * Cancel all active conversions (for graceful shutdown)
   * @returns {Promise<void>}
   */
  static async cancelAllConversions() {
    logger.info(`Cancelling all active conversions (${activeProcesses.size} processes)`);

    const cancellationPromises = [];

    for (const jobId of activeProcesses.keys()) {
      cancellationPromises.push(
        this.cancelConversion(jobId).catch((error) => {
          logger.error(`Failed to cancel job ${jobId} during shutdown:`, error);
        })
      );
    }

    await Promise.all(cancellationPromises);
    logger.info('All active conversions cancelled');
  }
}

export default ConversionService;
