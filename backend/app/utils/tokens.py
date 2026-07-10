import hashlib
import hmac


def hash_bearer_token(secret_key: str, token: str) -> str:
    """HMAC-SHA256 a raw bearer token with `secret_key` (hex digest, 64 chars).

    Keyed (not a bare hash) so a DB leak of the stored hash can't be brute-forced
    into a usable token without also holding the server secret. Shared by every
    single-use bearer-token table (magic links, wingperson invites, ...).
    """
    return hmac.new(secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()
