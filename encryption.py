import hashlib
import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

class LocalEncryption:
    _key = None
    _cipher = None
    KEY_FILE = "data/secret.key"

    @classmethod
    def _get_cipher(cls):
        if cls._cipher:
            return cls._cipher
            
        # Ensure data directory exists (it should from database.py)
        os.makedirs(os.path.dirname(cls.KEY_FILE), exist_ok=True)
        
        if os.path.exists(cls.KEY_FILE):
            with open(cls.KEY_FILE, "rb") as f:
                cls._key = f.read()
        else:
            # Generate a new key if one doesn't exist
            cls._key = Fernet.generate_key()
            with open(cls.KEY_FILE, "wb") as f:
                f.write(cls._key)
        
        cls._cipher = Fernet(cls._key)
        return cls._cipher

    @staticmethod
    def encrypt(raw_text: str) -> str:
        """Encrypts a raw string (like a token) for database storage."""
        if not raw_text: return ""
        try:
            cipher = LocalEncryption._get_cipher()
            return cipher.encrypt(raw_text.encode()).decode()
        except Exception as e:
            print(f"Encryption Error: {e}")
            return raw_text

    @staticmethod
    def decrypt(enc_text: str) -> str:
        """Decrypts a database string back to the raw token."""
        if not enc_text: return ""
        try:
            cipher = LocalEncryption._get_cipher()
            return cipher.decrypt(enc_text.encode()).decode()
        except Exception:

            return enc_text


class Encryption:

    CONSTANT_KEY = bytes([13, 146, 236, 36, 206, 221, 229, 5])
    KEY = bytes([241, 55, 32, 79, 252, 55, 172, 77, 98, 94, 137, 19, 247, 113, 197, 166])
    IV = bytes([0, 92, 145, 239, 90, 227, 23, 59, 55, 190, 85, 212, 234, 73, 12, 146])

    @staticmethod
    def transform_string(text):
        try:
            if not text: return ""
            encrypted_data = base64.b64decode(text)
            cipher = Cipher(algorithms.AES(Encryption.KEY), modes.CBC(Encryption.IV), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            pad_len = decrypted[-1]
            return decrypted[:-pad_len].decode('utf-8')
        except Exception as e:
            print(f"Encryption Error: {e}")
            return ""

    @staticmethod
    def compute_hash(a, b):
        combined = a + b
        digest = hashlib.sha256(combined).digest()
        return int.from_bytes(digest[:8], byteorder='little', signed=False)

    @staticmethod
    def compute_fingerprint(fingerprint_input, mobile_phone_encrypted):
        decrypted_mobile = Encryption.transform_string(mobile_phone_encrypted)
        mobile_bytes = bytes.fromhex(decrypted_mobile)
        mobile_hash_int = Encryption.compute_hash(mobile_bytes, Encryption.CONSTANT_KEY)
        mobile_hash_buffer = mobile_hash_int.to_bytes(8, byteorder='little')
        input_bytes = fingerprint_input.encode('utf-8')
        final_hash_int = Encryption.compute_hash(input_bytes, mobile_hash_buffer)
        return str(final_hash_int)