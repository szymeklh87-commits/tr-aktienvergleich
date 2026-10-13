"""Stabile Status- und Hinweiscodes mit deutschen Texten.

Hauptstatus (genau einer je Instrument und Fenster, addierbar zur Abdeckungsbilanz)
werden in Prioritätsreihenfolge vergeben: der erste zutreffende Grund gewinnt.
Hinweise (Warnungen) sind Bitmasken; ein Instrument kann mehrere besitzen. Sie
werden getrennt gezählt und verdoppeln keine Aktienzahl.

Die Tabellen werden in jedes Snapshot-Manifest geschrieben; die App liest ihre
Beschriftungen von dort und hat keine eigene, abweichende Kopie.
"""

from __future__ import annotations

from enum import IntEnum

from ..config import Ratio


class Status(IntEnum):
    ISIN_UNGUELTIG = 1
    KEIN_AKTIENINSTRUMENT = 2
    IDENTITAET_OFFEN = 3
    IDENTITAET_UNKLAR = 4
    KALENDER_FEHLT = 5
    KEINE_KURSDATEN = 6
    MARKT_AM_STICHTAG_GESCHLOSSEN = 7
    KURS_AM_STICHTAG_FEHLT = 8
    HISTORIE_ZU_KURZ = 9
    KEINE_STARTSITZUNG = 10
    STARTKURS_FEHLT = 11
    SITZUNGSABDECKUNG_ZU_GERING = 12
    KURSSPRUNG_PRUEFEN = 13
    VOLUMEN_UNZUREICHEND = 14
    ZU_WENIG_TAGESDATEN_TREND = 15
    NICHT_STEIGEND = 16
    TREND_NICHT_DEFINIERT = 17
    TREND_BEWERTBAR = 18


# Status, mit denen eine Kursrendite veröffentlicht werden darf (Menge V).
RETURN_PUBLISHABLE = frozenset(
    {
        Status.ZU_WENIG_TAGESDATEN_TREND,
        Status.NICHT_STEIGEND,
        Status.TREND_NICHT_DEFINIERT,
        Status.TREND_BEWERTBAR,
    }
)
# Status der Aufwärts-Gleichmäßigkeitsmenge U (Teilmenge von V).
TREND_ELIGIBLE = frozenset({Status.TREND_BEWERTBAR})

