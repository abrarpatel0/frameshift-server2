/**
 * GitHub OAuth and API configuration
 */
export const githubConfig = {
  clientId: process.env.GITHUB_CLIENT_ID,
  clientSecret: process.env.GITHUB_CLIENT_SECRET,
  callbackURL: process.env.GITHUB_CALLBACK_URL || 'http://localhost:5000/api/auth/github/callback',
  scope: ['user:email', 'repo', 'read:user'],
  authorizationURL: 'https://github.com/login/oauth/authorize',
  tokenURL: 'https://github.com/login/oauth/access_token',
  userProfileURL: 'https://api.github.com/user'
};

export default githubConfig;
