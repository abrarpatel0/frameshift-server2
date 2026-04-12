import { query } from '../config/database.js';

/**
 * Report model for database operations
 */
const sanitizeUnicodeString = (value) => {
  if (typeof value !== 'string') {
    return value;
  }

  let sanitized = '';

  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);

    if (codeUnit === 0) {
      continue;
    }

    const isHighSurrogate = codeUnit >= 0xD800 && codeUnit <= 0xDBFF;
    const isLowSurrogate = codeUnit >= 0xDC00 && codeUnit <= 0xDFFF;

    if (isHighSurrogate) {
      const nextCodeUnit = value.charCodeAt(index + 1);
      const hasValidPair = nextCodeUnit >= 0xDC00 && nextCodeUnit <= 0xDFFF;

      if (hasValidPair) {
        sanitized += value[index] + value[index + 1];
        index += 1;
      }

      continue;
    }

    if (isLowSurrogate) {
      continue;
    }

    sanitized += value[index];
  }

  return sanitized;
};

const sanitizeJsonValue = (value) => {
  if (Array.isArray(value)) {
    return value.map(sanitizeJsonValue);
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, entryValue]) => [
        sanitizeUnicodeString(key),
        sanitizeJsonValue(entryValue)
      ])
    );
  }

  return sanitizeUnicodeString(value);
};

// Whitelist of columns that can be updated
const VALID_UPDATE_COLUMNS = [
  'accuracy_score', 'total_files_converted', 'models_converted',
  'views_converted', 'urls_converted', 'forms_converted',
  'templates_converted', 'issues', 'warnings', 'suggestions',
  'gemini_verification', 'summary', 'file_diffs', 'manual_changes'
];

export class ReportModel {
  /**
   * Create a new report
   * @param {Object} reportData - Report data
   * @returns {Promise<Object>} Created report
   */
  static async create(reportData) {
    const {
      conversion_job_id,
      accuracy_score = null,
      total_files_converted = 0,
      models_converted = 0,
      views_converted = 0,
      urls_converted = 0,
      forms_converted = 0,
      templates_converted = 0,
      issues = null,
      warnings = null,
      suggestions = null,
      gemini_verification = null,
      summary = null,
      file_diffs = null,
      manual_changes = null
    } = reportData;

    const sanitizedIssues = issues ? sanitizeJsonValue(issues) : null;
    const sanitizedWarnings = warnings ? sanitizeJsonValue(warnings) : null;
    const sanitizedSuggestions = suggestions ? sanitizeJsonValue(suggestions) : null;
    const sanitizedGeminiVerification = gemini_verification ? sanitizeJsonValue(gemini_verification) : null;
    const sanitizedSummary = sanitizeUnicodeString(summary);
    const sanitizedFileDiffs = file_diffs ? sanitizeJsonValue(file_diffs) : null;
    const sanitizedManualChanges = manual_changes ? sanitizeJsonValue(manual_changes) : null;

    const values = [
      conversion_job_id, accuracy_score, total_files_converted,
      models_converted, views_converted, urls_converted, forms_converted,
      templates_converted,
      sanitizedIssues ? JSON.stringify(sanitizedIssues) : null,
      sanitizedWarnings ? JSON.stringify(sanitizedWarnings) : null,
      sanitizedSuggestions ? JSON.stringify(sanitizedSuggestions) : null,
      sanitizedGeminiVerification ? JSON.stringify(sanitizedGeminiVerification) : null,
      sanitizedSummary,
      sanitizedFileDiffs ? JSON.stringify(sanitizedFileDiffs) : null,
      sanitizedManualChanges ? JSON.stringify(sanitizedManualChanges) : null
    ];

    try {
      const result = await query(
        `INSERT INTO reports (
          conversion_job_id, accuracy_score, total_files_converted,
          models_converted, views_converted, urls_converted, forms_converted,
          templates_converted, issues, warnings, suggestions,
          gemini_verification, summary, file_diffs, manual_changes
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        ON CONFLICT (conversion_job_id) DO UPDATE SET
          accuracy_score = EXCLUDED.accuracy_score,
          total_files_converted = EXCLUDED.total_files_converted,
          models_converted = EXCLUDED.models_converted,
          views_converted = EXCLUDED.views_converted,
          urls_converted = EXCLUDED.urls_converted,
          forms_converted = EXCLUDED.forms_converted,
          templates_converted = EXCLUDED.templates_converted,
          issues = EXCLUDED.issues,
          warnings = EXCLUDED.warnings,
          suggestions = EXCLUDED.suggestions,
          gemini_verification = EXCLUDED.gemini_verification,
          summary = EXCLUDED.summary,
          file_diffs = EXCLUDED.file_diffs,
          manual_changes = EXCLUDED.manual_changes
        RETURNING *`,
        values
      );

      return result.rows[0];
    } catch (error) {
      if (error?.code !== '42P10') {
        throw error;
      }

      const existingReport = await this.findByConversionJobId(conversion_job_id);
      if (existingReport) {
        return this.update(existingReport.id, {
          accuracy_score,
          total_files_converted,
          models_converted,
          views_converted,
          urls_converted,
          forms_converted,
          templates_converted,
          issues,
          warnings,
          suggestions,
          gemini_verification,
          summary,
          file_diffs,
          manual_changes
        });
      }

      const fallbackResult = await query(
        `INSERT INTO reports (
          conversion_job_id, accuracy_score, total_files_converted,
          models_converted, views_converted, urls_converted, forms_converted,
          templates_converted, issues, warnings, suggestions,
          gemini_verification, summary, file_diffs, manual_changes
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        RETURNING *`,
        values
      );

      return fallbackResult.rows[0];
    }
  }

