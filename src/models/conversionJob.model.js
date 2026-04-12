import { query } from '../config/database.js';

/**
 * Valid conversion job statuses - single source of truth
 * All conversion jobs must have one of these status values
 */
export const VALID_STATUSES = Object.freeze([
  'pending',     // Queued, waiting to start
  'analyzing',   // Analyzing Django project structure
  'converting',  // Running Django→Flask conversion
  'verifying',   // Verifying converted Flask code
  'completed',   // Conversion finished successfully
  'validated',   // Conversion validated and ready
  'failed',      // Conversion failed
  'cancelled'    // User cancelled the conversion
]);

/**
 * ConversionJob model for database operations
 */
// Whitelist of columns that can be updated
const VALID_UPDATE_COLUMNS = [
  'status', 'progress_percentage', 'current_step', 'converted_file_path',
  'error_message', 'started_at', 'completed_at', 'use_ai', 'ai_enhancements',
  'conversion_mode', 'custom_api_config',
  'retry_count', 'last_retry_at', 'updated_at'
];
const SUCCESS_STATUSES = ['completed', 'validated'];

export class ConversionJobModel {
  /**
   * Create a new conversion job
   * @param {Object} jobData - Conversion job data
   * @returns {Promise<Object>} Created conversion job
   */
  static async create(jobData) {
    const {
      project_id,
      user_id,
      status = 'pending',
      progress_percentage = 0,
      current_step = null,
      converted_file_path = null,
      error_message = null,
      use_ai = true,
      ai_enhancements = [],
      conversion_mode = 'default',
      custom_api_config = null
    } = jobData;

    const result = await query(
      `INSERT INTO conversion_jobs (
        project_id, user_id, status, progress_percentage, current_step, converted_file_path,
        error_message, use_ai, ai_enhancements, conversion_mode, custom_api_config
      )
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
       RETURNING *`,
      [
        project_id,
        user_id,
        status,
        progress_percentage,
        current_step,
        converted_file_path,
        error_message,
        use_ai,
        ai_enhancements,
        conversion_mode,
        custom_api_config
      ]
    );

    return result.rows[0];
  }

  /**
   * Find conversion job by ID
   * @param {string} id - Conversion job ID
   * @returns {Promise<Object|null>} Conversion job or null
   */
  static async findById(id) {
    const result = await query(
      'SELECT * FROM conversion_jobs WHERE id = $1',
      [id]
    );

    return result.rows[0] || null;
  }

  /**
   * Find conversion job by ID and user ID (for authorization)
   * @param {string} id - Conversion job ID
   * @param {string} userId - User ID
   * @returns {Promise<Object|null>} Conversion job or null
   */
  static async findByIdAndUserId(id, userId) {
    const result = await query(
      'SELECT * FROM conversion_jobs WHERE id = $1 AND user_id = $2',
      [id, userId]
    );

    return result.rows[0] || null;
  }

  /**
   * Find all conversion jobs for a user
   * @param {string} userId - User ID
   * @param {Object} options - Query options
   * @returns {Promise<Array>} List of conversion jobs with project details
   */
  static async findByUserId(userId, options = {}) {
    const { limit = 10, offset = 0, status = null } = options;

    let queryText = `
      SELECT
        cj.*,
        p.name as project_name,
        p.source_type,
        p.source_url
      FROM conversion_jobs cj
      LEFT JOIN projects p ON cj.project_id = p.id
      WHERE cj.user_id = $1
    `;
    const params = [userId];

    if (status) {
      if (status === 'completed') {
        queryText += ' AND cj.status = ANY($2::text[])';
        params.push(SUCCESS_STATUSES);
      } else {
        queryText += ' AND cj.status = $2';
        params.push(status);
      }
    }

    queryText += ' ORDER BY cj.created_at DESC LIMIT $' + (params.length + 1) + ' OFFSET $' + (params.length + 2);
    params.push(limit, offset);

    const result = await query(queryText, params);
    return result.rows;
  }

  /**
   * Update conversion job
   * @param {string} id - Conversion job ID
   * @param {Object} updateData - Data to update
   * @returns {Promise<Object>} Updated conversion job
   */
  static async update(id, updateData) {
    if (!updateData || Object.keys(updateData).length === 0) {
      const error = new Error('No valid fields provided for conversion job update');
      error.statusCode = 400;
      throw error;
    }

    const fields = [];
    const values = [];
    let paramIndex = 1;

    Object.entries(updateData).forEach(([key, value]) => {
      if (!VALID_UPDATE_COLUMNS.includes(key)) {
        throw new Error(`Invalid update column: ${key}`);
      }
      if (key === 'custom_api_config') {
        fields.push(`${key} = $${paramIndex}`);
        values.push(value);
      } else {
        fields.push(`${key} = $${paramIndex}`);
        values.push(value);
      }
      paramIndex++;
    });

    values.push(id);

    const result = await query(
      `UPDATE conversion_jobs SET ${fields.join(', ')} WHERE id = $${paramIndex}
       RETURNING *`,
      values
    );

    return result.rows[0];
  }

