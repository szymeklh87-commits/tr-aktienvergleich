"""Import des öffentlichen Trade-Republic-Instrumentenuniversums (Aktienabschnitt).

Quelle: https://assets.traderepublic.com/assets/files/DE/Instrument_Universe_DE_en.pdf

* Es wird ausschließlich der Abschnitt „Stocks“ verwendet.
* ISINs werden normalisiert und per Prüfziffer kontrolliert; ungültige bleiben mit
  Status sichtbar.
* Deduplizierung nach ISIN; weitere Namen derselben ISIN werden Aliase.
* Schutzregeln: fehlender Abschnitt, zu wenige Einträge, viele ungültige ISINs oder ein
  starker Umfangssprung halten die neue Version zur Prüfung zurück. Dann bleibt die
  letzte akzeptierte Liste mit ihrem ursprünglichen Datum aktiv.
* Ein öffentlicher Listeneintrag belegt keine individuelle sofortige Kaufbarkeit.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from ..util.isin import ISIN_RE, is_valid_isin, normalize_isin
from ..util.jsonio import sha256_hex

PARSER_VERSION = "tr-pdf-parser-1"
DEFAULT_URL = "https://assets.traderepublic.com/assets/files/DE/Instrument_Universe_DE_en.pdf"

_ENTRY = re.compile(r"^([A-Z]{2}[A-Z0-9]{9}[0-9])\s+(.+?)\s*$")
_ISIN_LIKE = re.compile(r"^([A-Z]{2}[A-Z0-9]{10})\b")
_SECTION_INLINE = re.compile(r"^TRADING UNIVERSE\s*[-–]\s*(.+)$", re.IGNORECASE)
_SECTION_MARK = re.compile(r"^TRADING UNIVERSE\s*[-–]\s*$", re.IGNORECASE)
_PAGE_HEADER = re.compile(r"^TRADING UNIVERSE\s*$", re.IGNORECASE)
_TABLE_HEADER = re.compile(r"^ISIN\s+Name\s*$", re.IGNORECASE)
_RULE = re.compile(r"^[_\-–=\s]{5,}$")
_PAGE_NO = re.compile(r"^(?:Page\s+)?\d+(?:\s*/\s*\d+)?$", re.IGNORECASE)
STOCK_SECTION_TITLES = {"stocks", "aktien", "shares", "equities"}


@dataclass
class UniverseEntry:
    isin: str
    name: str
    valid: bool
    page: int
    aliases: list[str] = field(default_factory=list)


@dataclass
class UniverseParseResult:
    entries: list[UniverseEntry]
    sections: list[str]
    stock_section_found: bool
    duplicates: int
    invalid_isins: int
    continuation_lines: int
    unparsed_lines: list[str]
    parser_version: str = PARSER_VERSION

    @property
    def count(self) -> int:
        return len(self.entries)


def extract_lines(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Textzeilen mit Seitennummer. pdfplumber bevorzugt, pypdf als Ersatz."""
    lines: list[tuple[int, str]] = []
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                lines.extend((page_no, line) for line in text.splitlines())
        return lines
    except ImportError:
        pass
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines.extend((page_no, line) for line in text.splitlines())
    return lines


_FOOTER_WORDS = ("trade republic", "seite", "page", "www.", "http", "©", "bafin", "stand:", "as of")


def _looks_like_name_continuation(line: str) -> bool:
    lowered = line.lower()
    return len(line) <= 80 and not any(word in lowered for word in _FOOTER_WORDS)


