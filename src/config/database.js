import 'dotenv/config';
import pg from 'pg';
import logger from '../utils/logger.js';

const { Pool } = pg;

// Create PostgreSQL connection pool
// Note: Neon DB requires connectionString and often sslmode=require
const dbConfig = process.env.DATABASE_URL
  ? {
      connectionString: process.env.DATABASE_URL,
      ssl: { rejectUnauthorized: false }, // Required for Neon
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    }
  : {
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT) || 5432,
      database: process.env.DB_NAME || 'frameshift',
      user: process.env.DB_USER || 'postgres',
      password: process.env.DB_PASSWORD,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    };

const pool = new Pool(dbConfig);

// Pool event handlers for monitoring
pool.on('connect', () => {
  logger.debug('pg pool: +1 connection');
});

pool.on('error', (err) => {
  logger.error('pg pool error:', err.message);
});

pool.on('remove', () => {
  logger.debug('pg pool: -1 connection');
});

// Monitor pool health
setInterval(() => {
  if (pool.waitingCount > 5) {
    logger.warn(`pg pool: ${pool.waitingCount} queries waiting (total: ${pool.totalCount}, idle: ${pool.idleCount})`);
  }
}, 30000);

/**
 * Execute a query
 * @param {string} text - SQL query
 * @param {Array} params - Query parameters
 * @returns {Promise} Query result
 */
export const query = (text, params) => pool.query(text, params);

/**
 * Get a client from the pool for transactions
 * @returns {Promise} Pool client
 */
export const getClient = () => pool.connect();

export default pool;
