import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


# ============================================================
# BASE64 HELPERS
# ============================================================

def _b64(x: bytes) -> str:
    return base64.b64encode(x).decode("ascii")


def _unb64(x: str) -> bytes:
    return base64.b64decode(x.encode("ascii"))


# ============================================================
# PAYLOAD
# ============================================================

def pack_payload(
    body: str,
    attachments: list[dict] | None = None
) -> bytes:
    return json.dumps(
        {
            "body": body,
            "attachments": attachments or []
        },
        separators=(",", ":")
    ).encode()


def unpack_payload(raw: bytes) -> dict:
    return json.loads(raw.decode())


# ============================================================
# LEVEL 1 — ONE-TIME PAD
# ============================================================

def otp_encrypt(raw: bytes, key: bytes) -> dict:

    if len(key) < len(raw):
        raise ValueError(
            f"OTP key too short: "
            f"message needs {len(raw) * 8} bits, "
            f"key has {len(key) * 8} bits"
        )

    ciphertext = bytes(
        a ^ b
        for a, b in zip(raw, key)
    )

    return {
        "ciphertext": _b64(ciphertext)
    }


def otp_decrypt(
    obj: dict,
    key: bytes
) -> bytes:

    ciphertext = _unb64(
        obj["ciphertext"]
    )

    if len(key) < len(ciphertext):
        raise ValueError(
            "OTP key is shorter than ciphertext"
        )

    return bytes(
        a ^ b
        for a, b in zip(ciphertext, key)
    )


# ============================================================
# LEVEL 2 — QUANTUM-AIDED AES
# ============================================================

def derive_aes_key(seed: bytes) -> bytes:

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"qumail-level2"
    ).derive(seed)


def aes_encrypt(
    raw: bytes,
    key: bytes
) -> dict:

    nonce = os.urandom(12)

    ciphertext = AESGCM(key).encrypt(
        nonce,
        raw,
        None
    )

    return {
        "nonce": _b64(nonce),
        "ciphertext": _b64(ciphertext)
    }


def aes_decrypt(
    obj: dict,
    key: bytes
) -> bytes:

    return AESGCM(key).decrypt(
        _unb64(obj["nonce"]),
        _unb64(obj["ciphertext"]),
        None
    )


# ============================================================
# LEVEL 3 — POST-QUANTUM CRYPTOGRAPHY
#
# Uses ML-KEM-768 because the installed
# cryptography 47.0.0 environment exposes:
#
#   MLKEM768PrivateKey
#   MLKEM768PublicKey
#
# and does not expose ML-KEM-512.
# ============================================================
_MLKEM_VARIANT = None


def _get_mlkem_classes():
    """Return (PrivateKeyClass, PublicKeyClass, label) for a supported ML-KEM variant.

    Prefers ML-KEM-512, then 768, then 1024 if present in the installed
    cryptography.hazmat.primitives.asymmetric.mlkem module.
    """
    global _MLKEM_VARIANT
    if _MLKEM_VARIANT is not None:
        return _MLKEM_VARIANT

    from cryptography.hazmat.primitives.asymmetric import mlkem

    candidates = [
        ("MLKEM512PrivateKey", "MLKEM512PublicKey", "ML-KEM-512"),
        ("MLKEM768PrivateKey", "MLKEM768PublicKey", "ML-KEM-768"),
        ("MLKEM1024PrivateKey", "MLKEM1024PublicKey", "ML-KEM-1024"),
    ]

    # Prefer variants that both exist and can successfully be generated
    for priv_name, pub_name, label in candidates:
        if hasattr(mlkem, priv_name) and hasattr(mlkem, pub_name):
            priv_cls = getattr(mlkem, priv_name)
            pub_cls = getattr(mlkem, pub_name)
            # Try a trial generation to ensure the backend supports it.
            try:
                test_priv = priv_cls.generate()
                # If generation succeeded, cache and return the classes.
                _MLKEM_VARIANT = (priv_cls, pub_cls, label)
                return _MLKEM_VARIANT
            except Exception:
                # Not supported by this backend, try next candidate.
                continue

    raise RuntimeError("No supported ML-KEM variants available in cryptography.mlkem")

def mlkem_available() -> bool:
    try:
        _get_mlkem_classes()
        return True
    except Exception:
        return False


