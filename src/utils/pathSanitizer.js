import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Path sanitization utility
 */
export class PathSanitizer {
  /**
   * Sanitize and validate path
   * @param {string} inputPath - Path to sanitize
   * @returns {string} Sanitized absolute path
   * @throws {Error} If path is invalid or outside allowed directories
   */
  static sanitize(inputPath) {
    // Resolve to absolute path
    const absolutePath = path.resolve(inputPath);

    // Check for path traversal attempts
    if (inputPath.includes('..')) {
      throw new Error('Path traversal detected');
    }

    // Define allowed directories
    const allowedDirs = [
      path.join(process.cwd(), 'storage'),
      path.join(process.cwd(), 'python'),
      path.join(process.cwd(), 'logs')
    ];

    // Check if path is within allowed directories
    const isAllowed = allowedDirs.some(dir => absolutePath.startsWith(dir));

    if (!isAllowed) {
      throw new Error('Path outside allowed directories');
    }

    return absolutePath;
  }

  /**
   * Sanitize filename by removing dangerous characters
   * @param {string} filename - Filename to sanitize
   * @returns {string} Sanitized filename
   */
  static sanitizeFilename(filename) {
    // Remove path separators and dangerous characters
    let sanitized = filename.replace(/[^a-zA-Z0-9._-]/g, '_');

    // Remove leading dots to prevent hidden files
    sanitized = sanitized.replace(/^\.+/, '');

    // Ensure filename is not empty after sanitization
    if (!sanitized || sanitized.length === 0) {
      sanitized = 'file';
    }

    return sanitized;
  }

  /**
   * Check if path is within allowed directory
   * @param {string} targetPath - Path to check
   * @param {string} allowedDir - Allowed base directory
   * @returns {boolean} True if path is safe
   */
  static isPathSafe(targetPath, allowedDir) {
    const absolute = path.resolve(targetPath);
    const allowed = path.resolve(allowedDir);

    return absolute.startsWith(allowed);
  }

  /**
   * Create safe path for user files
   * @param {string} userId - User ID
   * @param {string} projectId - Project ID
   * @param {string} filename - Original filename
   * @returns {string} Safe file path
   */
  static createSafeUserPath(userId, projectId, filename) {
    const sanitizedFilename = this.sanitizeFilename(filename);
    const userDir = path.join(process.cwd(), 'storage', 'projects', userId, projectId);

    return path.join(userDir, sanitizedFilename);
  }
}

export default PathSanitizer;
