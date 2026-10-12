/* Ablage des abgeleiteten (nicht exportierbaren) Schlüssels in IndexedDB.
 * Die Passphrase selbst wird nirgends gespeichert. */

const DB_NAME = 'tr-aktienvergleich';
const STORE = 'schluessel';

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

interface StoredKey {
  key: CryptoKey;
  salt: string;
}

export async function loadKey(salt: string): Promise<CryptoKey | null> {
  try {
    const db = await open();
    const value = await new Promise<StoredKey | undefined>((resolve, reject) => {
      const request = db.transaction(STORE, 'readonly').objectStore(STORE).get('daten');
      request.onsuccess = () => resolve(request.result as StoredKey | undefined);
      request.onerror = () => reject(request.error);
    });
    db.close();
    if (!value || value.salt !== salt) return null;
    return value.key;
  } catch {
    return null;
  }
}

export async function saveKey(key: CryptoKey, salt: string): Promise<boolean> {
  try {
    const db = await open();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put({ key, salt } satisfies StoredKey, 'daten');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
    return true;
  } catch {
    return false;
  }
}

export async function forgetKey(): Promise<void> {
  try {
    const db = await open();
    await new Promise<void>((resolve) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).delete('daten');
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    });
    db.close();
  } catch {
    /* nichts zu tun */
  }
}
