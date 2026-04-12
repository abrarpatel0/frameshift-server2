const ALLOWED_PROVIDERS = ['openai', 'gemini', 'claude', 'custom'];
const MAX_FIELD_LENGTH = 500;

/**
 * Basic SSRF protection: check if URL is a valid public HTTPS URL.
 * Prevents requests to localhost, private networks, and non-HTTPS schemes.
 */
const isValidPublicUrl = (urlStr) => {
  try {
    const url = new URL(urlStr);
    
    // Only allow HTTPS in production
    if (url.protocol !== 'https:' && process.env.NODE_ENV === 'production') {
      return { valid: false, error: 'Only HTTPS endpoints are allowed in production.' };
    }

    const hostname = url.hostname.toLowerCase();

    // Block localhost and common local/private hostnames
    const blockedHostnames = ['localhost', '127.0.0.1', '0.0.0.0', '::1'];
    if (blockedHostnames.includes(hostname)) {
      return { valid: false, error: 'Localhost or loopback addresses are not allowed.' };
    }

    // Basic private IP range checks (IPv4)
    // 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16
    const privateIpRegex = /^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|169\.254\.)/;
    if (privateIpRegex.test(hostname)) {
      return { valid: false, error: 'Private network addresses are not allowed.' };
    }

    return { valid: true };
  } catch (e) {
    return { valid: false, error: 'Invalid URL format.' };
  }
};

const toTrimmedString = (value) => (typeof value === 'string' ? value.trim() : '');

export const normalizeConversionMode = (mode) => {
  return mode === 'custom' ? 'custom' : 'default';
};

export const validateAndSanitizeCustomApiConfig = (rawConfig = {}) => {
  const provider = toTrimmedString(rawConfig.provider).toLowerCase();
  const apiKey = toTrimmedString(rawConfig.api_key);
  const endpoint = toTrimmedString(rawConfig.endpoint);
  const model = toTrimmedString(rawConfig.model);

  if (!provider || !ALLOWED_PROVIDERS.includes(provider)) {
    return {
      valid: false,
      error: 'Invalid provider. Allowed providers: OpenAI, Gemini, Claude, Custom.'
    };
  }

  if (!apiKey) {
    return {
      valid: false,
      error: 'API key is required for custom conversion mode.'
    };
  }

  if (endpoint) {
    if (endpoint.length > MAX_FIELD_LENGTH) {
      return { valid: false, error: 'Endpoint URL exceeds maximum length.' };
    }
    
    const urlCheck = isValidPublicUrl(endpoint);
    if (!urlCheck.valid) {
      return { valid: false, error: urlCheck.error };
    }
  }

  if (model.length > MAX_FIELD_LENGTH) {
    return {
      valid: false,
      error: 'Model name exceeds maximum length.'
    };
  }

  const sanitized = {
    provider,
    api_key: apiKey
  };

  if (endpoint) {
    sanitized.endpoint = endpoint;
  }

  if (model) {
    sanitized.model = model;
  }

  return {
    valid: true,
    config: sanitized
  };
};

export const sanitizeCustomApiConfigForResponse = (config) => {
  if (!config || typeof config !== 'object') {
    return null;
  }

  const { api_key, ...safeConfig } = config;
  return safeConfig;
};

export const isAllowedProvider = (provider) => {
  return ALLOWED_PROVIDERS.includes(provider);
};

export const ALLOWED_CUSTOM_API_PROVIDERS = ALLOWED_PROVIDERS;