STATUS_INFO: dict[int, dict[str, str]] = {
    Status.ISIN_UNGUELTIG: {
        "key": "isin_ungueltig",
        "gruppe": "identitaet",
        "kurz": "ISIN ungültig",
        "text": "Die ISIN aus der TR-Liste hat ein ungültiges Format oder eine falsche Prüfziffer.",
    },
    Status.KEIN_AKTIENINSTRUMENT: {
        "key": "kein_aktieninstrument",
        "gruppe": "identitaet",
        "kurz": "Kein Aktieninstrument",
        "text": "Laut Identitätsquelle ein Fonds, ETP, Bezugsrecht oder Optionsschein; nicht im Aktienranking.",
    },
    Status.IDENTITAET_OFFEN: {
        "key": "identitaet_offen",
        "gruppe": "identitaet",
        "kurz": "Identität noch nicht geprüft",
        "text": "Die Zuordnung ISIN → Börsennotierung wurde noch nicht durchgeführt.",
    },
    Status.IDENTITAET_UNKLAR: {
        "key": "identitaet_unklar",
        "gruppe": "identitaet",
        "kurz": "Identität unklar",
        "text": "Keine eindeutige Börsennotierung zur ISIN gefunden oder widersprüchliche Angaben.",
    },
    Status.KALENDER_FEHLT: {
        "key": "kalender_fehlt",
        "gruppe": "daten",
        "kurz": "Börsenkalender fehlt",
        "text": "Für die Referenzbörse ist kein geprüfter Handelskalender verfügbar.",
    },
    Status.KEINE_KURSDATEN: {
        "key": "keine_kursdaten",
        "gruppe": "daten",
        "kurz": "Daten fehlen",
        "text": "Der Kursanbieter lieferte für diese Notierung keine verwertbare Historie.",
    },
    Status.MARKT_AM_STICHTAG_GESCHLOSSEN: {
        "key": "markt_geschlossen",
        "gruppe": "stichtag",
        "kurz": "Markt am Stichtag geschlossen",
        "text": "Die Referenzbörse hatte am Kursstichtag keine reguläre Sitzung.",
    },
    Status.KURS_AM_STICHTAG_FEHLT: {
        "key": "kurs_stichtag_fehlt",
        "gruppe": "stichtag",
        "kurz": "Schlusskurs am Stichtag fehlt",
        "text": "Die Börse war geöffnet, aber für den Stichtag liegt kein geprüfter Schlusskurs vor.",
    },
    Status.HISTORIE_ZU_KURZ: {
        "key": "historie_zu_kurz",
        "gruppe": "historie",
        "kurz": "Zu kurze Historie",
        "text": "Die vorhandene Kurshistorie reicht nicht bis zum Fensterbeginn zurück.",
    },
    Status.KEINE_STARTSITZUNG: {
        "key": "keine_startsitzung",
        "gruppe": "historie",
        "kurz": "Keine Startsitzung",
        "text": "Innerhalb von sieben Kalendertagen vor dem Ziel-Startdatum gab es keine Börsensitzung.",
    },
    Status.STARTKURS_FEHLT: {
        "key": "startkurs_fehlt",
        "gruppe": "historie",
        "kurz": "Startkurs fehlt",
        "text": "An der maßgeblichen Startsitzung fehlt ein gültiger Schlusskurs; es wird nicht auf ältere Kurse ausgewichen.",
    },
    Status.SITZUNGSABDECKUNG_ZU_GERING: {
        "key": "abdeckung_zu_gering",
        "gruppe": "historie",
        "kurz": "Zu viele fehlende Sitzungen",
        "text": "Zwischen Start und Kursstichtag fehlt an mehr als 20 % der erwarteten Börsensitzungen ein gültiger Schlusskurs (ein einzelner fehlender Tag ist erlaubt). Fehlende Tage werden nicht aufgefüllt.",
    },
    Status.KURSSPRUNG_PRUEFEN: {
        "key": "kapitalmassnahme_pruefen",
        "gruppe": "pruefung",
        "kurz": "Kapitalmaßnahme/Datenfehler prüfen",
        "text": "Im Fenster liegt ein gemeldeter Split bzw. eine Zusammenlegung (ohne dokumentierte Freigabe), ein ungeklärter Kurssprung (Faktor > 3), ein möglicherweise unbereinigter Split oder am Fensterbeginn/-ende eine starke Kursbewegung ohne belegten Umsatz.",
    },
    Status.VOLUMEN_UNZUREICHEND: {
        "key": "volumen_unzureichend",
        "gruppe": "pruefung",
        "kurz": "Zu wenig belegtes Handelsvolumen",
        "text": "An mindestens einer Beobachtung fehlt das Handelsvolumen, an der Start- oder Endsitzung ist es nicht positiv, oder weniger als 80 % der Kurstage haben ein positives Volumen.",
    },
    Status.ZU_WENIG_TAGESDATEN_TREND: {
        "key": "zu_wenig_tagesdaten",
        "gruppe": "rendite",
        "kurz": "Für Gleichmäßigkeit zu wenig Tagesdaten",
        "text": "Kursrendite veröffentlicht; für die Aufwärts-Gleichmäßigkeit fehlen echte Tageskurse (mindestens 15).",
    },
    Status.NICHT_STEIGEND: {
        "key": "nicht_steigend",
        "gruppe": "rendite",
        "kurz": "Nicht steigend",
        "text": "Kursrendite veröffentlicht; Rendite oder Trendsteigung ist nicht positiv. Kein Datenfehler.",
    },
    Status.TREND_NICHT_DEFINIERT: {
        "key": "trend_nicht_definiert",
        "gruppe": "rendite",
        "kurz": "Gleichmäßigkeit nicht definiert",
        "text": "Kursrendite veröffentlicht; R² ist für eine konstante Reihe nicht definiert.",
    },
    Status.TREND_BEWERTBAR: {
        "key": "trend_bewertbar",
        "gruppe": "rendite",
        "kurz": "Gleichmäßig steigend bewertbar",
        "text": "Kursrendite und Aufwärts-Gleichmäßigkeit berechnet; in allen elf Gewichtungen vertreten.",
    },
}


