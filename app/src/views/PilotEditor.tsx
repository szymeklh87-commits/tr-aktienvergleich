/* Regel-Baukasten (Gesamtauftrag, Abschnitte 27.4 und 31): eigene Kauf- und Verkaufsregeln aus allen geeigneten
 * Kennzahlen des Katalogs, frei einstellbare Gewinnmitnahmen (+30/+50/+100 % oder eigene, ganz oder als Leiter), Stops und
 * Zeitplan. Ergebnis ist eine geprüfte Regel als Daten (Schema tr-regel/1) – kein Programmcode. Die App prüft sofort; der
 * tägliche Lauf prüft verbindlich, bevor eine Regel handelt (jede Änderung = neue Version, neuer Test). */

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { EmptyState, KeyValues, Notice, SectionTitle, Segmented } from '../components/ui';
import { idAusName, ableiten, GEWICHTE, regelPruefen, standardRef, type Fehler } from '../lib/regelpruefung';
import { ausdruckText, regelZusammenfassung, WOCHENTAG, type Ausdruck, type Gewinnmitnahme, type Katalog, type KatalogKennzahl, type KatalogParam, type KennzahlRef, type PilotStand, type Quelle, type Regel } from '../lib/pilot';
import type { Route } from '../lib/router';
import { useApp } from '../state/AppState';

type Rolle = 'filter' | 'sortierung' | 'kapital' | 'ausstieg';
type Bedingung = Extract<Ausdruck, { kennzahl: KennzahlRef }>;
type Zeile = { nicht: boolean; b: Bedingung };
type Gruppe = { op: 'und' | 'oder'; zeilen: Zeile[] };

const ENTWURF = 'tr-pilot-regelentwurf';

const OP_LABEL: Record<string, string> = {
  '>': 'größer als',
  '>=': 'mindestens',
  '<': 'kleiner als',
  '<=': 'höchstens',
  '==': 'gleich',
  '!=': 'ungleich',
  zwischen: 'zwischen',
  gekreuzt_aufwaerts: 'kreuzt nach oben',
  gekreuzt_abwaerts: 'kreuzt nach unten',
  ist_wahr: 'ist erfüllt',
  ist_falsch: 'ist nicht erfüllt',
  in: 'ist eine von',
  nicht_in: 'ist keine von',
  neu_eingetreten: 'neu bis Platz',
  verlassen: 'verlässt Platz',
};

function num(value: string): number {
  const v = Number(value.replace(',', '.'));
  return Number.isFinite(v) ? v : NaN;
}

function clone<T>(x: T): T {
  return JSON.parse(JSON.stringify(x)) as T;
}

/** Flache Gruppe aus einem Ausdruck – null, wenn tiefer verschachtelt (dann nur als Text gezeigt). */
export function alsGruppe(a: Ausdruck | null | undefined): Gruppe | null {
  if (!a) return { op: 'und', zeilen: [] };
  const zeile = (x: Ausdruck): Zeile | null => {
    if ('nicht' in x && 'kennzahl' in x.nicht) return { nicht: true, b: x.nicht as Bedingung };
    if ('kennzahl' in x) return { nicht: false, b: x as Bedingung };
    return null;
  };
  if ('und' in a || 'oder' in a) {
    const op = 'und' in a ? 'und' : 'oder';
    const items = ('und' in a ? a.und : (a as { oder: Ausdruck[] }).oder).map(zeile);
    return items.every((z): z is Zeile => z !== null) ? { op, zeilen: items } : null;
  }
  const z = zeile(a);
  return z ? { op: 'und', zeilen: [z] } : null;
}

export function ausGruppe(g: Gruppe): Ausdruck | null {
  if (!g.zeilen.length) return null;
  const items = g.zeilen.map((z) => (z.nicht ? { nicht: z.b } : z.b)) as Ausdruck[];
  return g.op === 'und' ? { und: items } : { oder: items };
}

function speichernEntwurf(r: Regel) {
  try {
    localStorage.setItem(ENTWURF, JSON.stringify(r));
  } catch {
    /* nur Bequemlichkeit */
  }
}

function ladenEntwurf(): Regel | null {
  try {
    const raw = localStorage.getItem(ENTWURF);
    return raw ? (JSON.parse(raw) as Regel) : null;
  } catch {
    return null;
  }
}

/** Start der Bearbeitung aus der Adresse: Vorlage, Kopie, neue Version, Kennzahl („Als Regel verwenden“) oder Entwurf. */
export function startRegel(stand: PilotStand, route: Route): Regel | null {
  const vorlagen = stand.vorlagen ?? {};
  const p = route.params;
  const von = p.get('von');
  if (von && stand.regeln[von]) return ableiten(stand.regeln[von], p.get('art') === 'version' ? 'version' : 'kopie');
  const v = p.get('vorlage');
  if (v && vorlagen[v]) return ableiten(vorlagen[v], 'kopie');
  const k = p.get('kennzahl');
  const basis = vorlagen.lineal ?? Object.values(vorlagen)[0];
  if (k && basis) {
    const kz = stand.katalog?.kennzahlen.find((x) => x.id === k);
    if (kz) {
      const r = ableiten(basis, 'kopie');
      r.name = `Eigene Regel mit ${kz.name}`.slice(0, 80);
      r.id = idAusName(r.name);
      const ref = standardRef(kz);
      for (const prm of kz.parameter) {
        const given = p.get(`p.${prm.name}`);
        if (given !== null) ref.parameter[prm.name] = prm.art === 'auswahl' ? (prm.werte ?? []).find((w) => String(w) === given) ?? given : Number(given);
      }
      const op = kz.operatoren.includes('>') ? '>' : kz.operatoren[0];
      const cond: Bedingung = { kennzahl: ref, op, ...(op === 'ist_wahr' || op === 'ist_falsch' ? {} : { wert: 0 }) };
      if (kz.rollen.includes('filter')) r.filter = { und: [cond] };
      else if (kz.rollen.includes('sortierung')) r.sortierung = { schluessel: [{ kennzahl: ref, richtung: kz.besser === 'niedrig' ? 'auf' : 'ab' }] };
      return r;
    }
  }
  return ladenEntwurf() ?? (basis ? ableiten(basis, 'kopie') : null);
}

