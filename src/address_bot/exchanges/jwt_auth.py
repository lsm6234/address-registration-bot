from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid


def b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def hs256_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = b64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = encoded_header + b"." + encoded_payload
    signature = b64url(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return (signing_input + b"." + signature).decode()


def jwt_payload(access_key: str, query: str = "", *, include_timestamp: bool = False) -> dict:
    payload = {"access_key": access_key, "nonce": str(uuid.uuid4())}
    if include_timestamp:
        payload["timestamp"] = int(time.time() * 1000)
    if query:
        payload["query_hash"] = hashlib.sha512(query.encode()).hexdigest()
        payload["query_hash_alg"] = "SHA512"
    return payload