class InstrumentWarning(IntEnum):
    """Bitpositionen für instrumentbezogene Hinweise."""

    TYP_UNKLAR = 0
    NAME_ABWEICHEND = 1
    OTC_NOTIERUNG = 2
    WAEHRUNGS_UNTEREINHEIT = 3
    ERSATZKALENDER = 4
    WENIGE_AKTIVE_HANDELSTAGE = 5
    GEPRUEFTER_KURSSPRUNG = 6
    VOLUMEN_OFT_UNBEKANNT = 7
    BARS_AN_NICHTHANDELSTAGEN = 8
    SPLIT_IN_HISTORIE = 9
    IDENTITAET_ALT = 10
    TR_NACHWEIS_ALT = 11
    ROHKURS_REKONSTRUIERT = 12
    NULLUMSATZ_AUSREISSER = 13
    SEHR_NIEDRIGER_UMSATZ = 14
    UMSATZ_NICHT_BESTIMMBAR = 15


INSTRUMENT_WARNING_INFO: dict[int, dict[str, str]] = {
    InstrumentWarning.TYP_UNKLAR: {"key": "typ_unklar", "text": "Instrumenttyp laut Quelle unklar"},
    InstrumentWarning.NAME_ABWEICHEND: {"key": "name_abweichend", "text": "Name weicht zwischen Quellen ab (z. B. Umbenennung)"},
    InstrumentWarning.OTC_NOTIERUNG: {"key": "otc", "text": "Referenznotierung ist ein OTC-Markt"},
    InstrumentWarning.WAEHRUNGS_UNTEREINHEIT: {"key": "untereinheit", "text": "Kurs in Untereinheit (z. B. GBp = Pence)"},
    InstrumentWarning.ERSATZKALENDER: {"key": "ersatzkalender", "text": "Börsenkalender einer Schwesterbörse mit gleichen Feiertagen"},
    InstrumentWarning.WENIGE_AKTIVE_HANDELSTAGE: {"key": "wenige_handelstage", "text": "Wenige aktive Handelstage (oft kein Umsatz)"},
    InstrumentWarning.GEPRUEFTER_KURSSPRUNG: {"key": "gepruefter_sprung", "text": "Geprüfter, freigegebener starker Kurssprung in der Historie"},
    InstrumentWarning.VOLUMEN_OFT_UNBEKANNT: {"key": "volumen_unbekannt", "text": "Handelsvolumen häufig nicht angegeben"},
    InstrumentWarning.BARS_AN_NICHTHANDELSTAGEN: {"key": "nichthandelstage", "text": "Anbieter lieferte Kurse an Nicht-Handelstagen; verworfen"},
    InstrumentWarning.SPLIT_IN_HISTORIE: {"key": "split", "text": "Aktiensplit/Zusammenlegung in der geladenen Historie (bereinigt)"},
    InstrumentWarning.IDENTITAET_ALT: {"key": "identitaet_alt", "text": "Identitätsprüfung ist älter als vorgesehen"},
    InstrumentWarning.TR_NACHWEIS_ALT: {"key": "tr_nachweis_alt", "text": "TR-Listennachweis ist älter als 14 Tage"},
    InstrumentWarning.ROHKURS_REKONSTRUIERT: {"key": "rohkurs_rekonstruiert", "text": "Unveränderter Schlusskurs aus Splitfaktoren rekonstruiert"},
    InstrumentWarning.NULLUMSATZ_AUSREISSER: {"key": "nullumsatz_ausreisser", "text": "Starke Kursbewegung an einem Tag ohne belegten Umsatz (betroffene Fenster bis zur Prüfung zurückgehalten)"},
    InstrumentWarning.SEHR_NIEDRIGER_UMSATZ: {"key": "sehr_niedriger_umsatz", "text": "Sehr niedriger Handelsumsatz: Ø unter 1 Mio. USD je Sitzung (letzte 20 Sitzungen)"},
    InstrumentWarning.UMSATZ_NICHT_BESTIMMBAR: {"key": "umsatz_nicht_bestimmbar", "text": "Ø Tagesumsatz nicht bestimmbar (Volumen, Kurse oder Wechselkurs fehlen); nicht in Ranking 2"},
}


