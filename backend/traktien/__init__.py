"""TR-Aktienvergleich – tägliche historische Ranglisten für 1 bis 90 Kalendertage.

Das Paket ist in getrennte Schichten aufgeteilt:

* ``traktien.analytics`` – reiner Rechenkern ohne Ein-/Ausgabe (Fenster, Kennzahlen,
  Qualitätsregeln, elf Gewichtungen, Häufigkeiten, Abdeckungsbilanz, Umschichtungs-Regel).
* ``traktien.providers`` – austauschbare Adapter für TR-Universum, Identität,
  Börsenkalender und Kurse.
* ``traktien.store`` – dauerhafter Zustand (SQLite) mit versionierten Migrationen.
* ``traktien.jobs`` – täglicher Lauf mit Sperre, Checkpoints, Wiederanlauf.
* ``traktien.publish`` – statische, unveränderliche Snapshot-Veröffentlichung.
"""

__version__ = "1.18.0"
