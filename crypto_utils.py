"""
Cryptographic utilities for QR data encryption/decryption.
Uses AES-256-CBC for secure QR code content.
"""
import json
import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from config import AES_KEY, AES_IV


def encrypt_qr_data(data: dict) -> str:
    """
    Encrypt a dictionary of student data into a Base64-encoded AES string.
    """
    json_str = json.dumps(data, separators=(',', ':'))
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    padded = pad(json_str.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.urlsafe_b64encode(encrypted).decode('utf-8')


def decrypt_qr_data(encrypted_str: str) -> dict:
    """
    Decrypt a Base64-encoded AES string back into a dictionary.
    Returns None if decryption fails (tampered/invalid QR).
    """
    try:
        encrypted = base64.urlsafe_b64decode(encrypted_str)
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
        return json.loads(decrypted.decode('utf-8'))
    except Exception:
        return None


def generate_data_hash(data: dict) -> str:
    """
    Generate a SHA-256 hash of the student data for integrity verification.
    """
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]
