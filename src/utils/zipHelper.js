import archiver from 'archiver';
import unzipper from 'unzipper';
import fs from 'fs';
import path from 'path';
import { promises as fsPromises } from 'fs';
import logger from './logger.js';

/**
 * ZIP file helper utilities
 */
export class ZipHelper {
  /**
   * Extract ZIP file to destination directory with path traversal protection
   * @param {string} zipPath - Path to ZIP file
   * @param {string} destinationPath - Destination directory
   * @returns {Promise<string>} Destination path
   */
  static async extract(zipPath, destinationPath) {
    let isValidating = true;
    
    try {
      // Create destination directory
      await fsPromises.mkdir(destinationPath, { recursive: true });

      return new Promise((resolve, reject) => {
        fs.createReadStream(zipPath)
          .pipe(unzipper.Parse())
          .on('entry', async (entry) => {
            try {
              // SECURITY: Check for path traversal in every entry
              const normalizedPath = path.normalize(entry.path);
              const resolvedPath = path.resolve(destinationPath, normalizedPath);
              
              // Ensure resolved path is still within destinationPath
              const relativePath = path.relative(destinationPath, resolvedPath);
              if (relativePath.startsWith('..') || path.isAbsolute(normalizedPath)) {
                logger.error(`Path traversal attempt detected in ZIP: ${entry.path}`);
                entry.autodrain();
                isValidating = false;
                reject(new Error('Malicious ZIP: path traversal attempt detected'));
                return;
              }
              
              // Create directories as needed
              if (entry.type === 'Directory') {
                await fsPromises.mkdir(resolvedPath, { recursive: true });
                entry.autodrain();
                return;
              }

              const dir = path.dirname(resolvedPath);
              await fsPromises.mkdir(dir, { recursive: true });
              
              // Extract file
              entry.pipe(fs.createWriteStream(resolvedPath));
            } catch (error) {
              logger.error(`Error processing ZIP entry ${entry.path}:`, error);
              entry.autodrain();
              isValidating = false;
              reject(error);
            }
          })
          .on('close', () => {
            if (isValidating) {
              logger.info(`Extracted ZIP to: ${destinationPath}`);
              resolve(destinationPath);
            }
          })
          .on('error', (error) => {
            logger.error('ZIP extraction failed:', error);
            reject(error);
          });
      });
    } catch (error) {
      logger.error('Failed to extract ZIP:', error);
      throw error;
    }
  }

  /**
   * Create ZIP archive from directory
   * @param {string} sourcePath - Source directory to compress
   * @param {string} outputPath - Output ZIP file path
   * @returns {Promise<string>} Output path
   */
  static async create(sourcePath, outputPath) {
    try {
      // Ensure output directory exists
      const outputDir = path.dirname(outputPath);
      await fsPromises.mkdir(outputDir, { recursive: true });

      return new Promise((resolve, reject) => {
        const output = fs.createWriteStream(outputPath);
        const archive = archiver('zip', {
          zlib: { level: 9 } // Maximum compression
        });

        output.on('close', () => {
          logger.info(`Created ZIP archive: ${outputPath} (${archive.pointer()} bytes)`);
          resolve(outputPath);
        });

        archive.on('error', (error) => {
          logger.error('ZIP creation failed:', error);
          reject(error);
        });

        archive.on('warning', (warning) => {
          if (warning.code === 'ENOENT') {
            logger.warn('ZIP warning:', warning);
          } else {
            reject(warning);
          }
        });

        archive.pipe(output);

        // Add directory contents to archive
        archive.directory(sourcePath, false);

        archive.finalize();
      });
    } catch (error) {
      logger.error('Failed to create ZIP:', error);
      throw error;
    }
  }

  /**
   * List contents of ZIP file
   * @param {string} zipPath - Path to ZIP file
   * @returns {Promise<Array>} List of files in ZIP
   */
  static async listContents(zipPath) {
    try {
      const directory = await unzipper.Open.file(zipPath);
      return directory.files.map(file => ({
        path: file.path,
        type: file.type,
        size: file.uncompressedSize
      }));
    } catch (error) {
      logger.error('Failed to list ZIP contents:', error);
      throw error;
    }
  }

  /**
   * Validate ZIP file structure
   * @param {string} zipPath - Path to ZIP file
   * @returns {Promise<Object>} Validation result
   */
  static async validate(zipPath) {
    try {
      const contents = await this.listContents(zipPath);

      // Check for dangerous files
      const dangerousExtensions = ['.exe', '.bat', '.cmd', '.sh', '.ps1', '.dll', '.so'];
      const dangerousFiles = contents.filter(file =>
        dangerousExtensions.some(ext => file.path.toLowerCase().endsWith(ext))
      );

      if (dangerousFiles.length > 0) {
        return {
          valid: false,
          error: 'ZIP contains potentially dangerous files',
          dangerousFiles: dangerousFiles.map(f => f.path)
        };
      }

      // Check for path traversal attempts
      const pathTraversalFiles = contents.filter(file =>
        file.path.includes('..') || file.path.startsWith('/')
      );

      if (pathTraversalFiles.length > 0) {
        return {
          valid: false,
          error: 'ZIP contains path traversal attempts',
          suspiciousFiles: pathTraversalFiles.map(f => f.path)
        };
      }

      return {
        valid: true,
        fileCount: contents.length,
        totalSize: contents.reduce((sum, file) => sum + file.size, 0)
      };
    } catch (error) {
      logger.error('Failed to validate ZIP:', error);
      return {
        valid: false,
        error: error.message
      };
    }
  }

  /**
   * Get total uncompressed size of ZIP
   * @param {string} zipPath - Path to ZIP file
   * @returns {Promise<number>} Total size in bytes
   */
  static async getUncompressedSize(zipPath) {
    try {
      const contents = await this.listContents(zipPath);
      return contents.reduce((sum, file) => sum + file.size, 0);
    } catch (error) {
      logger.error('Failed to get ZIP size:', error);
      throw error;
    }
  }
}

export default ZipHelper;