def parse_lines(lines: list[tuple[int, str]]) -> UniverseParseResult:
    entries: dict[str, UniverseEntry] = {}
    order: list[str] = []
    sections: list[str] = []
    in_stocks = False
    stock_found = False
    expect_title = False
    duplicates = invalid = continuation = 0
    unparsed: list[str] = []
    last: UniverseEntry | None = None

    for page, raw in lines:
        line = " ".join(raw.replace(" ", " ").split())
        if not line:
            continue
        inline = _SECTION_INLINE.match(line)
        if expect_title or inline or _SECTION_MARK.match(line):
            if _SECTION_MARK.match(line):
                expect_title = True
                continue
            title = inline.group(1).strip() if inline else line
            expect_title = False
            sections.append(title)
            is_stock = title.strip().lower() in STOCK_SECTION_TITLES
            in_stocks = is_stock
            stock_found = stock_found or is_stock
            last = None
            continue
        if _PAGE_HEADER.match(line) or _TABLE_HEADER.match(line) or _RULE.match(line) or _PAGE_NO.match(line):
            continue
        if not in_stocks:
            continue
        match = _ENTRY.match(line)
        if match:
            isin = normalize_isin(match.group(1))
            name = match.group(2).strip()
            valid = is_valid_isin(isin)
            if not valid:
                invalid += 1
            if isin in entries:
                duplicates += 1
                if name != entries[isin].name and name not in entries[isin].aliases:
                    entries[isin].aliases.append(name)
                last = entries[isin]
                continue
            entry = UniverseEntry(isin=isin, name=name, valid=valid, page=page)
            entries[isin] = entry
            order.append(isin)
            last = entry
            continue
        like = _ISIN_LIKE.match(line)
        if like and not ISIN_RE.match(like.group(1)):
            unparsed.append(line)
            continue
        if last is not None and not like and _looks_like_name_continuation(line):
            # Zeilenumbruch in einem langen Namen.
            last.name = f"{last.name} {line}".strip()
            continuation += 1
            continue
        unparsed.append(line)

    return UniverseParseResult(
        entries=[entries[i] for i in order],
        sections=sections,
        stock_section_found=stock_found,
        duplicates=duplicates,
        invalid_isins=invalid,
        continuation_lines=continuation,
        unparsed_lines=unparsed[:200],
    )


@dataclass
class UniverseDecision:
    accepted: bool
    reason: str
    added: list[str]
    removed: list[str]
    renamed: list[tuple[str, str, str]]


def evaluate_new_universe(
    result: UniverseParseResult,
    previous: dict[str, str] | None,
    *,
    min_entries: int = 1000,
    max_change_share: float = 0.10,
    max_invalid_share: float = 0.02,
) -> UniverseDecision:
    """Schutzregeln (T45). ``previous`` bildet ISIN → Name der letzten akzeptierten Version ab."""
    current = {e.isin: e.name for e in result.entries}
    previous = previous or {}
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    renamed = sorted((i, previous[i], current[i]) for i in set(current) & set(previous) if previous[i] != current[i])

    if not result.stock_section_found:
        return UniverseDecision(False, "Aktienabschnitt nicht gefunden – Dokumentstruktur geändert?", added, removed, renamed)
    if result.count < min_entries:
        return UniverseDecision(False, f"Nur {result.count} Einträge (< {min_entries}) – Parser oder Dokument prüfen", added, removed, renamed)
    if result.count and result.invalid_isins / result.count > max_invalid_share:
        return UniverseDecision(False, f"{result.invalid_isins} ungültige ISINs – Parser prüfen", added, removed, renamed)
    if previous:
        change = (len(added) + len(removed)) / max(1, len(previous))
        if change > max_change_share:
            return UniverseDecision(
                False,
                f"Umfangsänderung {change:.1%} (> {max_change_share:.0%}): +{len(added)} / −{len(removed)} – zur Prüfung zurückgehalten",
                added,
                removed,
                renamed,
            )
    return UniverseDecision(True, "akzeptiert", added, removed, renamed)


def pdf_metadata(pdf_bytes: bytes) -> dict:
    """Erstellungs-/Änderungsdatum aus den PDF-Metadaten (falls vorhanden, nicht erfunden)."""
    try:
        from pypdf import PdfReader

        info = PdfReader(io.BytesIO(pdf_bytes)).metadata or {}
        return {
            "creation_date": str(info.get("/CreationDate")) if info.get("/CreationDate") else None,
            "mod_date": str(info.get("/ModDate")) if info.get("/ModDate") else None,
            "producer": str(info.get("/Producer")) if info.get("/Producer") else None,
        }
    except Exception:
        return {"creation_date": None, "mod_date": None, "producer": None}


def universe_id(pdf_bytes: bytes) -> tuple[str, str]:
    digest = sha256_hex(pdf_bytes)
    return "U" + digest[:15], digest