  /**
   * Find report by conversion job ID
   * @param {string} conversionJobId - Conversion job ID
   * @returns {Promise<Object|null>} Report or null
   */
  static async findByConversionJobId(conversionJobId) {
    const result = await query(
      'SELECT * FROM reports WHERE conversion_job_id = $1',
      [conversionJobId]
    );

    return result.rows[0] || null;
  }

  /**
   * Alias for findByConversionJobId
   * @param {string} conversionId - Conversion job ID
   * @returns {Promise<Object|null>} Report or null
   */
  static async findByConversionId(conversionId) {
    return this.findByConversionJobId(conversionId);
  }

  /**
   * Find report by ID
   * @param {string} id - Report ID
   * @returns {Promise<Object|null>} Report or null
   */
  static async findById(id) {
    const result = await query(
      'SELECT * FROM reports WHERE id = $1',
      [id]
    );

    return result.rows[0] || null;
  }

  /**
   * Update report
   * @param {string} id - Report ID
   * @param {Object} updateData - Data to update
   * @returns {Promise<Object>} Updated report
   */
  static async update(id, updateData) {
    if (!updateData || Object.keys(updateData).length === 0) {
      const error = new Error('No valid fields provided for report update');
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
      // JSON fields need to be stringified
      if (['issues', 'warnings', 'suggestions', 'gemini_verification', 'file_diffs', 'manual_changes'].includes(key) && value !== null) {
        fields.push(`${key} = $${paramIndex}`);
        values.push(JSON.stringify(sanitizeJsonValue(value)));
      } else {
        fields.push(`${key} = $${paramIndex}`);
        values.push(sanitizeUnicodeString(value));
      }
      paramIndex++;
    });

    values.push(id);

    const result = await query(
      `UPDATE reports SET ${fields.join(', ')} WHERE id = $${paramIndex}
       RETURNING *`,
      values
    );

    return result.rows[0];
  }

  /**
   * Update report by conversion job ID
   * @param {string} conversionJobId - Conversion job ID
   * @param {Object} updateData - Data to update
   * @returns {Promise<Object>} Updated report
   */
  static async updateByConversionId(conversionJobId, updateData) {
    // First, find the report by conversion_job_id
    const report = await this.findByConversionId(conversionJobId);

    if (!report) {
      throw new Error(`Report not found for conversion job ${conversionJobId}`);
    }

    // Then update using the report ID
    return this.update(report.id, updateData);
  }

  /**
   * Delete report
   * @param {string} id - Report ID
   * @returns {Promise<boolean>} Success status
   */
  static async delete(id) {
    const result = await query(
      'DELETE FROM reports WHERE id = $1',
      [id]
    );

    return result.rowCount > 0;
  }
}

export default ReportModel;
