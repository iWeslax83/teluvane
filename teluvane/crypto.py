# teluvane/teluvane/crypto.py
import os

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    key = os.environ["TELUVANE_SECRET_KEY"]
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
