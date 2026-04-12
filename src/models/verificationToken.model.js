import pool from '../config/database.js';
import crypto from 'crypto';
import logger from '../utils/logger.js';

class VerificationTokenModel {
  /**
   * Create a new verification token
   * @param {string} userId - User ID
   * @param {string} type - Token type ('email_verification' or 'password_reset')
   * @param {number} expiresInMinutes - Expiration time in minutes (default: 60)
   * @returns {Promise<Object>} Created token
   */
  static async create(userId, type, expiresInMinutes = 60) {
    const token = crypto.randomBytes(32).toString('hex');
    const expiresAt = new Date(Date.now() + expiresInMinutes * 60 * 1000);

    const result = await pool.query(
      `INSERT INTO verification_tokens (user_id, token, type, expires_at)
       VALUES ($1, $2, $3, $4)
       RETURNING *`,
      [userId, token, type, expiresAt]
    );

    logger.info(`Verification token created: ${type} for user ${userId}`);
    return result.rows[0];
  }

  /**
   * Find token by token string and type
   * @param {string} token - Token string
   * @param {string} type - Token type
   * @returns {Promise<Object|null>} Token or null
   */
  static async findByToken(token, type) {
    const result = await pool.query(
      `SELECT * FROM verification_tokens
       WHERE token = $1 AND type = $2 AND used = false AND expires_at > NOW()`,
      [token, type]
    );

    return result.rows[0] || null;
  }

  /**
   * Find all tokens for a user
   * @param {string} userId - User ID
   * @param {string} type - Optional token type filter
   * @returns {Promise<Array>} Array of tokens
   */
  static async findByUserId(userId, type = null) {
    let query = 'SELECT * FROM verification_tokens WHERE user_id = $1';
    const params = [userId];

    if (type) {
      query += ' AND type = $2';
      params.push(type);
    }

    query += ' ORDER BY created_at DESC';

    const result = await pool.query(query, params);
    return result.rows;
  }

  /**
   * Mark token as used
   * @param {string} tokenId - Token ID
   * @returns {Promise<Object>} Updated token
   */
  static async markAsUsed(tokenId) {
    const result = await pool.query(
      `UPDATE verification_tokens
       SET used = true, used_at = NOW()
       WHERE id = $1
       RETURNING *`,
      [tokenId]
    );

    logger.info(`Token marked as used: ${tokenId}`);
    return result.rows[0];
  }

  /**
   * Delete token
   * @param {string} tokenId - Token ID
   * @returns {Promise<boolean>} Success status
   */
  static async delete(tokenId) {
    await pool.query(
      'DELETE FROM verification_tokens WHERE id = $1',
      [tokenId]
    );

    logger.info(`Token deleted: ${tokenId}`);
    return true;
  }

  /**
   * Delete all expired tokens
   * @returns {Promise<number>} Number of deleted tokens
   */
  static async deleteExpired() {
    const result = await pool.query(
      'DELETE FROM verification_tokens WHERE expires_at < NOW() AND used = false RETURNING id'
    );

    const count = result.rowCount;
    logger.info(`Deleted ${count} expired tokens`);
    return count;
  }

  /**
   * Delete all tokens for a user
   * @param {string} userId - User ID
   * @param {string} type - Optional token type filter
   * @returns {Promise<number>} Number of deleted tokens
   */
  static async deleteAllForUser(userId, type = null) {
    let query = 'DELETE FROM verification_tokens WHERE user_id = $1';
    const params = [userId];

    if (type) {
      query += ' AND type = $2';
      params.push(type);
    }

    query += ' RETURNING id';

    const result = await pool.query(query, params);
    const count = result.rowCount;
    logger.info(`Deleted ${count} tokens for user ${userId}`);
    return count;
  }

  /**
   * Check if token is valid
   * @param {string} token - Token string
   * @param {string} type - Token type
   * @returns {Promise<boolean>} Validity status
   */
  static async isValid(token, type) {
    const tokenRecord = await this.findByToken(token, type);
    return tokenRecord !== null;
  }

  /**
   * Get token with user information
   * @param {string} token - Token string
   * @param {string} type - Token type
   * @returns {Promise<Object|null>} Token with user data
   */
  static async findByTokenWithUser(token, type) {
    const result = await pool.query(
      `SELECT vt.*, u.email, u.full_name
       FROM verification_tokens vt
       JOIN users u ON vt.user_id = u.id
       WHERE vt.token = $1 AND vt.type = $2 AND vt.used = false AND vt.expires_at > NOW()`,
      [token, type]
    );

    return result.rows[0] || null;
  }

  /**
   * Count tokens for user by type
   * @param {string} userId - User ID
   * @param {string} type - Token type
   * @returns {Promise<number>} Token count
   */
  static async countByUserAndType(userId, type) {
    const result = await pool.query(
      `SELECT COUNT(*) as count
       FROM verification_tokens
       WHERE user_id = $1 AND type = $2 AND used = false AND expires_at > NOW()`,
      [userId, type]
    );

    return parseInt(result.rows[0].count);
  }
}

export default VerificationTokenModel;
