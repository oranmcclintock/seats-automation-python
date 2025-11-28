import hashlib
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class Encryption:
    # Constants ported directly from the Node.js app
    CONSTANT_KEY = bytes([13, 146, 236, 36, 206, 221, 229, 5])
    KEY = bytes([241, 55, 32, 79, 252, 55, 172, 77, 98, 94, 137, 19, 247, 113, 197, 166])
    IV = bytes([0, 92, 145, 239, 90, 227, 23, 59, 55, 190, 85, 212, 234, 73, 12, 146])

    @staticmethod
    def transform_string(text):
        """Decrypts the encrypted mobile phone setting."""
        try:
            if not text: return ""
            encrypted_data = base64.b64decode(text)
            cipher = Cipher(algorithms.AES(Encryption.KEY), modes.CBC(Encryption.IV), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            # Remove PKCS7 padding
            pad_len = decrypted[-1]
            return decrypted[:-pad_len].decode('utf-8')
        except Exception as e:
            print(f"Encryption Error: {e}")
            return ""

    @staticmethod
    def compute_hash(a, b):
        """SHA256 hash of a + b, returns first 8 bytes as little-endian integer."""
        combined = a + b
        digest = hashlib.sha256(combined).digest()
        return int.from_bytes(digest[:8], byteorder='little', signed=False)

    @staticmethod
    def compute_fingerprint(fingerprint_input, mobile_phone_encrypted):
        """Generates the ?fp= value for the URL."""
        # 1. Decrypt the mobile phone string
        decrypted_mobile = Encryption.transform_string(mobile_phone_encrypted)

        # 2. Convert the hex string result to bytes
        mobile_bytes = bytes.fromhex(decrypted_mobile)

        # 3. Compute intermediate hash
        mobile_hash_int = Encryption.compute_hash(mobile_bytes, Encryption.CONSTANT_KEY)
        mobile_hash_buffer = mobile_hash_int.to_bytes(8, byteorder='little')

        # 4. Final Hash
        input_bytes = fingerprint_input.encode('utf-8')
        final_hash_int = Encryption.compute_hash(input_bytes, mobile_hash_buffer)

        return str(final_hash_int)