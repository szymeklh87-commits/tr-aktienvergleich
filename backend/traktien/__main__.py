import sys

from .cli import main

# Schutz für Hilfsprozesse (ab 1.10 rechnet der Lauf auf mehreren Kernen): nur beim direkten Start ausführen
if __name__ == "__main__":
    sys.exit(main())
