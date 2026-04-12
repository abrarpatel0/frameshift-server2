-- Create verification_tokens table for email verification and password reset
CREATE TABLE IF NOT EXISTS verification_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('email_verification', 'password_reset')),
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP
);

-- Create indexes only if they don't exist
CREATE INDEX IF NOT EXISTS idx_verification_tokens_token ON verification_tokens(token);
CREATE INDEX IF NOT EXISTS idx_verification_tokens_user_id ON verification_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_verification_tokens_type ON verification_tokens(type);
CREATE INDEX IF NOT EXISTS idx_verification_tokens_expires_at ON verification_tokens(expires_at);

-- Create function to automatically delete expired tokens
CREATE OR REPLACE FUNCTION delete_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM verification_tokens
    WHERE expires_at < NOW() AND used = false;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE verification_tokens IS 'Stores verification tokens for email verification and password reset';
COMMENT ON COLUMN verification_tokens.type IS 'Type of token: email_verification or password_reset';
COMMENT ON COLUMN verification_tokens.expires_at IS 'Token expiration timestamp';
COMMENT ON COLUMN verification_tokens.used IS 'Whether the token has been used';
