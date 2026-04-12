/**
 * AI Decision Engine — Smart AI Usage Strategy
 * 
 * Determines whether to use AI API for each file based on:
 * - File complexity score (from Python ProjectAnalyzer)
 * - File type and content patterns
 * - Conversion cache availability
 * - AI budget constraints
 * 
 * Goals:
 * - Skip AI for simple boilerplate (models with just field mappings, basic templates)
 * - Use pattern matching for medium-complexity files (forms, serializers)
 * - Reserve AI for truly complex logic (custom middleware, business logic)
 * - Batch similar files for single AI calls
 * - Reduce total AI API calls by 60%+
 */

import logger from '../utils/logger.js';

/**
 * Complexity thresholds for AI decision making
 */
const THRESHOLDS = {
  /** Below this: never use AI (pure pattern matching) */
  SIMPLE_MAX: 30,

  /** Below this: use AI only if pattern matching fails */
  MEDIUM_MAX: 70,

  /** Above this: always use AI */
  COMPLEX_MIN: 70,

  /** Files larger than this line count always trigger AI */
  LARGE_FILE_LOC: 200,
};

/**
 * File types that never need AI regardless of complexity
 */
const AI_SKIP_FILES = new Set([
  '__init__.py', 'apps.py', 'tests.py', 'manage.py',
  'wsgi.py', 'asgi.py', 'conftest.py', 'setup.py',
]);

/**
 * Django file categories that can be handled by pattern matching alone
 */
const PATTERN_ONLY_CATEGORIES = new Set([
  'settings',
  'static_files',
  'configuration',
]);

/**
 * Features that always require AI processing
 */
const AI_REQUIRED_FEATURES = new Set([
  'custom_middleware',
  'django_signals',
  'rest_framework',
  'custom_auth',
  'celery_tasks',
  'class_based_views',
  'management_commands',
]);

class AIDecisionEngine {
  /**
   * @param {Object} options
   * @param {number} options.maxAICalls - Maximum AI calls per conversion (default: 20)
   * @param {boolean} options.enabled - Whether AI is enabled at all
   */
  constructor(options = {}) {
    this.maxAICalls = options.maxAICalls || 20;
    this.enabled = options.enabled !== false;
    this.aiCallsUsed = 0;
    this.decisions = [];
  }

  /**
   * Decide whether to use AI for a specific file
   * 
   * @param {Object} fileAnalysis - Analysis from ProjectAnalyzer
   * @param {string} fileAnalysis.filename - File name
   * @param {number} fileAnalysis.complexity_score - 0-100 complexity
   * @param {number} fileAnalysis.loc - Lines of code
   * @param {string[]} fileAnalysis.features - Detected Django features
   * @param {boolean} fileAnalysis.needs_ai - Analyzer recommendation
   * @param {string} fileAnalysis.category - simple/medium/complex
   * @param {boolean} [hasCachedResult] - Whether cache has a result for this file
   * @returns {Object} Decision result
   */
  shouldUseAI(fileAnalysis, hasCachedResult = false) {
    if (!this.enabled) {
      return this._makeDecision(fileAnalysis, false, 'AI globally disabled');
    }

    const { filename, complexity_score = 50, loc = 0, features = [], category } = fileAnalysis;

    // 1. Skip files that never need AI
    if (AI_SKIP_FILES.has(filename)) {
      return this._makeDecision(fileAnalysis, false, `Skipped: ${filename} never needs AI`);
    }

    // 2. Use cache if available
    if (hasCachedResult) {
      return this._makeDecision(fileAnalysis, false, 'Using cached conversion result');
    }

    // 3. Budget check — if we've used too many AI calls, limit to complex only
    if (this.aiCallsUsed >= this.maxAICalls) {
      if (complexity_score < 85) {
        return this._makeDecision(fileAnalysis, false, 'AI budget exhausted (reserving for critical files)');
      }
    }

    // 4. Simple files — pure pattern matching
    if (complexity_score < THRESHOLDS.SIMPLE_MAX && loc < 100) {
      return this._makeDecision(fileAnalysis, false, 'Simple file: pattern matching sufficient');
    }

    // 5. Settings files — template-based conversion
    if (filename === 'settings.py') {
      return this._makeDecision(fileAnalysis, false, 'Settings: template-based conversion');
    }

    // 6. Complex features always require AI
    const complexFeatures = features.filter(f => AI_REQUIRED_FEATURES.has(f));
    if (complexFeatures.length > 0) {
      this.aiCallsUsed++;
      return this._makeDecision(
        fileAnalysis, true,
        `Complex features detected: ${complexFeatures.join(', ')}`
      );
    }

    // 7. Large files use AI
    if (loc > THRESHOLDS.LARGE_FILE_LOC) {
      this.aiCallsUsed++;
      return this._makeDecision(fileAnalysis, true, `Large file (${loc} lines): AI recommended`);
    }

    // 8. Complex category uses AI
    if (category === 'complex' || complexity_score >= THRESHOLDS.COMPLEX_MIN) {
      this.aiCallsUsed++;
      return this._makeDecision(fileAnalysis, true, `High complexity (${complexity_score}): AI required`);
    }

    // 9. Medium files — pattern matching first
    return this._makeDecision(
      fileAnalysis, false,
      `Medium complexity (${complexity_score}): pattern matching preferred`
    );
  }

