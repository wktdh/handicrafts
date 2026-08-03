"""Generate environment values for Web Push VAPID authentication."""

import base64

from cryptography.hazmat.primitives.asymmetric import ec


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


private_key = ec.generate_private_key(ec.SECP256R1())
numbers = private_key.private_numbers()
private = numbers.private_value.to_bytes(32, "big")
public = b"\x04" + numbers.public_numbers.x.to_bytes(32, "big") + numbers.public_numbers.y.to_bytes(32, "big")

print(f"HANDICRAFTS_VAPID_PUBLIC_KEY={encode(public)}")
print(f"HANDICRAFTS_VAPID_PRIVATE_KEY={encode(private)}")
print("HANDICRAFTS_VAPID_SUBJECT=mailto:your-email@example.com")
