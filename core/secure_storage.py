import base64
import os
import ctypes
from ctypes import wintypes
from typing import Optional

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char))
    ]

def encrypt_secret(plaintext: str) -> str:
    """Encrypts a sensitive secret string at rest using Windows DPAPI.

    Returns a 'dpapi:<base64>' prefixed string, or the plaintext if not on Windows.
    """
    if not plaintext:
        return ""
    if os.name != "nt":
        return plaintext

    try:
        data_bytes = plaintext.encode("utf-8")
        in_blob = DATA_BLOB(len(data_bytes), ctypes.cast(ctypes.c_char_p(data_bytes), ctypes.POINTER(ctypes.c_char)))
        out_blob = DATA_BLOB()
        res = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "FileTaggerEncryptedSecret",
            None,
            None,
            None,
            0x1,  # CRYPTPROTECT_UI_FORBIDDEN
            ctypes.byref(out_blob)
        )
        if not res:
            return plaintext
        try:
            encrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return "dpapi:" + base64.b64encode(encrypted_bytes).decode("ascii")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return plaintext

def decrypt_secret(ciphertext: str) -> str:
    """Decrypts a DPAPI-encrypted secret string.

    Transparently falls back to the raw string if not encrypted (for backward compatibility).
    """
    if not ciphertext:
        return ""
    if not ciphertext.startswith("dpapi:"):
        return ciphertext
    if os.name != "nt":
        return ciphertext[6:]

    try:
        raw_b64 = ciphertext[6:]
        encrypted_bytes = base64.b64decode(raw_b64)
        in_blob = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.c_char_p(encrypted_bytes), ctypes.POINTER(ctypes.c_char)))
        out_blob = DATA_BLOB()
        res = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0x1,  # CRYPTPROTECT_UI_FORBIDDEN
            ctypes.byref(out_blob)
        )
        if not res:
            return ""
        try:
            decrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return decrypted_bytes.decode("utf-8", errors="replace")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return ""