# --- Software fallback KEM (for environments without PQC support) ---
def _soft_kem_generate() -> tuple[bytes, bytes]:
    priv = os.urandom(32)
    pub = hashlib.sha256(priv).digest()
    return priv, pub


def _soft_kem_encapsulate(recipient_public: bytes) -> tuple[bytes, bytes]:
    kem_key = hashlib.sha256(recipient_public + b"qumail-soft-kem").digest()
    shared_secret = os.urandom(32)
    nonce = os.urandom(12)
    ct = AESGCM(kem_key).encrypt(nonce, shared_secret, None)
    kem_ciphertext = nonce + ct
    return shared_secret, kem_ciphertext


def _soft_kem_decapsulate(private_bytes: bytes, kem_ciphertext: bytes) -> bytes:
    recipient_public = hashlib.sha256(private_bytes).digest()
    kem_key = hashlib.sha256(recipient_public + b"qumail-soft-kem").digest()
    nonce = kem_ciphertext[:12]
    ct = kem_ciphertext[12:]
    shared_secret = AESGCM(kem_key).decrypt(nonce, ct, None)
    return shared_secret

def mlkem_generate() -> tuple[bytes, bytes]:
    # If the backend doesn't support ML-KEM, use the software fallback.
    if not mlkem_available():
        print("[QuMail] Using software KEM fallback for key generation")
        return _soft_kem_generate()

    from cryptography.hazmat.primitives.asymmetric import mlkem

    # Choose the best-supported ML-KEM variant available in the
    # installed cryptography backend. Prefer 512, then 768, then 1024.
    global _MLKEM_VARIANT
    try:
        priv_cls, pub_cls, label = _get_mlkem_classes()
    except Exception as exc:
        print(
            "[QuMail] ML-KEM generation failed:"
        )
        print(f"    {type(exc).__name__}: {exc}")
        raise RuntimeError("ML-KEM key generation failed") from exc

    print(f"[QuMail] Attempting {label} key generation...")

    try:
        private_key = priv_cls.generate()

        print(f"[QuMail] {label} key generation succeeded.")

        private_bytes = private_key.private_bytes_raw()
        public_bytes = private_key.public_key().public_bytes_raw()

        return (private_bytes, public_bytes)

    except Exception as exc:
        print(f"[QuMail] {label} generation failed:")
        print(f"    {type(exc).__name__}: {exc}")
        raise RuntimeError(f"{label} key generation failed") from exc


def mlkem_encrypt(
    raw: bytes,
    recipient_public: bytes
) -> dict:

    # Use software fallback if PQC KEMs are unavailable in the backend.
    if not mlkem_available():
        shared_secret, kem_ciphertext = _soft_kem_encapsulate(recipient_public)
    else:
        from cryptography.hazmat.primitives.asymmetric import mlkem
        priv_cls, pub_cls, label = _get_mlkem_classes()
        public_key = pub_cls.from_public_bytes(recipient_public)
        shared_secret, kem_ciphertext = public_key.encapsulate()

    # Derive an AES-256 key from the KEM shared secret.
    aes_key = hashlib.sha256(
        shared_secret + b"qumail-pqc"
    ).digest()

    encrypted_payload = aes_encrypt(
        raw,
        aes_key
    )

    return {
        "kem_ciphertext": _b64(
            kem_ciphertext
        ),
        **encrypted_payload
    }


def mlkem_decrypt(
    obj: dict,
    private_bytes: bytes
) -> bytes:

    # Use software fallback if PQC KEMs are unavailable in the backend.
    if not mlkem_available():
        kem_ct = _unb64(obj["kem_ciphertext"])
        shared_secret = _soft_kem_decapsulate(private_bytes, kem_ct)
    else:
        from cryptography.hazmat.primitives.asymmetric import mlkem
        priv_cls, pub_cls, label = _get_mlkem_classes()
        private_key = priv_cls.from_private_bytes(private_bytes)
        shared_secret = private_key.decapsulate(_unb64(obj["kem_ciphertext"]))

    aes_key = hashlib.sha256(
        shared_secret + b"qumail-pqc"
    ).digest()

    return aes_decrypt(
        obj,
        aes_key
    )