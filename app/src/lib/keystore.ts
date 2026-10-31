/* Ablage des abgeleiteten (nicht exportierbaren) Schlüssels in IndexedDB.
 * Die Passphrase selbst wird nirgends gespeichert.
 *
 * Ab 1.21 zwei weitere Bereiche derselben Datenbank (Version 2):
 *   „zugang“       der Zugang für „Jetzt aktualisieren“ – nur verschlüsselt (mit dem Datenschlüssel)
 *   „lieferungen“  gelieferte Kursaktualisierungen – so verschlüsselt, wie sie vom Server kommen
 * Ohne Datenschlüssel (gesperrt) sind beide nicht lesbar. */

const DB_NAME = 'tr-aktienvergleich';
const STORE = 'schluessel';
export const STORE_ZUGANG = 'zugang';
export const STORE_LIEFERUNGEN = 'lieferungen';
const VERSION = 2;

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, VERSION);
    request.onupgradeneeded = () => {
      for (const name of [STORE, STORE_ZUGANG, STORE_LIEFERUNGEN]) {
        if (!request.result.objectStoreNames.contains(name)) request.result.createObjectStore(name);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/** Gibt es die Datenbank schon? Lesen legt sie nie an (ab Gesamtauftrag: ein Update auf diese Version verändert den Speicher
 * eines Geräts ohne Schlüssel und Zugang nicht). Ohne ``indexedDB.databases`` (ältere Browser) wie bisher öffnen. */
async function present(): Promise<boolean> {
  try {
    const list = (indexedDB as IDBFactory & { databases?: () => Promise<{ name?: string }[]> }).databases;
    if (typeof list !== 'function') return true;
    const dbs = await list.call(indexedDB);
    return dbs.some((d) => d.name === DB_NAME);
  } catch {
    return true;
  }
}

interface StoredKey {
  key: CryptoKey;
  salt: string;
}

export async function loadKey(salt: string): Promise<CryptoKey | null> {
  const value = await getValue<StoredKey>(STORE, 'daten');
  if (!value || value.salt !== salt) return null;
  return value.key;
}

export async function saveKey(key: CryptoKey, salt: string): Promise<boolean> {
  return putValue(STORE, 'daten', { key, salt } satisfies StoredKey);
}

export async function forgetKey(): Promise<void> {
  await deleteValue(STORE, 'daten');
}

/** Wert eines Bereichs lesen; null, wenn es ihn nicht gibt oder der Speicher nicht verfügbar ist. */
export async function getValue<T>(store: string, id: string): Promise<T | null> {
  try {
    if (!(await present())) return null;
    const db = await open();
    const value = await new Promise<T | undefined>((resolve, reject) => {
      const request = db.transaction(store, 'readonly').objectStore(store).get(id);
      request.onsuccess = () => resolve(request.result as T | undefined);
      request.onerror = () => reject(request.error);
    });
    db.close();
    return value ?? null;
  } catch {
    return null;
  }
}

/** Alle Einträge eines Bereichs (Schlüssel und Wert). */
export async function allValues<T>(store: string): Promise<{ id: string; value: T }[]> {
  try {
    if (!(await present())) return [];
    const db = await open();
    const out = await new Promise<{ id: string; value: T }[]>((resolve, reject) => {
      const items: { id: string; value: T }[] = [];
      const request = db.transaction(store, 'readonly').objectStore(store).openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (!cursor) {
          resolve(items);
          return;
        }
        items.push({ id: String(cursor.key), value: cursor.value as T });
        cursor.continue();
      };
      request.onerror = () => reject(request.error);
    });
    db.close();
    return out;
  } catch {
    return [];
  }
}

export async function putValue(store: string, id: string, value: unknown): Promise<boolean> {
  try {
    const db = await open();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(store, 'readwrite');
      tx.objectStore(store).put(value, id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
    return true;
  } catch {
    return false;
  }
}

export async function deleteValue(store: string, id: string): Promise<void> {
  try {
    if (!(await present())) return;
    const db = await open();
    await new Promise<void>((resolve) => {
      const tx = db.transaction(store, 'readwrite');
      tx.objectStore(store).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    });
    db.close();
  } catch {
    /* nichts zu tun */
  }
}

export async function clearStore(store: string): Promise<void> {
  try {
    if (!(await present())) return;
    const db = await open();
    await new Promise<void>((resolve) => {
      const tx = db.transaction(store, 'readwrite');
      tx.objectStore(store).clear();
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    });
    db.close();
  } catch {
    /* nichts zu tun */
  }
}
