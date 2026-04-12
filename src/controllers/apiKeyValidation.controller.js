import axios from 'axios';
import asyncHandler from '../utils/asyncHandler.js';
import logger from '../utils/logger.js';
import {
  normalizeConversionMode,
  validateAndSanitizeCustomApiConfig,
} from '../utils/customApiConfig.js';

/**
 * Validate a custom API key by making a lightweight test request
 * POST /api/conversions/validate-api-key
 *
 * Body: { provider, api_key, endpoint?, model? }
 * Returns: { success, data: { valid, provider, message } }
 */
export const validateApiKey = asyncHandler(async (req, res) => {
  const rawConfig = req.body;

  // Re-use the existing format validation first
  const formatCheck = validateAndSanitizeCustomApiConfig(rawConfig);
  if (!formatCheck.valid) {
    return res.status(400).json({
      success: false,
      error: { message: formatCheck.error },
    });
  }

  const { provider, api_key, endpoint, model } = formatCheck.config;

  try {
    let testResult;

    switch (provider) {
      case 'openai':
        testResult = await testOpenAIKey(api_key, endpoint);
        break;
      case 'gemini':
        testResult = await testGeminiKey(api_key);
        break;
      case 'claude':
        testResult = await testClaudeKey(api_key, endpoint);
        break;
      case 'custom':
        testResult = await testCustomKey(api_key, endpoint, model);
        break;
      default:
        testResult = { valid: false, message: `Unsupported provider: ${provider}` };
    }

    return res.json({
      success: true,
      data: {
        valid: testResult.valid,
        provider,
        message: testResult.message,
      },
    });
  } catch (error) {
    logger.error(`API key validation failed for provider ${provider}:`, error.message);
    return res.json({
      success: true,
      data: {
        valid: false,
        provider,
        message: error.response?.data?.error?.message || error.message || 'API key validation failed',
      },
    });
  }
});

/**
 * Test OpenAI API key by listing models (lightweight GET)
 */
async function testOpenAIKey(apiKey, endpoint) {
  const baseUrl = (endpoint || 'https://api.openai.com/v1').replace(/\/+$/, '');
  const response = await axios.get(`${baseUrl}/models`, {
    headers: { Authorization: `Bearer ${apiKey}` },
    timeout: 10000,
  });

  if (response.status === 200) {
    return { valid: true, message: 'OpenAI API key is valid' };
  }
  return { valid: false, message: 'Invalid OpenAI API key' };
}

/**
 * Test Gemini API key by listing models
 */
async function testGeminiKey(apiKey) {
  const response = await axios.get(
    `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`,
    { timeout: 10000 }
  );

  if (response.status === 200) {
    return { valid: true, message: 'Gemini API key is valid' };
  }
  return { valid: false, message: 'Invalid Gemini API key' };
}

/**
 * Test Claude/Anthropic API key by sending a minimal message
 */
async function testClaudeKey(apiKey, endpoint) {
  const baseUrl = (endpoint || 'https://api.anthropic.com/v1').replace(/\/+$/, '');
  const response = await axios.post(
    `${baseUrl}/messages`,
    {
      model: 'claude-3-5-sonnet-latest',
      max_tokens: 1,
      messages: [{ role: 'user', content: 'hi' }],
    },
    {
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      timeout: 10000,
    }
  );

  if (response.status === 200) {
    return { valid: true, message: 'Claude API key is valid' };
  }
  return { valid: false, message: 'Invalid Claude API key' };
}

/**
 * Test custom (OpenAI-compatible) endpoint by listing models
 */
async function testCustomKey(apiKey, endpoint, model) {
  if (!endpoint) {
    return { valid: false, message: 'Custom provider requires an endpoint URL' };
  }

  const baseUrl = endpoint.replace(/\/+$/, '');
  // Try /models first (OpenAI-compatible), fall back to a minimal chat completion
  try {
    const response = await axios.get(`${baseUrl}/models`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      timeout: 10000,
    });
    if (response.status === 200) {
      return { valid: true, message: 'Custom API key is valid' };
    }
  } catch {
    // /models not available, try a minimal completion
    try {
      const response = await axios.post(
        `${baseUrl}/chat/completions`,
        {
          model: model || 'default-model',
          messages: [{ role: 'user', content: 'hi' }],
          max_tokens: 1,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${apiKey}`,
          },
          timeout: 10000,
        }
      );
      if (response.status === 200) {
        return { valid: true, message: 'Custom API endpoint is reachable and key is valid' };
      }
    } catch (innerError) {
      const msg = innerError.response?.data?.error?.message || innerError.message;
      return { valid: false, message: `Custom endpoint validation failed: ${msg}` };
    }
  }

  return { valid: false, message: 'Could not validate custom API key' };
}
