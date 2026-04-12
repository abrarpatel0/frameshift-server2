import nodemailer from 'nodemailer';
import fs from 'fs';
import path from 'path';

async function setupEthereal() {
  try {
    const testAccount = await nodemailer.createTestAccount();
    console.log('Ethereal Account Created:', testAccount);
    
    const envPath = path.join(process.cwd(), '.env');
    let envContent = fs.readFileSync(envPath, 'utf8');
    
    // Replace SMTP credentials
    envContent = envContent.replace(/SMTP_HOST=.*/, `SMTP_HOST=smtp.ethereal.email`);
    envContent = envContent.replace(/SMTP_PORT=.*/, `SMTP_PORT=587`);
    envContent = envContent.replace(/SMTP_USER=.*/, `SMTP_USER=${testAccount.user}`);
    envContent = envContent.replace(/SMTP_PASS=.*/, `SMTP_PASS=${testAccount.pass}`);
    envContent = envContent.replace(/SMTP_FROM=.*/, `SMTP_FROM=Test Sender<test@ethereal.email>`);
    
    fs.writeFileSync(envPath, envContent);
    console.log('Successfully updated .env with Ethereal credentials.');
  } catch (error) {
    console.error('Error creating ethereal account:', error);
  }
}

setupEthereal();