  /**
   * Update progress
   * @param {string} id - Conversion job ID
   * @param {number} percentage - Progress percentage (0-100)
   * @param {string} step - Current step
   * @returns {Promise<Object>} Updated conversion job
   */
  static async updateProgress(id, percentage, step) {
    const result = await query(
      `UPDATE conversion_jobs
       SET progress_percentage = GREATEST(progress_percentage, $1),
           current_step = CASE
             WHEN $1 >= progress_percentage THEN $2
             ELSE current_step
           END,
           updated_at = CURRENT_TIMESTAMP
       WHERE id = $3
         AND status NOT IN ('completed', 'validated', 'failed')
       RETURNING *`,
      [percentage, step, id]
    );

    return result.rows[0];
  }

  /**
   * Mark in-progress jobs as failed (used on server restart recovery)
   * @param {string} reason - Failure reason
   * @returns {Promise<number>} Number of jobs updated
   */
  static async failOrphanedInProgressJobs(reason = 'Conversion interrupted by server restart') {
    const result = await query(
      `UPDATE conversion_jobs
       SET status = 'failed',
           error_message = $1,
           completed_at = CURRENT_TIMESTAMP,
           updated_at = CURRENT_TIMESTAMP
       WHERE status IN ('analyzing', 'converting', 'verifying')
         AND completed_at IS NULL`,
      [reason]
    );

    return result.rowCount || 0;
  }

  /**
   * Mark job as started
   * @param {string} id - Conversion job ID
   * @returns {Promise<Object>} Updated conversion job
   */
  static async markAsStarted(id) {
    const result = await query(
      `UPDATE conversion_jobs
       SET status = 'analyzing', started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
       WHERE id = $1
       RETURNING *`,
      [id]
    );

    return result.rows[0];
  }

  /**
   * Mark job as completed
   * @param {string} id - Conversion job ID
   * @param {string} convertedFilePath - Path to converted project
   * @returns {Promise<Object>} Updated conversion job
   */
  static async markAsCompleted(id, convertedFilePath) {
    const result = await query(
      `UPDATE conversion_jobs
       SET status = 'completed',
           converted_file_path = $1,
           progress_percentage = 100,
           current_step = 'Conversion finished. Running validation checks.',
           completed_at = CURRENT_TIMESTAMP,
           updated_at = CURRENT_TIMESTAMP
       WHERE id = $2
       RETURNING *`,
      [convertedFilePath, id]
    );

    return result.rows[0];
  }

  /**
   * Mark job as validated after post-conversion checks pass
   * @param {string} id - Conversion job ID
   * @returns {Promise<Object>} Updated conversion job
   */
  static async markAsValidated(id) {
    try {
      const result = await query(
        `UPDATE conversion_jobs
         SET status = 'validated',
             progress_percentage = 100,
             current_step = 'Validation checks passed',
             completed_at = CURRENT_TIMESTAMP,
             updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
         RETURNING *`,
        [id]
      );

      return result.rows[0];
    } catch (error) {
      // Backward-compatible fallback for databases that still enforce the old
      // status check constraint and do not yet allow "validated".
      if (error?.code !== '23514') {
        throw error;
      }

      const fallbackResult = await query(
        `UPDATE conversion_jobs
         SET status = 'completed',
             progress_percentage = 100,
             current_step = 'Validation checks passed',
             completed_at = CURRENT_TIMESTAMP,
             updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
         RETURNING *`,
        [id]
      );

      return fallbackResult.rows[0];
    }
  }

  /**
   * Mark job as failed
   * @param {string} id - Conversion job ID
   * @param {string} errorMessage - Error message
   * @returns {Promise<Object>} Updated conversion job
   */
  static async markAsFailed(id, errorMessage) {
    const result = await query(
      `UPDATE conversion_jobs
       SET status = 'failed',
           error_message = $1,
           completed_at = CURRENT_TIMESTAMP,
           updated_at = CURRENT_TIMESTAMP
       WHERE id = $2
       RETURNING *`,
      [errorMessage, id]
    );

    return result.rows[0];
  }

  /**
   * Delete conversion job
   * @param {string} id - Conversion job ID
   * @returns {Promise<boolean>} Success status
   */
  static async delete(id) {
    const result = await query(
      'DELETE FROM conversion_jobs WHERE id = $1',
      [id]
    );

    return result.rowCount > 0;
  }

  /**
   * Count conversion jobs by user and status
   * @param {string} userId - User ID
   * @param {string} status - Job status (optional)
   * @returns {Promise<number>} Count
   */
  static async countByUserId(userId, status = null) {
    let queryText = 'SELECT COUNT(*) FROM conversion_jobs WHERE user_id = $1';
    const params = [userId];

    if (status) {
      if (status === 'completed') {
        queryText += ' AND status = ANY($2::text[])';
        params.push(SUCCESS_STATUSES);
      } else {
        queryText += ' AND status = $2';
        params.push(status);
      }
    }

    const result = await query(queryText, params);
    return parseInt(result.rows[0].count);
  }
}

export default ConversionJobModel;
