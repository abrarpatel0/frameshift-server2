import nodemailer from 'nodemailer';
import logger from '../utils/logger.js';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class EmailService {
  constructor() {
    const smtpPort = parseInt(process.env.SMTP_PORT) || 465;

    this.transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: smtpPort,
      secure: smtpPort === 465, // true for 465 (SSL), false for 587 (STARTTLS)
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS
      }
    });

    this.from = process.env.SMTP_FROM || 'FrameShift <noreply@frameshift.com>';
    this.frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3001';
  }

  /**
   * Send welcome email with verification link
   */
  async sendWelcomeEmail(user, verificationToken) {
    const verificationUrl = `${this.frontendUrl}/verify-email?token=${verificationToken}`;

    const html = await this.loadTemplate('welcome', {
      name: user.full_name || 'there',
      email: user.email,
      verificationUrl
    });

    await this.sendEmail({
      to: user.email,
      subject: 'Welcome to FrameShift! 🚀',
      html
    });

    logger.info(`Welcome email sent to ${user.email}`);
  }

  /**
   * Send email verification link
   */
  async sendVerificationEmail(user, verificationToken) {
    const verificationUrl = `${this.frontendUrl}/verify-email?token=${verificationToken}`;

    const html = await this.loadTemplate('verification', {
      name: user.full_name || 'there',
      verificationUrl
    });

    await this.sendEmail({
      to: user.email,
      subject: 'Verify Your Email - FrameShift',
      html
    });

    logger.info(`Verification email sent to ${user.email}`);
  }

  /**
   * Send password reset email
   */
  async sendPasswordResetEmail(user, resetToken) {
    const resetUrl = `${this.frontendUrl}/reset-password?token=${resetToken}`;

    const html = await this.loadTemplate('password-reset', {
      name: user.full_name || 'there',
      resetUrl,
      expiryMinutes: 15
    });

    await this.sendEmail({
      to: user.email,
      subject: 'Reset Your Password - FrameShift',
      html
    });

    logger.info(`Password reset email sent to ${user.email}`);
  }

  /**
   * Send conversion completion email
   */
  async sendConversionCompleteEmail(user, job, report) {
    const downloadUrl = `${this.frontendUrl}/reports/${job.id}`;
    const viewReportUrl = `${this.frontendUrl}/reports/${job.id}`;

    const html = await this.loadTemplate('conversion-complete', {
      name: user.full_name || 'there',
      projectName: job.project_name || 'Your project',
      accuracyScore: report.accuracy_score || 0,
      modelsConverted: report.models_converted || 0,
      viewsConverted: report.views_converted || 0,
      urlsConverted: report.urls_converted || 0,
      templatesConverted: report.templates_converted || 0,
      downloadUrl,
      viewReportUrl,
      hasIssues: report.issues && report.issues.length > 0,
      issuesCount: report.issues ? report.issues.length : 0
    });

    await this.sendEmail({
      to: user.email,
      subject: '✅ Your Django to Flask Conversion is Complete!',
      html
    });

    logger.info(`Conversion complete email sent to ${user.email} for job ${job.id}`);
  }

  /**
   * Send conversion failure email
   */
  async sendConversionFailedEmail(user, job, errorMessage) {
    const supportUrl = `${this.frontendUrl}/settings`;

    const html = await this.loadTemplate('conversion-failed', {
      name: user.full_name || 'there',
      projectName: job.project_name || 'Your project',
      errorMessage: errorMessage || 'Unknown error occurred',
      supportUrl
    });

    await this.sendEmail({
      to: user.email,
      subject: '❌ Conversion Failed - FrameShift',
      html
    });

    logger.info(`Conversion failed email sent to ${user.email} for job ${job.id}`);
  }

  /**
   * Generic email sender
   */
  async sendEmail({ to, subject, html, text }) {
    try {
      if (!process.env.SMTP_USER || !process.env.SMTP_PASS) {
        logger.warn('SMTP credentials not configured. Email not sent.');
        return;
      }

      const mailOptions = {
        from: this.from,
        to,
        subject,
        html,
        text: text || this.stripHtml(html)
      };

      const info = await this.transporter.sendMail(mailOptions);
      logger.info(`Email sent: ${info.messageId}`);
      const previewUrl = nodemailer.getTestMessageUrl(info);
      if (previewUrl) {
        logger.info(`Email preview URL: ${previewUrl}`);
      }
      return info;
    } catch (error) {
      logger.error(`Failed to send email to ${to}:`, error);
      throw error;
    }
  }

  /**
   * Load email template from file
   */
  async loadTemplate(templateName, variables = {}) {
    try {
      const templatePath = path.join(__dirname, '..', 'templates', 'emails', `${templateName}.html`);
      let html = await fs.readFile(templatePath, 'utf-8');

      // Replace variables in template
      Object.keys(variables).forEach(key => {
        const regex = new RegExp(`{{${key}}}`, 'g');
        html = html.replace(regex, variables[key]);
      });

      return html;
    } catch (error) {
      logger.error(`Failed to load email template ${templateName}:`, error);
      // Return basic fallback template
      return this.getFallbackTemplate(templateName, variables);
    }
  }

  /**
   * Fallback template if file doesn't exist
   */
  getFallbackTemplate(templateName, variables) {
    const styles = `
      <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }
        .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
      </style>
    `;

    switch (templateName) {
      case 'welcome':
        return `
          <!DOCTYPE html>
          <html>
            <head>${styles}</head>
            <body>
              <div class="container">
                <div class="header">
                  <h1>Welcome to FrameShift! 🚀</h1>
                </div>
                <div class="content">
                  <p>Hi ${variables.name},</p>
                  <p>Thank you for signing up for FrameShift! We're excited to help you convert your Django projects to Flask.</p>
                  <p>Please verify your email address to get started:</p>
                  <a href="${variables.verificationUrl}" class="button">Verify Email</a>
                  <p>If the button doesn't work, copy and paste this link into your browser:</p>
                  <p style="word-break: break-all; color: #667eea;">${variables.verificationUrl}</p>
                </div>
                <div class="footer">
                  <p>FrameShift - Django to Flask Migration Tool</p>
                </div>
              </div>
            </body>
          </html>
        `;

      case 'verification':
        return `
          <!DOCTYPE html>
          <html>
            <head>${styles}</head>
            <body>
              <div class="container">
                <div class="header">
                  <h1>Verify Your Email</h1>
                </div>
                <div class="content">
                  <p>Hi ${variables.name},</p>
                  <p>Please click the button below to verify your email address:</p>
                  <a href="${variables.verificationUrl}" class="button">Verify Email</a>
                  <p>If the button doesn't work, copy and paste this link:</p>
                  <p style="word-break: break-all; color: #667eea;">${variables.verificationUrl}</p>
                </div>
                <div class="footer">
                  <p>FrameShift - Django to Flask Migration Tool</p>
                </div>
              </div>
            </body>
          </html>
        `;

      case 'password-reset':
        return `
          <!DOCTYPE html>
          <html>
            <head>${styles}</head>
            <body>
              <div class="container">
                <div class="header">
                  <h1>Reset Your Password</h1>
                </div>
                <div class="content">
                  <p>Hi ${variables.name},</p>
                  <p>We received a request to reset your password. Click the button below to set a new password:</p>
                  <a href="${variables.resetUrl}" class="button">Reset Password</a>
                  <p>This link will expire in ${variables.expiryMinutes} minutes.</p>
                  <p>If you didn't request this, you can safely ignore this email.</p>
                  <p style="word-break: break-all; color: #667eea;">${variables.resetUrl}</p>
                </div>
                <div class="footer">
                  <p>FrameShift - Django to Flask Migration Tool</p>
                </div>
              </div>
            </body>
          </html>
        `;

      case 'conversion-complete':
        return `
          <!DOCTYPE html>
          <html>
            <head>${styles}</head>
            <body>
              <div class="container">
                <div class="header">
                  <h1>✅ Conversion Complete!</h1>
                </div>
                <div class="content">
                  <p>Hi ${variables.name},</p>
                  <p>Great news! Your Django to Flask conversion for <strong>${variables.projectName}</strong> is complete!</p>
                  <h3>Conversion Summary:</h3>
                  <ul>
                    <li>Accuracy Score: <strong>${variables.accuracyScore}%</strong></li>
                    <li>Models Converted: ${variables.modelsConverted}</li>
                    <li>Views Converted: ${variables.viewsConverted}</li>
                    <li>URLs Converted: ${variables.urlsConverted}</li>
                    <li>Templates Converted: ${variables.templatesConverted}</li>
                  </ul>
                  ${variables.hasIssues ? `<p style="color: #f39c12;">⚠️ Note: ${variables.issuesCount} issue(s) require manual review.</p>` : ''}
                  <a href="${variables.downloadUrl}" class="button">Download Project</a>
                  <a href="${variables.viewReportUrl}" class="button" style="background: #764ba2;">View Full Report</a>
                </div>
                <div class="footer">
                  <p>FrameShift - Django to Flask Migration Tool</p>
                </div>
              </div>
            </body>
          </html>
        `;

      case 'conversion-failed':
        return `
          <!DOCTYPE html>
          <html>
            <head>${styles}</head>
            <body>
              <div class="container">
                <div class="header" style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);">
                  <h1>❌ Conversion Failed</h1>
                </div>
                <div class="content">
                  <p>Hi ${variables.name},</p>
                  <p>Unfortunately, the conversion for <strong>${variables.projectName}</strong> failed.</p>
                  <p><strong>Error:</strong></p>
                  <p style="background: #fff; padding: 15px; border-left: 4px solid #e74c3c; font-family: monospace;">${variables.errorMessage}</p>
                  <p>Please check your project structure and try again. If the problem persists, contact our support team.</p>
                  <a href="${variables.supportUrl}" class="button">Contact Support</a>
                </div>
                <div class="footer">
                  <p>FrameShift - Django to Flask Migration Tool</p>
                </div>
              </div>
            </body>
          </html>
        `;

      default:
        return '<p>Email notification from FrameShift</p>';
    }
  }

  /**
   * Strip HTML tags for plain text version
   */
  stripHtml(html) {
    return html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
  }

  /**
   * Verify SMTP configuration
   */
  async verifyConnection() {
    try {
      await this.transporter.verify();
      logger.info('SMTP connection verified successfully');
      return true;
    } catch (error) {
      logger.error('SMTP connection failed:', error);
      return false;
    }
  }
}

export default new EmailService();
