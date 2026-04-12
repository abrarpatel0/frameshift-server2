import { Octokit } from "@octokit/rest";
import axios from "axios";
import { execFile } from "child_process";
import path from "path";
import fs from "fs/promises";
import fsSync from "fs";
import githubConfig from "../config/github.js";
import logger from "../utils/logger.js";

/**
 * GitHub service for OAuth and repository operations
 */
export class GitHubService {
  constructor(accessToken = null) {
    this.accessToken = accessToken;
    this.octokit = accessToken ? new Octokit({ auth: accessToken }) : null;
  }

  static sanitizeGithubUrl(repoUrl) {
    let parsedUrl;
    try {
      parsedUrl = new URL(repoUrl);
    } catch {
      throw new Error("Invalid GitHub repository URL");
    }

    if (parsedUrl.protocol !== "https:" || parsedUrl.hostname !== "github.com") {
      throw new Error("Repository URL must be an HTTPS GitHub URL");
    }

    return `${parsedUrl.origin}${parsedUrl.pathname}`.replace(/\/$/, "");
  }

  static validateBranchName(branch) {
    if (!branch || typeof branch !== "string") {
      throw new Error("Branch name is required");
    }

    if (branch.startsWith("-") || branch.includes("..")) {
      throw new Error("Invalid branch name");
    }

    const isValid = /^[A-Za-z0-9._/\-]+$/.test(branch);
    if (!isValid) {
      throw new Error("Invalid branch name");
    }
  }

  static buildGitAuthHeader(token) {
    if (!token) {
      return null;
    }
    const basicToken = Buffer.from(`x-access-token:${token}`).toString("base64");
    return `AUTHORIZATION: basic ${basicToken}`;
  }

  static runGit(args, options = {}) {
    return new Promise((resolve, reject) => {
      execFile("git", args, { ...options, maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
        if (error) {
          error.stdout = stdout;
          error.stderr = stderr;
          reject(error);
          return;
        }
        resolve({ stdout, stderr });
      });
    });
  }

