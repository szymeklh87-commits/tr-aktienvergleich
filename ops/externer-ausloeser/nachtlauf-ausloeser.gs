/**
 * Externer Auslöser für den Nachtlauf des TR-Aktienvergleichs (Google Apps Script, kostenlos) – optional.
 *
 * Startet in den Nächten nach einem Börsentag kurz nach Mitternacht (Berliner Zeit) den Workflow „Nachtlauf“ über die
 * GitHub-Schnittstelle. Das ist pünktlicher als GitHubs eigener Zeitplan, der geplante Läufe oft Stunden später
 * beginnt. Ohne diesen Auslöser läuft der Nachtlauf trotzdem – nur eben mit GitHubs Verzögerung.
 *
 * Zugangsdaten: Das Token steht ausschließlich in den Skripteigenschaften dieses Projekts (Projekteinstellungen →
 * Skripteigenschaften, Name GITHUB_TOKEN) – nie in diesem Code, nie in einer E-Mail oder einem Chat.
 *
 * Einrichtung (einmalig, etwa 10 Minuten): docs/02_Einrichtung_und_Betrieb.md, Abschnitt „Externer Auslöser“.
 *
 * Bei einem Fehler wirft das Skript keine Ausnahme (sonst schickt Google Fehler-E-Mails); es schreibt nur ins
 * Ausführungsprotokoll (Apps Script → Ausführungen). Bleibt der Stand aus, zeigt die App „Neuer Kursstand überfällig“.
 */

var REPOSITORY = 'szymeklh87-commits/tr-aktienvergleich';
var WORKFLOW = 'nachtlauf.yml';
var BRANCH = 'main';

/** Vom Zeitplan aufgerufen: nur in Nächten nach einem Börsentag (Dienstag- bis Samstagnacht kurz nach Mitternacht). */
function nachtlaufStarten() {
  var heute = Utilities.formatDate(new Date(), 'Europe/Berlin', 'yyyy-MM-dd');
  var tag = new Date(heute + 'T12:00:00Z').getUTCDay(); // 0 = Sonntag, 1 = Montag … 6 = Samstag (Berliner Datum)
  if (tag === 0 || tag === 1) {
    console.log('Nacht nach Samstag bzw. Sonntag – keine neuen Schlusskurse, nichts gestartet.');
    return;
  }
  starten_();
}

/** Zum Ausprobieren von Hand: startet den Nachtlauf sofort. */
function jetztTesten() {
  starten_();
}

function starten_() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    console.log('Skripteigenschaft GITHUB_TOKEN fehlt (Projekteinstellungen → Skripteigenschaften).');
    return false;
  }
  var antwort;
  try {
    antwort = UrlFetchApp.fetch('https://api.github.com/repos/' + REPOSITORY + '/actions/workflows/' + WORKFLOW + '/dispatches', {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      payload: JSON.stringify({ ref: BRANCH }),
      muteHttpExceptions: true,
    });
  } catch (fehler) {
    // Netzfehler (keine HTTP-Antwort): nur protokollieren – ohne das Token, falls es in der Meldung stünde
    var meldung = String((fehler && fehler.message) || fehler).split(token).join('…');
    console.log('GitHub nicht erreichbar (' + meldung + ') – der nächste Termin versucht es erneut.');
    return false;
  }
  var code = antwort.getResponseCode();
  if (code === 204 || code === 200) {
    console.log('Nachtlauf gestartet (HTTP ' + code + ').');
    return true;
  }
  var hilfe = code === 401
    ? 'Token ungültig, abgelaufen oder widerrufen – ein neues anlegen und in den Skripteigenschaften ersetzen.'
    : code === 403
      ? 'Token ohne „Actions: Read and write“ für dieses Repository.'
      : code === 404
        ? 'Repository oder Workflow-Datei nicht gefunden – REPOSITORY und WORKFLOW oben im Skript prüfen.'
        : code === 422
          ? 'GitHub nimmt den Start nicht an – meist ist der Zweig in BRANCH falsch („No ref found“).'
          : code >= 500
            ? 'GitHub ist gestört oder überlastet – der nächste Termin versucht es erneut.'
            : 'Unerwartete Antwort von GitHub – der nächste Termin versucht es erneut.';
  console.log('GitHub hat den Start abgelehnt (HTTP ' + code + nachricht_(antwort, token) + '): ' + hilfe);
  return false;
}

/** Die Fehlermeldung von GitHub („message“ der Antwort), gekürzt und ohne das Token – leer, wenn keine lesbar ist. */
function nachricht_(antwort, token) {
  try {
    var text = String(JSON.parse(antwort.getContentText()).message || '');
    return text ? ', „' + text.slice(0, 200).split(token).join('…') + '“' : '';
  } catch (fehler) {
    return '';
  }
}

/** Einmal ausführen: legt den Zeitplan an (00:25–00:55 Uhr Berliner Zeit, täglich; vorhandene Auslöser dieses Projekts werden ersetzt). */
function zeitplanEinrichten() {
  ScriptApp.getProjectTriggers().forEach(function (ausloeser) {
    ScriptApp.deleteTrigger(ausloeser);
  });
  ScriptApp.newTrigger('nachtlaufStarten').timeBased().everyDays(1).atHour(0).nearMinute(40).inTimezone('Europe/Berlin').create();
  console.log('Zeitplan angelegt: täglich gegen 00:40 Uhr (Europe/Berlin, ± 15 Minuten).');
}
