import path from 'path';
import fs from 'fs/promises';

/**
 * File validation utility
 */
export class FileValidator {
  static MAX_FILE_SIZE = parseInt(process.env.MAX_FILE_SIZE) || 104857600; // 100MB
  static ALLOWED_EXTENSIONS = ['.zip'];
  static DANGEROUS_FILES = [
    '.exe', '.bat', '.cmd', '.sh', '.ps1', '.dll', '.so',
    '.scr', '.vbs', '.js', '.jar', '.msi', '.app'
  ];

  /**
   * Check if file is a valid ZIP
   * @param {Object} file - Multer file object
   * @returns {boolean} Validation result
   */
  static isValidZip(file) {
    const ext = path.extname(file.originalname).toLowerCase();
    return this.ALLOWED_EXTENSIONS.includes(ext);
  }

  /**
   * Validate file size
   * @param {number} size - File size in bytes
   * @returns {boolean} Validation result
   */
  static validateFileSize(size) {
    return size <= this.MAX_FILE_SIZE;
  }

  /**
   * Check if filename contains dangerous patterns
   * @param {string} filename - File name to check
   * @returns {boolean} True if safe, false if dangerous
   */
  static isSafeFilename(filename) {
    // Check for path traversal
    if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
      return false;
    }

    // Check for dangerous extensions
    const ext = path.extname(filename).toLowerCase();
    if (this.DANGEROUS_FILES.includes(ext)) {
      return false;
    }

    // Check for null bytes
    if (filename.includes('\0')) {
      return false;
    }

    return true;
  }

  /**
   * Validate uploaded file
   * @param {Object} file - Multer file object
   * @returns {Object} Validation result { valid: boolean, error?: string }
   */
  static validate(file) {
    if (!file) {
      return { valid: false, error: 'No file provided' };
    }

    // Check file extension
    if (!this.isValidZip(file)) {
      return { valid: false, error: 'Only ZIP files are allowed' };
    }

    // Check file size
    if (!this.validateFileSize(file.size)) {
      return {
        valid: false,
        error: `File size exceeds maximum allowed size of ${this.MAX_FILE_SIZE / 1024 / 1024}MB`
      };
    }

    // Check filename safety
    if (!this.isSafeFilename(file.originalname)) {
      return { valid: false, error: 'Invalid or unsafe filename' };
    }

    return { valid: true };
  }

  /**
   * Validate MIME type
   * @param {string} mimetype - File MIME type
   * @returns {boolean} Validation result
   */
  static isValidMimeType(mimetype) {
    const validMimeTypes = [
      'application/zip',
      'application/x-zip-compressed',
      'multipart/x-zip'
    ];
    return validMimeTypes.includes(mimetype);
  }
}

export default FileValidator;