  /**
   * Categorize multiple files for batch processing
   * 
   * @param {Object[]} fileAnalyses - Array of file analyses from ProjectAnalyzer
   * @returns {Object} Categorized files
   */
  categorizeForProcessing(fileAnalyses) {
    const batches = {
      /** Files to process without AI (pattern matching / direct copy) */
      noAI: [],
      /** Files needing AI enhancement */
      withAI: [],
      /** Files to skip entirely */
      skip: [],
    };

    for (const fa of fileAnalyses) {
      const decision = this.shouldUseAI(fa);

      if (AI_SKIP_FILES.has(fa.filename)) {
        batches.skip.push({ ...fa, reason: decision.reason });
      } else if (decision.useAI) {
        batches.withAI.push({ ...fa, reason: decision.reason });
      } else {
        batches.noAI.push({ ...fa, reason: decision.reason });
      }
    }

    logger.info(
      `AI decision: ${batches.noAI.length} no-AI, ` +
      `${batches.withAI.length} with-AI, ` +
      `${batches.skip.length} skipped ` +
      `(${this.aiCallsUsed}/${this.maxAICalls} AI budget used)`
    );

    return batches;
  }

  /**
   * Group similar files for batch AI processing
   * Reduces API calls by sending similar files together
   * 
   * @param {Object[]} aiFiles - Files that need AI processing
   * @param {number} [maxBatchSize=5] - Max files per batch
   * @returns {Object[][]} Array of file batches
   */
  createAIBatches(aiFiles, maxBatchSize = 5) {
    // Group by file type/purpose
    const groups = {};

    for (const file of aiFiles) {
      const key = this._getGroupKey(file);
      if (!groups[key]) groups[key] = [];
      groups[key].push(file);
    }

    // Split groups that are too large
    const batches = [];
    for (const [key, files] of Object.entries(groups)) {
      for (let i = 0; i < files.length; i += maxBatchSize) {
        batches.push(files.slice(i, i + maxBatchSize));
      }
    }

    logger.info(
      `Created ${batches.length} AI batches from ${aiFiles.length} files ` +
      `(${Object.keys(groups).length} groups)`
    );

    return batches;
  }

  /**
   * Get AI decision statistics
   * @returns {Object} Statistics
   */
  getStats() {
    const total = this.decisions.length;
    const aiDecisions = this.decisions.filter(d => d.useAI).length;
    const noAIDecisions = total - aiDecisions;

    return {
      totalDecisions: total,
      aiDecisions,
      noAIDecisions,
      aiCallsUsed: this.aiCallsUsed,
      maxAICalls: this.maxAICalls,
      aiReductionRate: total > 0
        ? ((noAIDecisions / total) * 100).toFixed(1) + '%'
        : '0%',
    };
  }

  /**
   * Reset decision state (for new conversion)
   */
  reset() {
    this.aiCallsUsed = 0;
    this.decisions = [];
  }

  // ── Private Methods ──

  /**
   * @private
   */
  _makeDecision(fileAnalysis, useAI, reason) {
    const decision = {
      filename: fileAnalysis.filename || 'unknown',
      complexity: fileAnalysis.complexity_score || 0,
      useAI,
      reason,
      timestamp: Date.now(),
    };

    this.decisions.push(decision);
    logger.debug(
      `AI decision for ${decision.filename}: ` +
      `${useAI ? 'USE AI' : 'SKIP AI'} — ${reason}`
    );

    return decision;
  }

  /**
   * @private
   */
  _getGroupKey(file) {
    const name = file.filename || '';
    if (name.includes('models')) return 'models';
    if (name.includes('views')) return 'views';
    if (name.includes('routes')) return 'routes';
    if (name.includes('forms')) return 'forms';
    if (name.includes('admin')) return 'admin';
    if (name.includes('serializer')) return 'serializers';
    if (name.includes('urls')) return 'urls';
    return 'other';
  }
}

export { AIDecisionEngine, THRESHOLDS, AI_SKIP_FILES, AI_REQUIRED_FEATURES };
export default AIDecisionEngine;
