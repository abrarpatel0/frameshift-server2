import Joi from 'joi';
import { ALLOWED_CUSTOM_API_PROVIDERS } from '../utils/customApiConfig.js';

export const authSchemas = {
  register: {
    body: Joi.object({
      email: Joi.string().email().required(),
      password: Joi.string().min(8).required(),
      full_name: Joi.string().trim().max(255).allow('', null).optional(),
    }),
  },
  login: {
    body: Joi.object({
      email: Joi.string().email().required(),
      password: Joi.string().required(),
    }),
  },
  verifyEmail: {
    body: Joi.object({
      token: Joi.string().trim().required(),
    }),
  },
  forgotPassword: {
    body: Joi.object({
      email: Joi.string().email().required(),
    }),
  },
  resetPassword: {
    body: Joi.object({
      token: Joi.string().trim().required(),
      password: Joi.string().min(8).required(),
    }),
  },
  changePassword: {
    body: Joi.object({
      currentPassword: Joi.string().required(),
      newPassword: Joi.string().min(8).required(),
    }),
  },
};

export const projectSchemas = {
  importGithub: {
    body: Joi.object({
      repoUrl: Joi.string().uri().required(),
      name: Joi.string().trim().max(255).allow('', null).optional(),
      description: Joi.string().allow('', null).optional(),
    }),
  },
  update: {
    params: Joi.object({
      id: Joi.string().guid({ version: ['uuidv4', 'uuidv5'] }).required(),
    }),
    body: Joi.object({
      name: Joi.string().trim().max(255).optional(),
      description: Joi.string().allow('', null).optional(),
    }).min(1),
  },
  projectIdParam: {
    params: Joi.object({
      id: Joi.string().guid({ version: ['uuidv4', 'uuidv5'] }).required(),
    }),
  },
};

export const conversionSchemas = {
  start: {
    body: Joi.object({
      projectId: Joi.string().guid({ version: ['uuidv4', 'uuidv5'] }).required(),
      use_ai: Joi.boolean().optional(),
      conversion_mode: Joi.string().valid('default', 'custom').optional(),
      accuracy_goal: Joi.string().valid('standard', 'high').optional(),
      gemini_api_key: Joi.string().optional(),
      custom_api_config: Joi.object({
        provider: Joi.string().valid(...ALLOWED_CUSTOM_API_PROVIDERS).required(),
        api_key: Joi.string().required(),
        endpoint: Joi.string().uri().allow('', null).optional(),
        model: Joi.string().allow('', null).optional(),
      }).allow(null).optional(),
    }),
  },
  validateApiKey: {
    body: Joi.object({
      provider: Joi.string().valid(...ALLOWED_CUSTOM_API_PROVIDERS).required(),
      api_key: Joi.string().required(),
      endpoint: Joi.string().uri().allow('', null).optional(),
      model: Joi.string().allow('', null).optional(),
    }),
  },
  conversionIdParam: {
    params: Joi.object({
      id: Joi.string().guid({ version: ['uuidv4', 'uuidv5'] }).required(),
    }),
  },
  fileContentParams: {
    params: Joi.object({
      id: Joi.string().guid({ version: ['uuidv4', 'uuidv5'] }).required(),
      fileId: Joi.string().required(),
    }),
    query: Joi.object({
      version: Joi.string().valid('original', 'converted').optional(),
    }),
  },
};

export default {
  authSchemas,
  projectSchemas,
  conversionSchemas,
};
