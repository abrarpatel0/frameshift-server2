import multer from 'multer';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import FileValidator from '../utils/fileValidator.js';
import logger from '../utils/logger.js';

// Configure storage
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    // Store in uploads directory
    const uploadPath = path.join(process.cwd(), 'storage', 'uploads');
    cb(null, uploadPath);
  },
  filename: (req, file, cb) => {
    // Generate unique filename with timestamp and UUID
    const uniqueSuffix = `${Date.now()}-${uuidv4()}`;
    const ext = path.extname(file.originalname);
    const basename = path.basename(file.originalname, ext);
    const sanitizedBasename = basename.replace(/[^a-zA-Z0-9_-]/g, '_');

    cb(null, `${sanitizedBasename}-${uniqueSuffix}${ext}`);
  }
});

// File filter
const fileFilter = (req, file, cb) => {
  // Validate file type
  if (!FileValidator.isValidZip(file)) {
    logger.warn(`Invalid file type attempted: ${file.originalname}`);
    return cb(new Error('Only ZIP files are allowed'), false);
  }

  // Validate MIME type
  if (!FileValidator.isValidMimeType(file.mimetype)) {
    logger.warn(`Invalid MIME type: ${file.mimetype}`);
    return cb(new Error('Invalid file type'), false);
  }

  // Validate filename safety
  if (!FileValidator.isSafeFilename(file.originalname)) {
    logger.warn(`Unsafe filename detected: ${file.originalname}`);
    return cb(new Error('Invalid or unsafe filename'), false);
  }

  cb(null, true);
};

// Create multer upload middleware
export const uploadMiddleware = multer({
  storage,
  limits: {
    fileSize: FileValidator.MAX_FILE_SIZE,
    files: 1 // Only allow one file at a time
  },
  fileFilter
});

/**
 * Middleware to handle upload errors
 */
export const handleUploadError = (error, req, res, next) => {
  logger.debug('handleUploadError called', { hasError: !!error, hasFile: !!req.file, hasBody: !!req.body });
  
  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({
        success: false,
        error: {
          message: `File too large. Maximum size is ${FileValidator.MAX_FILE_SIZE / 1024 / 1024}MB`
        }
      });
    }

    if (error.code === 'LIMIT_FILE_COUNT') {
      return res.status(400).json({
        success: false,
        error: {
          message: 'Too many files. Only one file allowed'
        }
      });
    }

    logger.error('Multer error:', error);
    return res.status(400).json({
      success: false,
      error: {
        message: 'File upload error',
        details: error.message
      }
    });
  }

  if (error) {
    logger.error('Upload error:', error);
    return res.status(400).json({
      success: false,
      error: {
        message: error.message || 'File upload failed'
      }
    });
  }
  
  // No error, continue to next middleware
  next();
};

export default uploadMiddleware;
