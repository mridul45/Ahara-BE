import secrets

def generate_otp(length: int = 4) -> str:
    """
    Generate a secure, random numeric string of a given length.
    """
    return "".join(str(secrets.randbelow(10)) for _ in range(length))
