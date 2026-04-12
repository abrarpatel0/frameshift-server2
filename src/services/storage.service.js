import fs from 'fs/promises';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import ZipHelper from '../utils/zipHelper.js';
import PathSanitizer from '../utils/pathSanitizer.js';
import logger from '../utils/logger.js';

/**
 * Storage service for file operations
 */
export class StorageService {
  constructor() {
    this.baseDir = path.join(process.cwd(), 'storage');
    this.uploadsDir = path.join(this.baseDir, 'uploads');
    this.projectsDir = path.join(this.baseDir, 'projects');
    this.convertedDir = path.join(this.baseDir, 'converted');
    this.reportsDir = path.join(this.baseDir, 'reports');
  }

  /**
   * Initialize storage directories
   * @returns {Promise<void>}
   */
  async init() {
    try {
      await fs.mkdir(this.uploadsDir, { recursive: true });
      await fs.mkdir(this.projectsDir, { recursive: true });
      await fs.mkdir(this.convertedDir, { recursive: true });
      await fs.mkdir(this.reportsDir, { recursive: true });
      logger.info('Storage directories initialized');
    } catch (error) {
      logger.error('Failed to initialize storage directories:', error);
      throw error;
    }
  }

  /**
   * Create project directory for user
   * @param {string} userId - User ID
   * @param {string} projectId - Project ID (optional, generated if not provided)
   * @returns {Promise<string>} Project directory path
   */
  async createProjectDirectory(userId, projectId = null) {
    try {
      const id = projectId || uuidv4();
      const projectPath = path.join(this.projectsDir, userId, id);
      await fs.mkdir(projectPath, { recursive: true });
      logger.info(`Created project directory: ${projectPath}`);
      return projectPath;
    } catch (error) {
      logger.error('Failed to create project directory:', error);
      throw error;
    }
  }

  /**
   * Create converted project directory
   * @param {string} userId - User ID
   * @param {string} jobId - Conversion job ID
   * @returns {Promise<string>} Converted directory path
   */
  async createConvertedDirectory(userId, jobId) {
    try {
      const convertedPath = path.join(this.convertedDir, userId, jobId);
      await fs.mkdir(convertedPath, { recursive: true });
      logger.info(`Created converted directory: ${convertedPath}`);
      return convertedPath;
    } catch (error) {
      logger.error('Failed to create converted directory:', error);
      throw error;
    }
  }

  /**
   * Extract ZIP file to project directory with timeout protection
   * @param {string} zipPath - Path to ZIP file
   * @param {string} destinationPath - Destination directory
   * @param {number} timeoutMs - Timeout in milliseconds (default 2 minutes)
   * @returns {Promise<string>} Extraction path
   */
  async extractZip(zipPath, destinationPath, timeoutMs = 2 * 60 * 1000) {
    try {
      // Validate ZIP before extraction
      const validation = await ZipHelper.validate(zipPath);
      if (!validation.valid) {
        throw new Error(validation.error);
      }

      // Extract ZIP with timeout protection
      await Promise.race([
        ZipHelper.extract(zipPath, destinationPath),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error(
              'ZIP extraction timed out. Your Django project may be too large or contain too many files. ' +
              'Try removing virtualenv/, node_modules/, or __pycache__/ directories before uploading.'
            )),
            timeoutMs
          )
        )
      ]);

      logger.info(`Extracted ZIP to: ${destinationPath}`);
      return destinationPath;
    } catch (error) {
      logger.error('Failed to extract ZIP:', error);
      throw error;
    }
  }

  /**
   * Create ZIP archive from directory
   * @param {string} sourcePath - Source directory
   * @param {string} outputFilename - Output filename
   * @param {string} userId - User ID
   * @returns {Promise<string>} ZIP file path
   */
  async createZip(sourcePath, outputFilename, userId) {
    try {
      const outputPath = path.join(this.convertedDir, userId, outputFilename);
      await ZipHelper.create(sourcePath, outputPath);
      logger.info(`Created ZIP archive: ${outputPath}`);
      return outputPath;
    } catch (error) {
      logger.error('Failed to create ZIP:', error);
      throw error;
    }
  }

  /**
   * Delete file
   * @param {string} filePath - File path
   * @returns {Promise<boolean>} Success status
   */
  async deleteFile(filePath) {
    try {
      // Sanitize path
      const safePath = PathSanitizer.sanitize(filePath);
      await fs.unlink(safePath);
      logger.info(`Deleted file: ${safePath}`);
      return true;
    } catch (error) {
      if (error.code === 'ENOENT') {
        logger.warn(`File not found: ${filePath}`);
        return false;
      }
      logger.error(`Failed to delete file ${filePath}:`, error);
      throw error;
    }
  }

  /**
   * Delete directory recursively
   * @param {string} dirPath - Directory path
   * @returns {Promise<boolean>} Success status
   */
  async deleteDirectory(dirPath) {
    try {
      // Sanitize path
      const safePath = PathSanitizer.sanitize(dirPath);
      await fs.rm(safePath, { recursive: true, force: true });
      logger.info(`Deleted directory: ${safePath}`);
      return true;
    } catch (error) {
      if (error.code === 'ENOENT') {
        logger.warn(`Directory not found: ${dirPath}`);
        return false;
      }
      logger.error(`Failed to delete directory ${dirPath}:`, error);
      throw error;
    }
  }

  /**
   * Get file size
   * @param {string} filePath - File path
   * @returns {Promise<number>} File size in bytes
   */
  async getFileSize(filePath) {
    try {
      const stats = await fs.stat(filePath);
      return stats.size;
    } catch (error) {
      logger.error(`Failed to get file size for ${filePath}:`, error);
      throw error;
    }
  }

  /**
   * Get directory size recursively
   * @param {string} dirPath - Directory path
   * @returns {Promise<number>} Total size in bytes
   */
  async getDirectorySize(dirPath) {
    try {
      let totalSize = 0;
      const files = await fs.readdir(dirPath, { withFileTypes: true });

      for (const file of files) {
        const filePath = path.join(dirPath, file.name);

        if (file.isDirectory()) {
          totalSize += await this.getDirectorySize(filePath);
        } else {
          const stats = await fs.stat(filePath);
          totalSize += stats.size;
        }
      }

      return totalSize;
    } catch (error) {
      logger.error(`Failed to get directory size for ${dirPath}:`, error);
      throw error;
    }
  }

  /**
   * Check if file exists
   * @param {string} filePath - File path
   * @returns {Promise<boolean>} Existence status
   */
  async fileExists(filePath) {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Move file
   * @param {string} sourcePath - Source file path
   * @param {string} destinationPath - Destination file path
   * @returns {Promise<void>}
   */
  async moveFile(sourcePath, destinationPath) {
    try {
      // Ensure destination directory exists
      const destDir = path.dirname(destinationPath);
      await fs.mkdir(destDir, { recursive: true });

      await fs.rename(sourcePath, destinationPath);
      logger.info(`Moved file from ${sourcePath} to ${destinationPath}`);
    } catch (error) {
      logger.error('Failed to move file:', error);
      throw error;
    }
  }
}

// Create singleton instance
const storageService = new StorageService();

// Initialize storage on module load
storageService.init().catch(error => {
  logger.error('Failed to initialize storage service:', error);
});

export default storageService;
