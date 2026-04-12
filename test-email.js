import 'dotenv/config';
import UserModel from './src/models/user.model.js';
import emailService from './src/services/email.service.js';

async function testEmailFlow() {
  const testEmail = 'alip6059@gmail.com';
  console.log(`Checking user: ${testEmail}`);
  
  try {
    const user = await UserModel.findByEmail(testEmail);
    if (!user) {
      console.log('USER DOES NOT EXIST IN DATABASE!');
      process.exit(0);
    }
    
    console.log(`User exists! Has password: ${!!user.password_hash}`);
    if (!user.password_hash) {
      console.log('User is an OAuth-only user. No email will be sent by design.');
      process.exit(0);
    }
    
    console.log('Attempting to test email service...');
    const isSmtpReady = await emailService.verifyConnection();
    if (!isSmtpReady) {
      console.log('SMTP connection failed. Check SMTP_USER, SMTP_PASS, and provider settings.');
      process.exit(1);
    }
    console.log('SMTP connection successful.');
    
    console.log('Sending test reset email...');
    await emailService.sendPasswordResetEmail(user, 'test-token-12345');
    console.log('Email sent successfully!');
    
  } catch (err) {
    console.error('ERROR OCCURRED:', err);
  }
  process.exit(0);
}

testEmailFlow();
