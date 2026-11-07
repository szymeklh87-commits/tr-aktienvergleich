/* Mindestumsatz für alle Ranglisten (ab 1.23, Simons Vorgabe vom 07.11.2026, dauerhaft für alle künftigen Versionen):
 * Ranglisten, Spitzenreiter, Top-Listen, Häufigkeit, Bericht, Matrix, Musterdepots, Kaufkandidaten und der Spielgeld-Robo
 * berücksichtigen nur Aktien, deren Ø Tagesumsatz der letzten 20 Sitzungen nachweislich mindestens 10 Mio. USD beträgt
 * (bisher „Gruppe B“). Aktien darunter oder ohne verlässlich bestimmten Umsatz stehen in keiner regulären Rangliste; ihre
 * Plätze werden nicht freigehalten, die Ranglisten sind ohne sie gerechnet. Eine Auswahl „alle Aktien“ (bisher „Gruppe A“)
 * gibt es in der Oberfläche nicht mehr – die Rohdaten aller Aktien bleiben im Datenstand für spätere Nachprüfungen. */

import type { Group } from './types';

/** Die einzige Vergleichsmenge der Oberfläche (Datenfelder „…l“ bzw. „ul“, „v0l“, „winners_l“). */
export const GROUP: Group = 'b';

export const MIN_TURNOVER_TEXT = 'Mindestumsatz: 10 Mio. USD pro Handelstag (Durchschnitt)';
export const MIN_TURNOVER_SHORT = 'Ø Tagesumsatz ab 10 Mio. USD';
