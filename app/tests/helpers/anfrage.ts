/* Hilfsprogramm für den Python-Test test_kursaktualisierung: erzeugt mit dem Code der App eine verschlüsselte Anfrage.
 * Aufruf: node --import tsx tests/helpers/anfrage.ts <kennung> <zeit_ms> <isin:symbol,…> */

import { requestAad, requestPayload } from '../../src/lib/aktualisierung.ts';
import { bytesToBase64, deriveKey, encodeJson } from '../../src/lib/container.ts';

const [kennung, nowText, valuesText] = process.argv.slice(2);
const values = valuesText.split(',').map((pair) => {
  const [isin, symbol] = pair.split(':');
  return { isin, symbol };
});
const key = await deriveKey('Testpassphrase-nur-fuer-Tests', { enabled: true, salt_b64: Buffer.from('0123456789abcdef').toString('base64'), iterations: 1000 } as never);
const payload = requestPayload(kennung, 'merkliste', values, 1, [values[0].isin], Number(nowText));
process.stdout.write(bytesToBase64(await encodeJson(payload, key, requestAad(kennung))));
