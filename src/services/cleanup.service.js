import cron from 'node-cron';
import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import logger from '../utils/logger.js';
import { query } from '../config/database.js';
import storageService from './storage.service.js';

/**
 * Cleanup Service - handles periodic cleanup of old files and database records
 */
export class CleanupService {
  static cleanupInterval = null;

  /**
   * Start the cleanup cron job
   * Runs daily at 3:00 AM to clean up stale files and expired records
   */
  static start() {
    logger.info('Starting cleanup service cron job (runs daily at 03:00)');

    // Run cleanup every day at 3 AM (0 3 * * *)
    this.cleanupInterval = cron.schedule('0 3 * * *', async () => {
      await this.runCleanup();
    });
  }

  /**
   * Stop the cleanup cron job
   */
  static stop() {
    if (this.cleanupInterval) {
      this.cleanupInterval.stop();
      logger.info('Cleanup cron job stopped');
    }
  }

  /**
   * Run the cleanup tasks
   */
  static async runCleanup() {
    logger.info('Starting daily cleanup routine...');
    const startTime = Date.now();

    try {
      // 1. Clean up extracted Django project directories for deleted/failed projects
      await this.cleanupOldProjectDirs();

      // 2. Clean up uploaded ZIP files (older than 7 days)
      await this.cleanupOldZipFiles();

      // 3. Clean up generated Flask output directories (completed > 60 days ago)
      await this.cleanupOldConvertedDirs();

      // 4. Delete expired verification tokens
      await this.cleanupExpiredTokens();

      const duration = Date.now() - startTime;
      logger.info(`Cleanup routine completed in ${duration}ms`);
    } catch (error) {
      logger.error('Cleanup routine failed:', error);
    }
  }

  /**
   * Clean up extracted project directories for deleted or failed projects
   */
  static async cleanupOldProjectDirs() {
    try {
      const result = await query(
        `SELECT id, file_path FROM projects
         WHERE deleted_at < NOW() - INTERVAL '30 days'
         OR (status = 'failed' AND created_at < NOW() - INTERVAL '30 days')`
      );

      let deletedCount = 0;
      let freedBytes = 0;

      for (const project of result.rows) {
        if (project.file_path && fsSync.existsSync(project.file_path)) {
          try {
            const stats = await this.getDirSize(project.file_path);
            await fs.rm(project.file_path, { recursive: true, force: true });
            deletedCount++;
            freedBytes += stats;
            logger.debug(`Deleted project dir: ${project.file_path}`);
          } catch (error) {
            logger.warn(`Failed to delete project dir ${project.file_path}:`, error.message);
          }
        }
      }

      if (deletedCount > 0) {
        logger.info(`Cleaned up ${deletedCount} old project directories (${Math.round(freedBytes / 1024 / 1024)}MB freed)`);
      }
    } catch (error) {
      logger.error('Failed to cleanup old project directories:', error);
    }
  }

  /**
   * Clean up uploaded ZIP files older than 7 days
   */
  static async cleanupOldZipFiles() {
    try {
      const uploadsDir = path.join(process.cwd(), 'storage', 'uploads');
      
      if (!fsSync.existsSync(uploadsDir)) {
        return;
      }

      const files = await fs.readdir(uploadsDir, { withFileTypes: true });
      const sevenDaysAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
      
      let deletedCount = 0;
      let freedBytes = 0;

      for (const file of files) {
        if (!file.isFile() || !file.name.endsWith('.zip')) continue;

        const filePath = path.join(uploadsDir, file.name);
        try {
          const stats = await fs.stat(filePath);
          if (stats.mtimeMs < sevenDaysAgo) {
            await fs.unlink(filePath);
            deletedCount++;
            freedBytes += stats.size;
            logger.debug(`Deleted old ZIP file: ${file.name}`);
          }
        } catch (error) {
          logger.warn(`Failed to cleanup ZIP ${file.name}:`, error.message);
        }
      }

      if (deletedCount > 0) {
        logger.info(`Cleaned up ${deletedCount} old ZIP files (${Math.round(freedBytes / 1024 / 1024)}MB freed)`);
      }
    } catch (error) {
      logger.error('Failed to cleanup old ZIP files:', error);
    }
  }

  /**
   * Clean up generated Flask output directories for conversions completed > 60 days ago
   */
  static async cleanupOldConvertedDirs() {
    try {
      const result = await query(
        `SELECT id, converted_file_path FROM conversion_jobs
         WHERE status IN ('completed', 'validated')
         AND completed_at < NOW() - INTERVAL '60 days'
         AND converted_file_path IS NOT NULL`
      );

      let deletedCount = 0;
      let freedBytes = 0;

      for (const job of result.rows) {
        if (job.converted_file_path && fsSync.existsSync(job.converted_file_path)) {
          try {
            const stats = await this.getDirSize(job.converted_file_path);
            await fs.rm(job.converted_file_path, { recursive: true, force: true });
            deletedCount++;
            freedBytes += stats;
            logger.debug(`Deleted old converted dir: ${job.converted_file_path}`);
          } catch (error) {
            logger.warn(`Failed to delete converted dir ${job.converted_file_path}:`, error.message);
          }
        }
      }

      if (deletedCount > 0) {
        logger.info(`Cleaned up ${deletedCount} old converted directories (${Math.round(freedBytes / 1024 / 1024)}MB freed)`);
      }
    } catch (error) {
      logger.error('Failed to cleanup old converted directories:', error);
    }
  }

  /**
   * Delete expired verification tokens
   */
  static async cleanupExpiredTokens() {
    try {
      const result = await query(
        `DELETE FROM verification_tokens
         WHERE expires_at < NOW()
         RETURNING id`
      );

      if (result.rowCount > 0) {
        logger.info(`Deleted ${result.rowCount} expired verification tokens`);
      }
    } catch (error) {
      logger.error('Failed to cleanup expired tokens:', error);
    }
  }

  /**
   * Get directory size recursively
   * @param {string} dir - Directory path
   * @returns {Promise<number>} Total size in bytes
   */
  static async getDirSize(dir) {
    let size = 0;
    try {
      const files = await fs.readdir(dir, { withFileTypes: true });
      for (const file of files) {
        const fullPath = path.join(dir, file.name);
        if (file.isDirectory()) {
          size += await this.getDirSize(fullPath);
        } else {
          const stats = await fs.stat(fullPath);
          size += stats.size;
        }
      }
    } catch (error) {
      logger.debug(`Error calculating dir size for ${dir}:`, error.message);
    }
    return size;
  }
}

export default CleanupService;
