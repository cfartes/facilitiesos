import hashlib
import hmac
import secrets


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(value: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.scrypt(value.encode(), salt=salt.encode(), n=16384, r=8, p=1)
    return f'scrypt${salt}${key.hex()}'


def verify_password(value: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split('$')
        if algorithm != 'scrypt':
            return False
        actual = hashlib.scrypt(value.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
