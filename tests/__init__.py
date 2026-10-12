"""Testpaket. Fügt ``backend`` dem Importpfad hinzu, damit ``import traktien`` funktioniert.

Alle Tests verwenden ausdrücklich synthetische, als solche benannte Testdaten oder
eingefrorene Formatbeispiele. Es sind keine Livekurse enthalten.
"""

import os
import sys

_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