class WindowWarning(IntEnum):
    """Bitpositionen für fensterbezogene Hinweise."""

    IMPULSTAG = 0
    SPLIT_IM_FENSTER = 1
    GEPRUEFTER_SPRUNG_IM_FENSTER = 2
    R2_NUMERISCH_INSTABIL = 3
    UEBERNAHMEMUSTER = 4
    BOERSENPLATZ_ABWEICHUNG = 5


WINDOW_WARNING_INFO: dict[int, dict[str, str]] = {
    WindowWarning.IMPULSTAG: {"key": "impulstag", "text": "Ein einzelner Handelstag erklärt mehr als die Hälfte der Kursbewegung"},
    WindowWarning.SPLIT_IM_FENSTER: {"key": "split_im_fenster", "text": "Split/Zusammenlegung im Fenster – nach dokumentierter Prüfung freigegeben, splitbereinigt gerechnet"},
    WindowWarning.GEPRUEFTER_SPRUNG_IM_FENSTER: {"key": "gepruefter_sprung", "text": "Geprüfter starker Kurssprung im Fenster"},
    WindowWarning.R2_NUMERISCH_INSTABIL: {"key": "r2_instabil", "text": "R² numerisch nicht stabil bestimmbar (nahezu konstanter Kurs); keine Aufwärtsbewertung"},
    WindowWarning.UEBERNAHMEMUSTER: {"key": "uebernahmemuster", "text": "Kurssprung von mindestens 15 % an einem Tag, danach kaum Bewegung – typisch für ein Übernahmeangebot"},
    WindowWarning.BOERSENPLATZ_ABWEICHUNG: {
        "key": "boersenplatz_abweichung",
        "text": "Auffällige Kursabweichung zwischen Börsenplätzen: Wertentwicklung oder Endkurs weichen am zweiten Börsenplatz um mehr als 10 % ab",
    },
}


def _pct(ratio) -> str:
    value = 100 * ratio.num / ratio.den
    text = f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} %"


def status_info(cfg=None) -> dict[int, dict[str, str]]:
    """Statustexte; mit ``cfg`` nennen die Schwellen genau die Werte der Methodenversion."""
    info = {k: dict(v) for k, v in STATUS_INFO.items()}
    if cfg is not None:
        rules = cfg.admission_rules()
        share = _pct(Ratio(rules.session_coverage.den - rules.session_coverage.num, rules.session_coverage.den))
        tolerated = rules.tolerated_missing_sessions
        allowance = "" if tolerated <= 0 else (" (ein einzelner fehlender Tag ist erlaubt)" if tolerated == 1 else f" ({tolerated} fehlende Tage sind immer erlaubt)")
        info[Status.SITZUNGSABDECKUNG_ZU_GERING]["text"] = (
            f"Zwischen Start und Kursstichtag fehlt an mehr als {share} der erwarteten Börsensitzungen ein gültiger Schlusskurs{allowance}. Fehlende Tage werden nicht aufgefüllt."
        )
        base = "der erwarteten Börsensitzungen" if rules.volume_basis == "sitzungen" else "der Kurstage"
        info[Status.VOLUMEN_UNZUREICHEND]["text"] = (
            f"An mindestens einer Beobachtung fehlt das Handelsvolumen, an der Start- oder Endsitzung ist es nicht positiv, oder weniger als {_pct(rules.volume_coverage)} {base} haben ein positives Volumen."
        )
    return info


def code_tables(cfg=None) -> dict:
    """Serialisierbare Tabellen für das Manifest (Statustexte passend zu den Schwellen in ``cfg``)."""
    from .turnover import TURNOVER_STATUS
    from .venues import INSTRUMENT_STATUS, PAIR_STATUS

    return {
        "turnover_status": {key: dict(value, key=key) for key, value in TURNOVER_STATUS.items()},
        "venue_status": {key: dict(value, key=key) for key, value in INSTRUMENT_STATUS.items()},
        "venue_pair_status": {key: dict(value, key=key) for key, value in PAIR_STATUS.items()},
        "status": {str(int(k)): v for k, v in status_info(cfg).items()},
        "return_publishable": sorted(int(s) for s in RETURN_PUBLISHABLE),
        "trend_eligible": sorted(int(s) for s in TREND_ELIGIBLE),
        "instrument_warnings": {str(int(k)): v for k, v in INSTRUMENT_WARNING_INFO.items()},
        "window_warnings": {str(int(k)): v for k, v in WINDOW_WARNING_INFO.items()},
    }
