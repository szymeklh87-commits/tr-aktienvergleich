"""Normalisierung und Ähnlichkeit von Unternehmensnamen.

Namensähnlichkeit ist nur ein Plausibilitätshinweis. Die Identität eines Wertpapiers
wird über die ISIN-Zuordnung eines Identitätsanbieters belegt, nicht über ähnliche
Namen. Historien werden niemals allein wegen ähnlicher Namen zusammengeführt.
"""

from __future__ import annotations

import re
import unicodedata

_LEGAL_SUFFIXES = {
    "ag", "se", "sa", "nv", "n", "v", "plc", "inc", "corp", "corporation", "ltd", "limited", "llc",
    "holding", "holdings", "group", "grp", "co", "company", "gmbh", "kgaa", "kg", "asa", "as", "ab",
    "oyj", "oy", "spa", "s", "p", "a", "bhd", "tbk", "pcl", "lp", "the", "and", "of", "de", "la",
    "registered", "shares", "share", "reg", "shs", "on", "o", "ord", "ordinary", "class", "cl",
    "adr", "ads", "sponsored", "unsponsored", "namens", "aktien", "inhaber", "vz", "st", "pref",
    "preferred", "dl", "eo", "sf", "nk", "dk", "sk", "cad", "usd", "eur", "new", "units", "unit",
    "trust", "reit", "incorporated", "aktiengesellschaft", "societe", "anonyme", "mines", "mining",
    "resources", "res", "intl", "international", "technologies", "technology", "tech",
}
_NON_WORD = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_for_search(text: str | None) -> str:
    """Kleinbuchstaben, ohne Akzente, Satzzeichen durch Leerzeichen ersetzt."""
    lowered = strip_accents(text or "").lower().replace("&", " and ")
    return " ".join(_NON_WORD.sub(" ", lowered).split())


def significant_tokens(text: str | None) -> set[str]:
    tokens = normalize_for_search(text).split()
    kept = {tok for tok in tokens if tok not in _LEGAL_SUFFIXES and len(tok) > 1}
    if kept:
        return kept
    return {tok for tok in tokens if len(tok) > 1}


def name_similarity(left: str | None, right: str | None) -> float:
    """Jaccard-Ähnlichkeit der bedeutsamen Namensbestandteile, zusätzlich Präfixtreffer."""
    a = significant_tokens(left)
    b = significant_tokens(right)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    prefix_hits = 0
    for tok_a in a - b:
        if len(tok_a) >= 4 and any(tok_b.startswith(tok_a[:4]) for tok_b in b - a if len(tok_b) >= 4):
            prefix_hits += 1
    score = (overlap + 0.5 * prefix_hits) / len(a | b)
    return min(1.0, score)
