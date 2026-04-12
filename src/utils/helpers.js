/**
 * Shared utility helpers used across multiple controllers.
 * Centralised here to eliminate duplication.
 */

/**
 * Safely parse a value to a positive integer, clamped to [1, max].
 * Returns the fallback if the value is not a finite positive number.
 *
 * @param {*}      value    - Raw value to parse (usually `req.query.*`)
 * @param {number} fallback - Default when value is invalid
 * @param {number} [max=100] - Upper bound
 * @returns {number}
 */
export const toPositiveInt = (value, fallback, max = 100) => {
  const parsed = parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }
  return Math.min(parsed, max);
};

/**
 * Set of conversion statuses considered "successful" for gating downloads,
 * push-to-GitHub, diffs, and other post-conversion features.
 */
export const SUCCESSFUL_CONVERSION_STATUSES = new Set(['completed', 'validated']);
