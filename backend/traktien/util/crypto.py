"""Dateicontainer für veröffentlichte Daten: gzip + optional AES-256-GCM.

Format (Bytefolge)::

    "TRA1" | flags (1 Byte) | [IV 12 Byte, nur verschlüsselt] | Nutzlast

flags: Bit 0 = verschlüsselt, Bit 1 = gzip-komprimiert.
Verschlüsselte Nutzlast = AES-GCM(Schlüssel, IV, gzip(JSON), AAD = relativer Pfad).
Der Schlüssel wird mit PBKDF2-HMAC-SHA256 aus einer Passphrase abgeleitet.
Die AAD bindet jede Datei an ihren Pfad; vertauschte Dateien lassen sich nicht
unbemerkt entschlüsseln.

Die Passphrase liegt ausschließlich serverseitig (GitHub-Secret) und auf dem Gerät
des Nutzers. Sie wird nie geloggt, nie exportiert und nie in den Service-Worker-Cache
geschrieben; dort liegen nur verschlüsselte Bytes.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"TRA1"
FLAG_ENCRYPTED = 0x01
FLAG_GZIP = 0x02
KDF_ITERATIONS = 600_000
CHECK_PLAINTEXT = b"TR-AKTIENVERGLEICH-SCHLUESSEL-OK"
CHECK_AAD = "crypto-check"


class ContainerError(ValueError):
    """Ungültiger oder nicht entschlüsselbarer Container."""


@dataclass(frozen=True)
class KeyMaterial:
    key: bytes
    salt: bytes
    iterations: int


def derive_key(passphrase: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> KeyMaterial:
    if not passphrase:
        raise ValueError("Leere Passphrase ist nicht zulässig")
    if len(salt) < 16:
        raise ValueError("Salt muss mindestens 16 Byte lang sein")
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)
    return KeyMaterial(key=key, salt=salt, iterations=iterations)


def new_salt() -> bytes:
    return os.urandom(16)


def pack(plaintext: bytes, key: KeyMaterial | None, aad: str) -> bytes:
    compressed = gzip.compress(plaintext, compresslevel=9, mtime=0)
    if key is None:
        return MAGIC + bytes([FLAG_GZIP]) + compressed
    iv = os.urandom(12)
    ciphertext = AESGCM(key.key).encrypt(iv, compressed, aad.encode("utf-8"))
    return MAGIC + bytes([FLAG_GZIP | FLAG_ENCRYPTED]) + iv + ciphertext


def unpack(blob: bytes, key: KeyMaterial | None, aad: str) -> bytes:
    if len(blob) < 5 or blob[:4] != MAGIC:
        raise ContainerError("Unbekanntes Dateiformat")
    flags = blob[4]
    payload = blob[5:]
    if flags & FLAG_ENCRYPTED:
        if key is None:
            raise ContainerError("Datei ist verschlüsselt, aber kein Schlüssel vorhanden")
        if len(payload) < 12 + 16:
            raise ContainerError("Verschlüsselte Datei ist zu kurz")
        iv, ciphertext = payload[:12], payload[12:]
        try:
            payload = AESGCM(key.key).decrypt(iv, ciphertext, aad.encode("utf-8"))
        except Exception as exc:  # cryptography wirft InvalidTag
            raise ContainerError("Entschlüsselung fehlgeschlagen (falscher Schlüssel oder veränderte Datei)") from exc
    if flags & FLAG_GZIP:
        payload = gzip.decompress(payload)
    return payload


def crypto_descriptor(key: KeyMaterial | None) -> dict:
    """Öffentliche Beschreibung für ``data/crypto.json`` (enthält kein Geheimnis)."""
    if key is None:
        return {"schema": "tr-crypto/1", "enabled": False}
    check = pack(CHECK_PLAINTEXT, key, CHECK_AAD)
    return {
        "schema": "tr-crypto/1",
        "enabled": True,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": key.iterations,
        "salt_b64": base64.b64encode(key.salt).decode("ascii"),
        "cipher": "AES-256-GCM",
        "container": "TRA1",
        "check_b64": base64.b64encode(check).decode("ascii"),
        "check_aad": CHECK_AAD,
    }


def verify_descriptor(descriptor: dict, passphrase: str) -> KeyMaterial:
    salt = base64.b64decode(descriptor["salt_b64"])
    key = derive_key(passphrase, salt, int(descriptor["iterations"]))
    check = base64.b64decode(descriptor["check_b64"])
    if unpack(check, key, descriptor.get("check_aad", CHECK_AAD)) != CHECK_PLAINTEXT:
        raise ContainerError("Schlüsselprüfung fehlgeschlagen")
    return key