  /**
   * Exchange authorization code for access token
   * @param {string} code - Authorization code from GitHub callback
   * @returns {Promise<string>} Access token
   */
  static async exchangeCodeForToken(code) {
    try {
      const response = await axios.post(
        githubConfig.tokenURL,
        {
          client_id: githubConfig.clientId,
          client_secret: githubConfig.clientSecret,
          code,
        },
        {
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (response.data.error) {
        throw new Error(
          response.data.error_description || "Failed to exchange code for token"
        );
      }

      return response.data.access_token;
    } catch (error) {
      logger.error("Failed to exchange code for token:", error);
      throw error;
    }
  }

  /**
   * Get authenticated user profile
   * @returns {Promise<Object>} User profile
   */
  async getUserProfile() {
    try {
      const { data } = await this.octokit.users.getAuthenticated();
      return data;
    } catch (error) {
      logger.error("Failed to get user profile:", error);
      throw error;
    }
  }

  /**
   * Get user's email addresses
   * @returns {Promise<Array>} Email addresses
   */
  async getUserEmails() {
    try {
      const { data } =
        await this.octokit.users.listEmailsForAuthenticatedUser();
      return data;
    } catch (error) {
      logger.error("Failed to get user emails:", error);
      return [];
    }
  }

  /**
   * Get primary email for user
   * @returns {Promise<string>} Primary email
   */
  async getPrimaryEmail() {
    try {
      const emails = await this.getUserEmails();
      const primaryEmail = emails.find(
        (email) => email.primary && email.verified
      );
      return primaryEmail ? primaryEmail.email : null;
    } catch (error) {
      logger.error("Failed to get primary email:", error);
      return null;
    }
  }

  /**
   * List user's repositories
   * @param {Object} options - Query options
   * @returns {Promise<Array>} List of repositories
   */
  async listUserRepos(options = {}) {
    try {
      const { data } = await this.octokit.repos.listForAuthenticatedUser({
        sort: options.sort || "updated",
        per_page: options.perPage || 100,
        page: options.page || 1,
      });
      return data;
    } catch (error) {
      logger.error("Failed to list repositories:", error);
      throw error;
    }
  }

  /**
   * Get repository information
   * @param {string} owner - Repository owner
   * @param {string} repo - Repository name
   * @returns {Promise<Object>} Repository information
   */
  async getRepository(owner, repo) {
    try {
      const { data } = await this.octokit.repos.get({ owner, repo });
      return data;
    } catch (error) {
      logger.error("Failed to get repository:", error);
      throw error;
    }
  }

  /**
   * Clone repository to local directory
   * @param {string} repoUrl - Repository URL
   * @param {string} destinationPath - Local destination path
   * @param {string} customToken - Optional custom token (PAT) to use instead of OAuth token
   * @returns {Promise<string>} Destination path
   */
  async cloneRepo(repoUrl, destinationPath, customToken = null) {
    try {
      // Ensure destination directory exists
      await fs.mkdir(destinationPath, { recursive: true });

      // Use custom token if provided, otherwise fall back to OAuth token
      const token = customToken || this.accessToken;
      const cloneUrl = GitHubService.sanitizeGithubUrl(repoUrl);

      const cloneArgs = [];
      const authHeader = GitHubService.buildGitAuthHeader(token);
      if (authHeader) {
        cloneArgs.push("-c", `http.extraheader=${authHeader}`);
      }
      cloneArgs.push("clone", cloneUrl, destinationPath);
      await GitHubService.runGit(cloneArgs);

      logger.info(`Cloned repository to: ${destinationPath}${customToken ? ' (using custom PAT)' : ''}`);
      return destinationPath;
    } catch (error) {
      logger.error("Failed to clone repository:", error);

      // Check if it's an authentication error
      if (error.message.includes('Authentication failed') || error.message.includes('could not read Username')) {
        throw new Error('GITHUB_AUTH_REQUIRED');
      }

      throw new Error(`Failed to clone repository: ${error.message}`);
    }
  }

  /**
   * Create a new repository
   * @param {Object} options - Repository options
   * @returns {Promise<Object>} Created repository
   */
  async createRepo(options) {
    try {
      const { data } = await this.octokit.repos.createForAuthenticatedUser({
        name: options.name,
        description: options.description || "",
        private: options.isPrivate !== false, // Default to private
        auto_init: options.autoInit || false,
      });

      logger.info(`Created repository: ${data.full_name}`);
      return data;
    } catch (error) {
      logger.error("Failed to create repository:", error);
      throw error;
    }
  }

  /**
   * Push local directory to GitHub repository
   * @param {string} localPath - Local directory path
   * @param {string} repoUrl - Repository URL
   * @param {string} branch - Branch name (default: main)
   * @returns {Promise<void>}
   */
  async pushToRepo(localPath, repoUrl, branch = "main") {
    try {
      const targetRepoUrl = GitHubService.sanitizeGithubUrl(repoUrl);
      GitHubService.validateBranchName(branch);

      // Remove any existing .git directory to ensure fresh repository
      const gitDir = path.join(localPath, ".git");
      if (fsSync.existsSync(gitDir)) {
        fsSync.rmSync(gitDir, { recursive: true, force: true });
        logger.info("Removed existing git repository");
      }

      // Initialize a completely fresh git repository
      // Use GIT_CEILING_DIRECTORIES to prevent Git from looking at parent directories
      const gitEnv = {
        ...process.env,
        GIT_CEILING_DIRECTORIES: path.dirname(localPath),
      };

      await GitHubService.runGit(["init", "--initial-branch=main"], {
        cwd: localPath,
        env: gitEnv,
      });
      logger.info("Initialized fresh git repository");

      // Configure git user (use GitHub's noreply email)
      await GitHubService.runGit(["config", "user.email", "frameshift@users.noreply.github.com"], { cwd: localPath });
      await GitHubService.runGit(["config", "user.name", "FrameShift"], { cwd: localPath });

      // Add all files in the converted project directory ONLY
      await GitHubService.runGit(["add", "-A"], { cwd: localPath });

      // Commit changes
      const commitMessage =
        "Initial commit: Django to Flask conversion by FrameShift";
      await GitHubService.runGit(["commit", "-m", commitMessage], { cwd: localPath });

      // Set branch name
      await GitHubService.runGit(["branch", "-M", branch], { cwd: localPath });

      // Add remote
      try {
        await GitHubService.runGit(["remote", "add", "origin", targetRepoUrl], {
          cwd: localPath,
        });
      } catch {
        // Remote might already exist, set URL instead
        await GitHubService.runGit(["remote", "set-url", "origin", targetRepoUrl], {
          cwd: localPath,
        });
      }

      // Push to remote
      const pushArgs = [];
      const authHeader = GitHubService.buildGitAuthHeader(this.accessToken);
      if (authHeader) {
        pushArgs.push("-c", `http.extraheader=${authHeader}`);
      }
      pushArgs.push("push", "-u", "origin", branch);
      await GitHubService.runGit(pushArgs, { cwd: localPath });

      logger.info(`Pushed to repository: ${repoUrl}`);
    } catch (error) {
      logger.error("Failed to push to repository:", error);
      throw new Error(`Failed to push to repository: ${error.message}`);
    }
  }

  /**
   * Parse GitHub repository URL
   * @param {string} url - Repository URL
   * @returns {Object} Parsed repository info { owner, repo }
   */
  static parseRepoUrl(url) {
    try {
      // Handle different GitHub URL formats
      const patterns = [
        /github\.com\/([^\/]+)\/([^\/\.]+)(\.git)?$/,
        /github\.com:([^\/]+)\/([^\/\.]+)(\.git)?$/,
      ];

      for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) {
          return {
            owner: match[1],
            repo: match[2],
          };
        }
      }

      throw new Error("Invalid GitHub repository URL");
    } catch (error) {
      logger.error("Failed to parse repository URL:", error);
      throw error;
    }
  }

  /**
   * Check if repository exists
   * @param {string} owner - Repository owner
   * @param {string} repo - Repository name
   * @returns {Promise<boolean>} Exists status
   */
  async repoExists(owner, repo) {
    try {
      await this.octokit.repos.get({ owner, repo });
      return true;
    } catch (error) {
      if (error.status === 404) {
        return false;
      }
      throw error;
    }
  }

  /**
   * Delete repository
   * @param {string} owner - Repository owner
   * @param {string} repo - Repository name
   * @returns {Promise<void>}
   */
  async deleteRepo(owner, repo) {
    try {
      await this.octokit.repos.delete({ owner, repo });
      logger.info(`Deleted repository: ${owner}/${repo}`);
    } catch (error) {
      logger.error("Failed to delete repository:", error);
      throw error;
    }
  }
}

export default GitHubService;
