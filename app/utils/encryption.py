"""Encryption utilities."""
import os
import base64
from cryptography.fernet import Fernet
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize Fernet cipher
def _get_encryption_key():
    """Get or generate encryption key."""
    key_env = os.getenv("ENCRYPTION_KEY", "")
    
    if key_env:
        try:
            # Validate that it's a proper Fernet key (base64 encoded 32 bytes)
            key_bytes = key_env.encode() if isinstance(key_env, str) else key_env
            # Test if it's a valid Fernet key
            Fernet(key_bytes)
            return key_bytes
        except Exception as e:
            logger.warning(f"Invalid ENCRYPTION_KEY format: {str(e)}")
            # Fall through to generate new key
    
    # Generate new key if not provided or invalid
    new_key = Fernet.generate_key()
    logger.warning("ENCRYPTION_KEY not set or invalid. Generated temporary key. Set ENCRYPTION_KEY in .env for persistence.")
    return new_key

try:
    ENCRYPTION_KEY = _get_encryption_key()
    CIPHER = Fernet(ENCRYPTION_KEY)
except Exception as e:
    logger.warning(f"Failed to initialize encryption cipher: {str(e)}. Using dummy cipher.")
    # Fallback for testing
    CIPHER = None


def encrypt(plaintext):
    """Encrypt plaintext string."""
    try:
        if not CIPHER:
            logger.warning("Cipher not initialized, returning plaintext")
            return plaintext
        
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()
        encrypted = CIPHER.encrypt(plaintext)
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        raise


def decrypt(ciphertext):
    """Decrypt ciphertext string."""
    try:
        if not CIPHER:
            logger.warning("Cipher not initialized, returning ciphertext")
            return ciphertext
        
        if isinstance(ciphertext, str):
            ciphertext = ciphertext.encode()
        decrypted = CIPHER.decrypt(ciphertext)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        raise
