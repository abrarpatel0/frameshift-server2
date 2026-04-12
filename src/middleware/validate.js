import Joi from 'joi';

const SEGMENTS = ['body', 'query', 'params'];

export const validateRequest = (schemas = {}) => (req, res, next) => {
  try {
    for (const segment of SEGMENTS) {
      const schema = schemas[segment];
      if (!schema) {
        continue;
      }

      const { value, error } = schema.validate(req[segment], {
        abortEarly: false,
        stripUnknown: true,
      });

      if (error) {
        const validationError = new Error('Request validation failed');
        validationError.statusCode = 400;
        validationError.details = error.details.map((detail) => detail.message);
        throw validationError;
      }

      req[segment] = value;
    }

    next();
  } catch (error) {
    next(error);
  }
};

export const commonSchemas = {
  uuid: Joi.string().guid({ version: ['uuidv4', 'uuidv5'] }).required(),
  paginationQuery: Joi.object({
    page: Joi.number().integer().min(1).optional(),
    pageSize: Joi.number().integer().min(1).max(100).optional(),
    status: Joi.string().optional(),
  }),
};

export default validateRequest;
