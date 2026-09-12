import secrets

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_LENGTH = 7


def generate_code(length: int = DEFAULT_LENGTH) -> str:
    """Cryptographically random base62 string of the given length.

    Uses ``secrets.choice`` so the code is unpredictable (defeats enumeration
    attacks where an attacker would otherwise brute-force sequential codes).
    """
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))


def validate_custom_code(code: str) -> bool:
    """3-32 chars from the URL-safe subset [A-Za-z0-9_-]."""
    if len(code) < 3 or len(code) > 32:
        return False
    return all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in code)