export function PilotEditor({ stand, route }: { stand: PilotStand; route: Route }) {
  const katalog = stand.katalog;
  const [regel, setRegel] = useState<Regel | null>(() => startRegel(stand, route));
  const [idFest] = useState(() => route.params.get('art') === 'version');
  useEffect(() => {
    if (regel) speichernEntwurf(regel);
  }, [regel]);
  const fehler = useMemo(() => (regel && katalog ? regelPruefen(regel, katalog) : []), [regel, katalog]);
  if (!katalog || !regel) {
    return <EmptyState title="Regel-Baukasten nicht verfügbar">Der Spielgeld-Stand enthält noch keinen Kennzahlenkatalog. Er kommt mit dem nächsten täglichen Lauf.</EmptyState>;
  }
  const set = (change: (r: Regel) => void) => {
    const next = clone(regel);
    change(next);
    setRegel(next);
  };
  const vergeben = new Set(Object.values(stand.regeln).map((r) => r.id));
  const idKollision = !idFest && vergeben.has(regel.id);
  return (
    <div className="pilot-editor">
      <SectionTitle>Regel-Baukasten</SectionTitle>
      <p className="section-note">
        Bausteine aus {katalog.kennzahlen.length} Kennzahlen (Ranglisten, Häufigkeit, Kurs und Technik, Umsatz, Datenqualität, Analysten, Depot). Fehlende Daten machen eine Bedingung
        „nicht prüfbar“ – dann wird nicht gekauft. Zentrale Risikogrenzen gelten immer und lassen sich hier nicht erhöhen.
      </p>
      <Vorlagenwahl stand={stand} onPick={(r) => setRegel(r)} />

      <Abschnitt titel="Name">
        <label className="field">
          <span className="field-label">Name der Regel</span>
          <input
            className="input"
            type="text"
            maxLength={80}
            value={regel.name}
            onInput={(e: Event) => {
              const name = (e.target as HTMLInputElement).value;
              set((r) => {
                r.name = name;
                if (!idFest) r.id = idAusName(name);
              });
            }}
          />
        </label>
        <label className="field">
          <span className="field-label">Beschreibung (optional)</span>
          <textarea className="input" rows={2} maxLength={500} value={regel.beschreibung ?? ''} onInput={(e: Event) => set((r) => void (r.beschreibung = (e.target as HTMLTextAreaElement).value))} />
        </label>
        <p className="section-note">
          Kennung {regel.id}, Version {regel.version}
          {idKollision ? ' – diese Kennung gibt es schon: bitte einen anderen Namen wählen (oder die vorhandene Regel als neue Version bearbeiten).' : ''}
        </p>
      </Abschnitt>

      <Abschnitt titel="Kandidaten">
        {regel.kandidaten.map((q, i) => (
          <QuelleEditor
            key={i}
            q={q}
            onChange={(nq) => set((r) => void (r.kandidaten[i] = nq))}
            onRemove={regel.kandidaten.length > 1 ? () => set((r) => void r.kandidaten.splice(i, 1)) : undefined}
          />
        ))}
        {regel.kandidaten.length < 8 ? <QuelleNeu onAdd={(q) => set((r) => void r.kandidaten.push(q))} /> : null}
        <p className="section-note">Mehrere Quellen werden vereinigt; jede Aktie zählt einmal.</p>
      </Abschnitt>

      <Abschnitt titel="Filter (alle Kandidaten müssen sie erfüllen)">
        <BedingungenEditor katalog={katalog} rolle="filter" wert={regel.filter} onChange={(a) => set((r) => void (r.filter = a))} />
      </Abschnitt>

      <Abschnitt titel="Sortierung">
        <SortierungEditor katalog={katalog} regel={regel} set={set} />
      </Abschnitt>

      <Abschnitt titel="Auswahl und Kapital">
        <div className="pilot-row">
          <Zahl label="Anzahl Aktien" value={regel.auswahl.anzahl} min={1} max={50} onChange={(v) => set((r) => void (r.auswahl.anzahl = v))} />
          <Zahl
            label="höchstens je Branche (leer = ohne)"
            value={regel.auswahl.max_je_branche ?? NaN}
            min={1}
            max={50}
            optional
            onChange={(v) => set((r) => void (r.auswahl.max_je_branche = Number.isFinite(v) ? v : null))}
          />
        </div>
        <Segmented
          label="Kapital je Aktie"
          value={regel.kapital.art}
          onChange={(art) =>
            set((r) => {
              r.kapital = art === 'ziel' ? { art, ziele_pct: Array.from({ length: r.auswahl.anzahl }, () => Math.round((10000 / r.auswahl.anzahl)) / 100) } : { art };
            })
          }
          options={[
            { value: 'gleich', label: 'gleich' },
            { value: 'risiko', label: 'nach Risiko' },
            { value: 'ziel', label: 'Zielgewichte' },
          ]}
        />
        {regel.kapital.art === 'ziel' ? (
          <label className="field">
            <span className="field-label">Zielgewichte je Platz in % (Summe 100), durch Leerzeichen getrennt</span>
            <input
              className="input"
              type="text"
              inputMode="decimal"
              value={(regel.kapital.ziele_pct ?? []).join(' ')}
              onInput={(e: Event) => {
                const parts = (e.target as HTMLInputElement).value.trim().split(/\s+/).filter(Boolean).map(num);
                set((r) => void (r.kapital.ziele_pct = parts));
              }}
            />
          </label>
        ) : null}
      </Abschnitt>

      <Abschnitt titel="Kauf">
        <label className="field">
          <span className="field-label">Kaufen</span>
          <select className="select" value={regel.kauf.ausloeser} onChange={(e: Event) => set((r) => void (r.kauf.ausloeser = (e.target as HTMLSelectElement).value as Regel['kauf']['ausloeser']))}>
            <option value="termin">zum Umschichtungstermin</option>
            <option value="neues_signal">nur bei neuem Signal</option>
            <option value="eintritt_top_n">bei Eintritt in die Auswahl</option>
            <option value="auffuellen">beim Wiederauffüllen mit freiem Guthaben</option>
          </select>
        </label>
      </Abschnitt>

      <Abschnitt titel="Verkauf">
        <label className="check">
          <input
            type="checkbox"
            checked={Boolean(regel.verkauf.herausfallen?.aktiv)}
            onChange={(e: Event) => set((r) => void (r.verkauf.herausfallen = { aktiv: (e.target as HTMLInputElement).checked, puffer: r.verkauf.herausfallen?.puffer ?? 3 }))}
          />
          <span>verkaufen, wenn die Aktie aus der Auswahl fällt</span>
        </label>
        {regel.verkauf.herausfallen?.aktiv ? (
          <Zahl label="Puffer (Plätze unter der Auswahl, die noch gehalten werden)" value={regel.verkauf.herausfallen.puffer} min={0} max={50} onChange={(v) => set((r) => void (r.verkauf.herausfallen!.puffer = v))} />
        ) : null}
        <Zahl
          label="höchstens halten (Sitzungen, leer = ohne)"
          value={regel.verkauf.max_haltedauer_sitzungen ?? NaN}
          min={1}
          max={2000}
          optional
          onChange={(v) => set((r) => void (r.verkauf.max_haltedauer_sitzungen = Number.isFinite(v) ? v : null))}
        />
        <h4 className="pilot-sub">Ausstiegsbedingung (verkaufen, sobald erfüllt)</h4>
        <BedingungenEditor katalog={katalog} rolle="ausstieg" wert={regel.verkauf.ausstieg ?? null} onChange={(a) => set((r) => void (r.verkauf.ausstieg = a))} />
        <label className="field">
          <span className="field-label">Wiedereinstieg nach einem Verkauf</span>
          <select
            className="select"
            value={regel.verkauf.wiedereinstieg?.art ?? 'neues_signal'}
            onChange={(e: Event) => set((r) => void (r.verkauf.wiedereinstieg = { art: (e.target as HTMLSelectElement).value as 'neues_signal', pause_sitzungen: r.verkauf.wiedereinstieg?.pause_sitzungen ?? 0 }))}
          >
            <option value="neues_signal">erst bei einem neuen Signal</option>
            <option value="pause">nach einer Pause</option>
            <option value="naechste_umschichtung">zur nächsten Umschichtung</option>
          </select>
        </label>
        {regel.verkauf.wiedereinstieg?.art === 'pause' ? (
          <Zahl label="Pause (Sitzungen)" value={regel.verkauf.wiedereinstieg.pause_sitzungen ?? 0} min={0} max={250} onChange={(v) => set((r) => void (r.verkauf.wiedereinstieg!.pause_sitzungen = v))} />
        ) : null}
      </Abschnitt>

      <Abschnitt titel="Gewinnmitnahme">
        <GewinnEditor g={regel.verkauf.gewinnmitnahme ?? null} onChange={(g) => set((r) => void (r.verkauf.gewinnmitnahme = g))} />
      </Abschnitt>

      <Abschnitt titel="Stop (Pflicht)">
        <StopEditor label="Initialstop" s={regel.stop.initial} onChange={(s) => set((r) => void (r.stop.initial = s!))} />
        <StopEditor label="Nachgezogener Stop (optional, steigt nur)" s={regel.stop.trailing ?? null} optional onChange={(s) => set((r) => void (r.stop.trailing = s))} />
      </Abschnitt>

      <Abschnitt titel="Zeitplan">
        <Segmented
          label="Entscheiden"
          value={regel.zeitplan.intervall}
          onChange={(intervall) => set((r) => void (r.zeitplan = intervall === 'taeglich' ? { intervall } : { intervall, wochentag: r.zeitplan.wochentag ?? 4 }))}
          options={[
            { value: 'taeglich', label: 'täglich' },
            { value: 'woechentlich', label: 'wöchentlich' },
          ]}
        />
        {regel.zeitplan.intervall === 'woechentlich' ? (
          <label className="field">
            <span className="field-label">mit den Daten vom</span>
            <select className="select" value={String(regel.zeitplan.wochentag ?? 4)} onChange={(e: Event) => set((r) => void (r.zeitplan.wochentag = Number((e.target as HTMLSelectElement).value)))}>
              {WOCHENTAG.map((w, i) => (
                <option key={w} value={String(i)}>
                  {w}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="pilot-row">
          <Zahl
            label="Mindesthaltedauer (Sitzungen)"
            value={regel.optionen?.mindesthaltedauer_sitzungen ?? 0}
            min={0}
            max={250}
            onChange={(v) => set((r) => void (r.optionen = { ...(r.optionen ?? {}), mindesthaltedauer_sitzungen: v }))}
          />
          <Zahl
            label="Mindestorderwert (€)"
            value={regel.optionen?.mindestorderwert_eur ?? 0}
            min={0}
            max={100000}
            onChange={(v) => set((r) => void (r.optionen = { ...(r.optionen ?? {}), mindestorderwert_eur: v }))}
          />
        </div>
      </Abschnitt>

      <section className="section" aria-labelledby="pruefung">
        <SectionTitle id="pruefung">Prüfung und Zusammenfassung</SectionTitle>
        {fehler.length || idKollision ? (
          <Notice tone="warn" title={`${fehler.length + (idKollision ? 1 : 0)} Punkte vor dem Übernehmen klären`}>
            <ul className="plain-list">
              {fehler.map((x: Fehler, i: number) => (
                <li key={i}>
                  <b>{pfadText(x.pfad)}</b>: {x.text}
                </li>
              ))}
              {idKollision ? <li>Kennung {regel.id} ist schon vergeben.</li> : null}
            </ul>
          </Notice>
        ) : (
          <Notice tone="info" compact>
            Regel vollständig – die App findet keine Fehler. Verbindlich prüft der tägliche Lauf.
          </Notice>
        )}
        <KeyValues items={regelZusammenfassung(regel, katalog)} />
        <RegelAktionen regel={regel} gueltig={!fehler.length && !idKollision} />
      </section>
    </div>
  );
}

const PFAD: [RegExp, string][] = [
  [/^kandidaten/, 'Kandidaten'],
  [/^filter/, 'Filter'],
  [/^sortierung/, 'Sortierung'],
  [/^auswahl/, 'Auswahl'],
  [/^kapital/, 'Kapital'],
  [/^kauf/, 'Kauf'],
  [/^verkauf\.gewinnmitnahme/, 'Gewinnmitnahme'],
  [/^verkauf\.ausstieg/, 'Ausstiegsbedingung'],
  [/^verkauf/, 'Verkauf'],
  [/^stop\.trailing/, 'Nachgezogener Stop'],
  [/^stop/, 'Stop'],
  [/^zeitplan/, 'Zeitplan'],
  [/^optionen/, 'Optionen'],
  [/^(name|id|version|beschreibung)/, 'Name'],
];

function pfadText(p: string): string {
  return PFAD.find(([re]) => re.test(p))?.[1] ?? (p || 'Regel');
}

function Abschnitt({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <fieldset className="pilot-fieldset">
      <legend>{titel}</legend>
      {children}
    </fieldset>
  );
}

function Zahl({ label, value, min, max, step, optional = false, onChange }: { label: string; value: number; min?: number; max?: number; step?: number; optional?: boolean; onChange: (v: number) => void }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input
        className="input"
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step ?? 'any'}
        value={Number.isFinite(value) ? String(value) : ''}
        onInput={(e: Event) => {
          const text = (e.target as HTMLInputElement).value;
          onChange(text === '' && optional ? NaN : num(text));
        }}
      />
    </label>
  );
}

function Vorlagenwahl({ stand, onPick }: { stand: PilotStand; onPick: (r: Regel) => void }) {
  const vorlagen = Object.entries(stand.vorlagen ?? {});
  const eigene = Object.entries(stand.regeln);
  return (
    <label className="field">
      <span className="field-label">Ausgangspunkt (ersetzt den Entwurf)</span>
      <select
        className="select"
        value=""
        onChange={(e: Event) => {
          const key = (e.target as HTMLSelectElement).value;
          if (!key) return;
          const [art, id] = key.split(':', 2);
          const basis = art === 'v' ? stand.vorlagen?.[id] : stand.regeln[id];
          if (basis) onPick(ableiten(basis, 'kopie'));
        }}
      >
        <option value="">Vorlage oder vorhandene Regel wählen …</option>
        <optgroup label="Vorlagen">
          {vorlagen.map(([k, r]) => (
            <option key={k} value={`v:${k}`}>
              {r.name.replace(/^Vorlage: /, '')}
            </option>
          ))}
        </optgroup>
        <optgroup label="Regeln im Robo (als Kopie)">
          {eigene.map(([k, r]) => (
            <option key={k} value={`r:${k}`}>
              {r.name} ({k})
            </option>
          ))}
        </optgroup>
      </select>
    </label>
  );
}

/* ------------------------------------------------------------------ Kandidatenquellen */

function GewichteChips({ value, onChange }: { value: number[]; onChange: (v: number[]) => void }) {
  return (
    <div className="pilot-chips" role="group" aria-label="Gewichtungen Gleichmäßigkeit/Rendite">
      {GEWICHTE.map((w) => {
        const on = value.includes(w);
        return (
          <button key={w} type="button" className={`chip${on ? ' is-active' : ''}`} aria-pressed={on} onClick={() => onChange(on ? value.filter((x) => x !== w) : [...value, w].sort((a, b) => a - b))}>
            {w}/{100 - w}
          </button>
        );
      })}
      <button type="button" className="chip" onClick={() => onChange(value.length === GEWICHTE.length ? [0] : [...GEWICHTE])}>
        {value.length === GEWICHTE.length ? 'nur 0/100' : 'alle'}
      </button>
    </div>
  );
}

function Zeitraum({ von, bis, onChange }: { von: number; bis: number; onChange: (von: number, bis: number) => void }) {
  return (
    <div className="pilot-row">
      <Zahl label="Zeitraum von (Tage)" value={von} min={1} max={90} onChange={(v) => onChange(v, bis)} />
      <Zahl label="bis (Tage)" value={bis} min={1} max={90} onChange={(v) => onChange(von, v)} />
    </div>
  );
}

function QuelleEditor({ q, onChange, onRemove }: { q: Quelle; onChange: (q: Quelle) => void; onRemove?: () => void }) {
  const upd = (patch: Partial<Quelle>) => onChange({ ...q, ...patch });
  const titel: Record<Quelle['art'], string> = { rangliste: 'Rangliste (Lineal)', haeufigkeit: 'Häufigkeit in den Top-Listen', universum: 'Alle Aktien', isins: 'Eigene Liste' };
  return (
    <div className="pilot-source">
      <div className="pilot-source-head">
        <b>{titel[q.art]}</b>
        {onRemove ? (
          <button type="button" className="btn btn-quiet" onClick={onRemove}>
            Entfernen
          </button>
        ) : null}
      </div>
      {q.art === 'rangliste' || q.art === 'haeufigkeit' ? (
        <>
          <Segmented label="Gruppe" value={q.gruppe ?? 'A'} onChange={(gruppe) => upd({ gruppe })} options={[{ value: 'A', label: 'A (alle)' }, { value: 'B', label: 'B (Umsatz)' }]} />
          <Segmented label="Vergleichsfeld" value={q.politik ?? 'native'} onChange={(politik) => upd({ politik })} options={[{ value: 'native', label: 'eigenes' }, { value: 'common_trend', label: 'gemeinsamer Trend' }]} />
          <GewichteChips value={q.gewichte ?? [0]} onChange={(gewichte) => upd({ gewichte })} />
          <Zeitraum von={q.fenster?.von ?? 1} bis={q.fenster?.bis ?? 30} onChange={(von, bis) => upd({ fenster: { von, bis } })} />
        </>
      ) : null}
      {q.art === 'rangliste' ? (
        <>
          <Zahl label="Plätze 1 bis" value={q.platz_bis ?? 1} min={1} max={100} onChange={(platz_bis) => upd({ platz_bis })} />
          <Segmented
            label="Wann"
            value={q.variante ?? 'heute'}
            onChange={(variante) => upd(variante === 'stichtage' ? { variante, stichtage: q.stichtage ?? 5 } : { variante, stichtage: undefined })}
            options={[
              { value: 'heute', label: 'heutige Rangliste' },
              { value: 'stichtage', label: 'vergangene Stichtage' },
            ]}
          />
          {q.variante === 'stichtage' ? <Zahl label="letzte Stichtage" value={q.stichtage ?? 5} min={1} max={60} onChange={(stichtage) => upd({ stichtage })} /> : null}
        </>
      ) : null}
      {q.art === 'haeufigkeit' ? (
        <div className="pilot-row">
          <label className="field">
            <span className="field-label">Top</span>
            <select className="select" value={String(q.k ?? 10)} onChange={(e: Event) => upd({ k: Number((e.target as HTMLSelectElement).value) })}>
              <option value="1">Platz 1</option>
              <option value="3">Top 3</option>
              <option value="10">Top 10</option>
            </select>
          </label>
          <Zahl label="mindestens Nennungen" value={q.mindestens ?? 1} min={1} onChange={(mindestens) => upd({ mindestens })} />
        </div>
      ) : null}
      {q.art === 'isins' ? <IsinListe q={q} onChange={onChange} /> : null}
    </div>
  );
}

function IsinListe({ q, onChange }: { q: Quelle; onChange: (q: Quelle) => void }) {
  const { watchlist } = useApp();
  return (
    <>
      <label className="field">
        <span className="field-label">ISINs (durch Leerzeichen oder Komma getrennt)</span>
        <textarea
          className="input"
          rows={3}
          value={(q.isins ?? []).join(' ')}
          onInput={(e: Event) =>
            onChange({
              ...q,
              isins: (e.target as HTMLTextAreaElement).value
                .toUpperCase()
                .split(/[\s,;]+/)
                .filter(Boolean),
            })
          }
        />
      </label>
      <button type="button" className="btn" disabled={!watchlist.length} onClick={() => onChange({ ...q, isins: [...watchlist], bezeichnung: 'Merkliste' })}>
        Merkliste übernehmen ({watchlist.length})
      </button>
    </>
  );
}

function QuelleNeu({ onAdd }: { onAdd: (q: Quelle) => void }) {
  return (
    <label className="field">
      <span className="field-label">Quelle hinzufügen</span>
      <select
        className="select"
        value=""
        onChange={(e: Event) => {
          const art = (e.target as HTMLSelectElement).value;
          if (art === 'rangliste') onAdd({ art, gruppe: 'A', politik: 'native', gewichte: [0], fenster: { von: 1, bis: 30 }, platz_bis: 1, variante: 'heute' });
          if (art === 'haeufigkeit') onAdd({ art, k: 10, fenster: { von: 1, bis: 30 }, gewichte: [...GEWICHTE], gruppe: 'A', politik: 'native', mindestens: 3 });
          if (art === 'universum') onAdd({ art });
          if (art === 'isins') onAdd({ art, isins: [], bezeichnung: 'eigene Auswahl' });
        }}
      >
        <option value="">wählen …</option>
        <option value="rangliste">Rangliste (Platz 1 … n, je Zeitraum und Gewichtung)</option>
        <option value="haeufigkeit">Häufigkeit in den Top-Listen</option>
        <option value="universum">alle Aktien</option>
        <option value="isins">eigene Liste / Merkliste</option>
      </select>
    </label>
  );
}

/* ------------------------------------------------------------------ Bedingungen */

function kennzahlenFuer(katalog: Katalog, rolle: Rolle): Map<string, KatalogKennzahl[]> {
  const groups = new Map<string, KatalogKennzahl[]>();
  for (const k of katalog.kennzahlen) {
    if (k.rueckblickend || !k.rollen.includes(rolle)) continue;
    const list = groups.get(k.gruppe) ?? [];
    list.push(k);
    groups.set(k.gruppe, list);
  }
  return groups;
}

function KennzahlWahl({ katalog, rolle, value, onChange, label }: { katalog: Katalog; rolle: Rolle; value: string; onChange: (k: KatalogKennzahl) => void; label: string }) {
  const groups = useMemo(() => kennzahlenFuer(katalog, rolle), [katalog, rolle]);
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <select
        className="select"
        value={value}
        onChange={(e: Event) => {
          const k = katalog.kennzahlen.find((x) => x.id === (e.target as HTMLSelectElement).value);
          if (k) onChange(k);
        }}
      >
        {[...groups.entries()].map(([g, list]) => (
          <optgroup key={g} label={g}>
            {list.map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
                {k.backtest !== 'ja' ? ' (nur vorwärts)' : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

const PARAM_LABEL: Record<string, string> = {
  fenster: 'Zeitraum',
  sitzungen: 'Sitzungen',
  gewicht: 'Gewichtung',
  gewichte: 'Gewichtungen',
  gruppe: 'Gruppe',
  politik: 'Vergleichsfeld',
  k: 'Top',
  faktor: 'Faktor',
  schwelle: 'Schwelle',
  art: 'Art',
};

function ParamEditor({ p, value, onChange }: { p: KatalogParam; value: unknown; onChange: (v: unknown) => void }) {
  const label = PARAM_LABEL[p.name] ?? p.name;
  if (p.art === 'auswahl') {
    return (
      <label className="field">
        <span className="field-label">{label}</span>
        <select className="select" value={String(value)} onChange={(e: Event) => onChange((p.werte ?? []).find((w) => String(w) === (e.target as HTMLSelectElement).value))}>
          {(p.werte ?? []).map((w) => (
            <option key={String(w)} value={String(w)}>
              {String(w)}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (p.art === 'gewichte') return <GewichteChips value={(value as number[]) ?? [0]} onChange={onChange} />;
  if (p.art === 'bereich') {
    const b = (value as { von: number; bis: number }) ?? { von: p.minimum ?? 1, bis: p.maximum ?? 30 };
    return <Zeitraum von={b.von} bis={b.bis} onChange={(von, bis) => onChange({ von, bis })} />;
  }
  return <Zahl label={`${label} (${p.erklaerung})`} value={Number(value)} min={p.minimum} max={p.maximum} step={p.art === 'ganzzahl' ? 1 : undefined} onChange={onChange} />;
}

function RefEditor({ katalog, rolle, r, onChange, label }: { katalog: Katalog; rolle: Rolle; r: KennzahlRef; onChange: (r: KennzahlRef) => void; label: string }) {
  const k = katalog.kennzahlen.find((x) => x.id === r.id);
  return (
    <>
      <KennzahlWahl katalog={katalog} rolle={rolle} value={r.id} label={label} onChange={(nk) => onChange(standardRef(nk))} />
      {k?.erklaerung ? <p className="section-note">{k.erklaerung}</p> : null}
      {k?.parameter.map((p) => (
        <ParamEditor key={p.name} p={p} value={r.parameter?.[p.name] ?? p.standard} onChange={(v) => onChange({ ...r, parameter: { ...r.parameter, [p.name]: v } })} />
      ))}
    </>
  );
}

function BedingungEditor({ katalog, rolle, z, onChange, onRemove }: { katalog: Katalog; rolle: Rolle; z: Zeile; onChange: (z: Zeile) => void; onRemove: () => void }) {
  const b = z.b;
  const k = katalog.kennzahlen.find((x) => x.id === b.kennzahl.id);
  const setB = (nb: Bedingung) => onChange({ ...z, b: nb });
  const vergleichbar = katalog.kennzahlen.filter((o) => k && o.vergleichsklasse && o.vergleichsklasse === k.vergleichsklasse && o.rollen.includes(rolle) && !o.rueckblickend);
  const mitVergleich = Boolean(b.vergleich);
  const op = b.op;
  return (
    <div className="pilot-condition">
      <RefEditor
        katalog={katalog}
        rolle={rolle}
        r={b.kennzahl}
        label="Kennzahl"
        onChange={(ref) => {
          const nk = katalog.kennzahlen.find((x) => x.id === ref.id);
          const nop = nk && nk.operatoren.includes(op) ? op : (nk?.operatoren[0] ?? '>');
          setB({ kennzahl: ref, op: nop, ...(nop === 'ist_wahr' || nop === 'ist_falsch' ? {} : nop === 'zwischen' ? { von: 0, bis: 1 } : { wert: 0 }) });
        }}
      />
      <label className="field">
        <span className="field-label">Bedingung</span>
        <select
          className="select"
          value={op}
          onChange={(e: Event) => {
            const nop = (e.target as HTMLSelectElement).value;
            const base = { kennzahl: b.kennzahl, op: nop };
            if (nop === 'ist_wahr' || nop === 'ist_falsch') setB(base);
            else if (nop === 'zwischen') setB({ ...base, von: b.von ?? 0, bis: b.bis ?? 1 });
            else if (nop === 'in' || nop === 'nicht_in') setB({ ...base, werte: b.werte ?? [] });
            else if (mitVergleich && !['neu_eingetreten', 'verlassen'].includes(nop)) setB({ ...base, vergleich: b.vergleich });
            else setB({ ...base, wert: typeof b.wert === 'number' ? b.wert : 0 });
          }}
        >
          {(k?.operatoren ?? []).map((o) => (
            <option key={o} value={o}>
              {OP_LABEL[o] ?? o}
            </option>
          ))}
        </select>
      </label>
      {op === 'zwischen' ? (
        <div className="pilot-row">
          <Zahl label={`von${k?.einheit ? ` (${k.einheit})` : ''}`} value={Number(b.von)} onChange={(von) => setB({ ...b, von })} />
          <Zahl label="bis" value={Number(b.bis)} onChange={(bis) => setB({ ...b, bis })} />
        </div>
      ) : op === 'in' || op === 'nicht_in' ? (
        <label className="field">
          <span className="field-label">Werte (durch Komma getrennt)</span>
          <input className="input" type="text" value={(b.werte ?? []).join(', ')} onInput={(e: Event) => setB({ ...b, werte: (e.target as HTMLInputElement).value.split(',').map((x) => x.trim()).filter(Boolean) })} />
        </label>
      ) : op === 'ist_wahr' || op === 'ist_falsch' ? null : (
        <>
          {vergleichbar.length > 1 && !['neu_eingetreten', 'verlassen'].includes(op) ? (
            <Segmented
              label="verglichen mit"
              value={mitVergleich ? 'kennzahl' : 'wert'}
              onChange={(m) => {
                if (m === 'wert') setB({ kennzahl: b.kennzahl, op, wert: 0 });
                else setB({ kennzahl: b.kennzahl, op, vergleich: standardRef(vergleichbar.find((o) => o.id !== b.kennzahl.id) ?? vergleichbar[0]) });
              }}
              options={[
                { value: 'wert', label: 'einer Zahl' },
                { value: 'kennzahl', label: 'einer Kennzahl' },
              ]}
            />
          ) : null}
          {mitVergleich && b.vergleich ? (
            <RefEditor katalog={{ ...katalog, kennzahlen: vergleichbar }} rolle={rolle} r={b.vergleich} label="Vergleichskennzahl" onChange={(ref) => setB({ ...b, vergleich: ref })} />
          ) : (
            <Zahl label={`Wert${k?.einheit ? ` (${k.einheit})` : ''}`} value={Number(b.wert)} onChange={(wert) => setB({ ...b, wert })} />
          )}
        </>
      )}
      <div className="pilot-condition-foot">
        <label className="check">
          <input type="checkbox" checked={z.nicht} onChange={(e: Event) => onChange({ ...z, nicht: (e.target as HTMLInputElement).checked })} />
          <span>umkehren (NICHT)</span>
        </label>
        <button type="button" className="btn btn-quiet" onClick={onRemove}>
          Bedingung entfernen
        </button>
      </div>
      <p className="section-note">{k ? `${k.backtest === 'ja' ? 'historisch testbar' : 'nur vorwärts prüfbar (keine Zeitreihe)'}${k.hinweis ? ` · ${k.hinweis}` : ''}` : 'unbekannte Kennzahl'}</p>
    </div>
  );
}

function BedingungenEditor({ katalog, rolle, wert, onChange }: { katalog: Katalog; rolle: Rolle; wert: Ausdruck | null | undefined; onChange: (a: Ausdruck | null) => void }) {
  const g = alsGruppe(wert);
  if (!g) {
    return (
      <>
        <p className="section-note">Verschachtelte Bedingung (bleibt unverändert): {ausdruckText(wert, katalog)}</p>
        <button type="button" className="btn" onClick={() => onChange(null)}>
          Durch eine einfache Liste ersetzen
        </button>
      </>
    );
  }
  const setG = (ng: Gruppe) => onChange(ausGruppe(ng));
  const first = katalog.kennzahlen.find((k) => k.rollen.includes(rolle) && !k.rueckblickend);
  return (
    <>
      {g.zeilen.length > 1 ? (
        <Segmented
          label="Verknüpfung"
          value={g.op}
          onChange={(op) => setG({ ...g, op })}
          options={[
            { value: 'und', label: 'alle (UND)' },
            { value: 'oder', label: 'mindestens eine (ODER)' },
          ]}
        />
      ) : null}
      {g.zeilen.map((z, i) => (
        <BedingungEditor
          key={i}
          katalog={katalog}
          rolle={rolle}
          z={z}
          onChange={(nz) => setG({ ...g, zeilen: g.zeilen.map((x, j) => (j === i ? nz : x)) })}
          onRemove={() => setG({ ...g, zeilen: g.zeilen.filter((_, j) => j !== i) })}
        />
      ))}
      {!g.zeilen.length ? <p className="section-note">Keine Bedingung.</p> : null}
      {first && g.zeilen.length < 40 ? (
        <button type="button" className="btn" onClick={() => setG({ ...g, zeilen: [...g.zeilen, { nicht: false, b: { kennzahl: standardRef(first), op: first.operatoren[0], wert: 0 } }] })}>
          Bedingung hinzufügen
        </button>
      ) : null}
    </>
  );
}

/* ------------------------------------------------------------------ Sortierung, Gewinnmitnahme, Stop */

function SortierungEditor({ katalog, regel, set }: { katalog: Katalog; regel: Regel; set: (f: (r: Regel) => void) => void }) {
  const s = regel.sortierung;
  const score = 'score' in s;
  const items = score ? s.score : s.schluessel;
  const first = katalog.kennzahlen.find((k) => k.rollen.includes('sortierung') && !k.rueckblickend)!;
  return (
    <>
      <Segmented
        label="Art"
        value={score ? 'score' : 'schluessel'}
        onChange={(m) =>
          set((r) => {
            const refs = ('score' in r.sortierung ? r.sortierung.score : r.sortierung.schluessel).map((x) => ({ kennzahl: x.kennzahl, richtung: x.richtung }));
            r.sortierung = m === 'score' ? { score: refs.map((x) => ({ ...x, gewicht: 1 })), normierung: 'perzentil' } : { schluessel: refs };
          })
        }
        options={[
          { value: 'schluessel', label: 'Reihenfolge' },
          { value: 'score', label: 'Score (gewichtet)' },
        ]}
      />
      {items.map((it, i) => (
        <div className="pilot-condition" key={i}>
          <RefEditor
            katalog={katalog}
            rolle="sortierung"
            r={it.kennzahl}
            label={score ? `Bestandteil ${i + 1}` : i === 0 ? 'zuerst nach' : 'dann nach'}
            onChange={(ref) => set((r) => void (('score' in r.sortierung ? r.sortierung.score : r.sortierung.schluessel)[i].kennzahl = ref))}
          />
          <Segmented
            label="Richtung"
            value={it.richtung}
            onChange={(richtung) => set((r) => void (('score' in r.sortierung ? r.sortierung.score : r.sortierung.schluessel)[i].richtung = richtung))}
            options={[
              { value: 'ab', label: 'hoch zuerst' },
              { value: 'auf', label: 'niedrig zuerst' },
            ]}
          />
          {score ? (
            <Zahl label="Gewicht" value={(it as unknown as { gewicht: number }).gewicht} min={0.01} max={100} onChange={(v) => set((r) => void ((r.sortierung as { score: { gewicht: number }[] }).score[i].gewicht = v))} />
          ) : null}
          {items.length > 1 ? (
            <button type="button" className="btn btn-quiet" onClick={() => set((r) => void ('score' in r.sortierung ? r.sortierung.score : r.sortierung.schluessel).splice(i, 1))}>
              Entfernen
            </button>
          ) : null}
        </div>
      ))}
      {items.length < 6 ? (
        <button
          type="button"
          className="btn"
          onClick={() =>
            set((r) => {
              const ref = standardRef(first);
              if ('score' in r.sortierung) r.sortierung.score.push({ kennzahl: ref, gewicht: 1, richtung: 'ab' });
              else r.sortierung.schluessel.push({ kennzahl: ref, richtung: 'ab' });
            })
          }
        >
          {score ? 'Bestandteil hinzufügen' : 'Weitere Sortierung'}
        </button>
      ) : null}
      {score ? <p className="section-note">Jede Kennzahl wird innerhalb der Kandidaten in Perzentile (0–100) umgerechnet und gewichtet addiert – keine Addition von Prozenten und Rängen.</p> : null}
    </>
  );
}

const SCHWELLEN = [30, 50, 100];

function GewinnEditor({ g, onChange }: { g: Gewinnmitnahme | null; onChange: (g: Gewinnmitnahme | null) => void }) {
  const art = g?.art ?? 'keine';
  return (
    <>
      <Segmented
        label="Gewinnmitnahme"
        value={art}
        onChange={(a) => {
          if (a === 'keine') onChange(null);
          else if (a === 'ganz') onChange({ art: 'ganz', schwelle_pct: 30, basis: 'nach_kosten', umfang: { art: 'alles' } });
          else onChange({ art: 'leiter', basis: 'nach_kosten', bezug: 'urspruenglich', stufen: [{ schwelle_pct: 30, anteil_pct: 25 }, { schwelle_pct: 50, anteil_pct: 25 }, { schwelle_pct: 100, anteil_pct: 50 }] });
        }}
        options={[
          { value: 'keine', label: 'keine' },
          { value: 'ganz', label: 'ab einer Schwelle' },
          { value: 'leiter', label: 'Leiter' },
        ]}
      />
      {g ? (
        <Segmented
          label="Gewinn gemessen"
          value={g.basis}
          onChange={(basis) => onChange({ ...g, basis })}
          options={[
            { value: 'nach_kosten', label: 'nach Kosten' },
            { value: 'kurs', label: 'nur Kurs' },
          ]}
        />
      ) : null}
      {g?.art === 'ganz' ? (
        <>
          <div className="pilot-chips" role="group" aria-label="Schwelle">
            {SCHWELLEN.map((s) => (
              <button key={s} type="button" className={`chip${g.schwelle_pct === s ? ' is-active' : ''}`} aria-pressed={g.schwelle_pct === s} onClick={() => onChange({ ...g, schwelle_pct: s })}>
                +{s} %
              </button>
            ))}
          </div>
          <Zahl label="eigene Schwelle (%)" value={g.schwelle_pct ?? 30} min={0.1} max={10000} onChange={(schwelle_pct) => onChange({ ...g, schwelle_pct })} />
          <Segmented
            label="verkaufen"
            value={g.umfang?.art ?? 'alles'}
            onChange={(u) => onChange({ ...g, umfang: u === 'alles' ? { art: 'alles' } : u === 'anteil' ? { art: 'anteil', pct: 50 } : { art: 'stueck', stueck: 1 } })}
            options={[
              { value: 'alles', label: 'alles' },
              { value: 'anteil', label: 'Anteil' },
              { value: 'stueck', label: 'Stück' },
            ]}
          />
          {g.umfang?.art === 'anteil' ? <Zahl label="Anteil der Position (%)" value={g.umfang.pct} min={1} max={100} onChange={(pct) => onChange({ ...g, umfang: { art: 'anteil', pct } })} /> : null}
          {g.umfang?.art === 'stueck' ? <Zahl label="Stück" value={g.umfang.stueck} min={1} step={1} onChange={(stueck) => onChange({ ...g, umfang: { art: 'stueck', stueck } })} /> : null}
        </>
      ) : null}
      {g?.art === 'leiter' ? (
        <>
          <Segmented
            label="Anteile bezogen auf"
            value={g.bezug ?? 'urspruenglich'}
            onChange={(bezug) => onChange({ ...g, bezug })}
            options={[
              { value: 'urspruenglich', label: 'ursprüngliche Menge' },
              { value: 'verbleibend', label: 'verbleibende Menge' },
            ]}
          />
          {(g.stufen ?? []).map((st, i) => (
            <div className="pilot-row" key={i}>
              <Zahl label={`Stufe ${i + 1}: ab Gewinn (%)`} value={st.schwelle_pct} min={0.1} max={10000} onChange={(v) => onChange({ ...g, stufen: (g.stufen ?? []).map((x, j) => (j === i ? { ...x, schwelle_pct: v } : x)) })} />
              <Zahl label="verkaufen (%)" value={st.anteil_pct} min={1} max={100} onChange={(v) => onChange({ ...g, stufen: (g.stufen ?? []).map((x, j) => (j === i ? { ...x, anteil_pct: v } : x)) })} />
            </div>
          ))}
          <div className="toolbar">
            {(g.stufen ?? []).length < 6 ? (
              <button type="button" className="btn" onClick={() => onChange({ ...g, stufen: [...(g.stufen ?? []), { schwelle_pct: ((g.stufen ?? []).at(-1)?.schwelle_pct ?? 0) + 50, anteil_pct: 10 }] })}>
                Stufe hinzufügen
              </button>
            ) : null}
            {(g.stufen ?? []).length > 1 ? (
              <button type="button" className="btn btn-quiet" onClick={() => onChange({ ...g, stufen: (g.stufen ?? []).slice(0, -1) })}>
                Letzte Stufe entfernen
              </button>
            ) : null}
          </div>
          <p className="section-note">Jede Stufe wird genau einmal ausgeführt; Bruchteile werden abgerundet, unter einem ganzen Stück wird die Stufe übersprungen und im Journal vermerkt.</p>
        </>
      ) : null}
    </>
  );
}

type StopArt = Regel['stop']['initial'];

function StopEditor({ label, s, optional = false, onChange }: { label: string; s: StopArt | null; optional?: boolean; onChange: (s: StopArt | null) => void }) {
  const art = s?.art ?? 'aus';
  return (
    <>
      <Segmented
        label={label}
        value={art}
        onChange={(a) => onChange(a === 'aus' ? null : a === 'atr' ? { art: 'atr', faktor: 2, sitzungen: 14 } : { art: 'prozent', wert: 10 })}
        options={[...(optional ? [{ value: 'aus' as const, label: 'aus' }] : []), { value: 'atr' as const, label: 'ATR-Abstand' }, { value: 'prozent' as const, label: 'Prozent' }]}
      />
      {s?.art === 'atr' ? (
        <div className="pilot-row">
          <Zahl label="Faktor × ATR" value={s.faktor} min={0.5} max={10} onChange={(faktor) => onChange({ ...s, faktor })} />
          <Zahl label="ATR-Sitzungen" value={s.sitzungen ?? 14} min={5} max={50} step={1} onChange={(sitzungen) => onChange({ ...s, sitzungen })} />
        </div>
      ) : null}
      {s?.art === 'prozent' ? <Zahl label="Prozent unter dem Einstieg" value={s.wert} min={1} max={50} onChange={(wert) => onChange({ art: 'prozent', wert })} /> : null}
    </>
  );
}

/* ------------------------------------------------------------------ Aktionen */

function RegelAktionen({ regel, gueltig }: { regel: Regel; gueltig: boolean }) {
  const [hinweis, setHinweis] = useState<string | null>(null);
  const json = JSON.stringify(regel, null, 1);
  const datei = () => {
    const blob = new Blob([json], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${regel.id}-v${regel.version}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    setHinweis('Regel als Datei gesichert.');
  };
  const kopieren = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setHinweis('Regel in die Zwischenablage kopiert.');
    } catch {
      setHinweis('Kopieren ist hier nicht möglich – bitte „Als Datei sichern“ nutzen.');
    }
  };
  return (
    <>
      <div className="toolbar">
        <button type="button" className="btn btn-primary" disabled={!gueltig} onClick={datei}>
          Als Datei sichern
        </button>
        <button type="button" className="btn" disabled={!gueltig} onClick={() => void kopieren()}>
          Kopieren
        </button>
      </div>
      {hinweis ? <p className="section-note" role="status">{hinweis}</p> : null}
      <p className="section-note">
        Übernahme in den Robo: Die Regel wird im täglichen Lauf noch einmal vollständig geprüft und startet dann in einem eigenen Forschungsdepot mit neuer Test-Kennung. Eine Regel
        ändert nie rückwirkend einen laufenden Test.
      </p>
    </>
  );
}
