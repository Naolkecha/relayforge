from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from relayforge.errors import SecurityPolicyError


class SecretCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Fernet key") from exc

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise SecurityPolicyError("secret ciphertext could not be authenticated") from exc
