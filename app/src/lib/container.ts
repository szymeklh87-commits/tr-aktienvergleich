/* TRA1-Container: gzip und optional AES-256-GCM (Schlüssel aus PBKDF2-HMAC-SHA256). */

import type { CryptoDescriptor } from './types';

const MAGIC = [0x54, 0x52, 0x41, 0x31];
const FLAG_ENCRYPTED = 0x01;
const FLAG_GZIP = 0x02;
const CHECK_PLAINTEXT = 'TR-AKTIENVERGLEICH-SCHLUESSEL-OK';

export class NeedKeyError extends Error {
  constructor() {
    super('Für diese Daten wird der Zugangsschlüssel benötigt.');
  }
}

export class DecodeError extends Error {}

function bytesFrom(buffer: ArrayBuffer | Uint8Array): Uint8Array {
  return buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
}

export function base64ToBytes(text: string): Uint8Array {
  const binary = atob(text);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

async function gunzip(data: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export function isEncrypted(buffer: ArrayBuffer | Uint8Array): boolean {
  const bytes = bytesFrom(buffer);
  return bytes.length > 4 && (bytes[4] & FLAG_ENCRYPTED) !== 0;
}

export async function decodeBytes(buffer: ArrayBuffer | Uint8Array, key: CryptoKey | null, aad: string): Promise<Uint8Array> {
  const bytes = bytesFrom(buffer);
  if (bytes.length < 5 || MAGIC.some((value, i) => bytes[i] !== value)) {
    throw new DecodeError('Unbekanntes Dateiformat');
  }
  const flags = bytes[4];
  let payload = bytes.subarray(5);
  if (flags & FLAG_ENCRYPTED) {
    if (!key) throw new NeedKeyError();
    const iv = payload.subarray(0, 12);
    const ciphertext = payload.subarray(12);
    try {
      const plain = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: iv as BufferSource, additionalData: new TextEncoder().encode(aad) as BufferSource },
        key,
        ciphertext as BufferSource,
      );
      payload = new Uint8Array(plain);
    } catch {
      throw new DecodeError('Entschlüsselung fehlgeschlagen – falscher Schlüssel oder veränderte Datei');
    }
  }
  if (flags & FLAG_GZIP) payload = await gunzip(payload);
  return payload;
}

export async function decodeJson<T>(buffer: ArrayBuffer | Uint8Array, key: CryptoKey | null, aad: string): Promise<T> {
  const payload = await decodeBytes(buffer, key, aad);
  return JSON.parse(new TextDecoder().decode(payload)) as T;
}

export async function deriveKey(passphrase: string, descriptor: CryptoDescriptor): Promise<CryptoKey> {
  if (!descriptor.salt_b64 || !descriptor.iterations) throw new DecodeError('Schlüsselparameter fehlen');
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(passphrase) as BufferSource, 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt: base64ToBytes(descriptor.salt_b64) as BufferSource, iterations: descriptor.iterations },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt'],
  );
}

/** Prüft den Schlüssel am öffentlichen Prüfwert; wirft bei falscher Passphrase. */
export async function verifyKey(key: CryptoKey, descriptor: CryptoDescriptor): Promise<void> {
  if (!descriptor.check_b64) throw new DecodeError('Prüfwert fehlt');
  const plain = await decodeBytes(base64ToBytes(descriptor.check_b64), key, descriptor.check_aad ?? 'crypto-check');
  if (new TextDecoder().decode(plain) !== CHECK_PLAINTEXT) throw new DecodeError('Schlüsselprüfung fehlgeschlagen');
}
