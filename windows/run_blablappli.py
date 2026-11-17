"""Point d'entrée de blablappli.exe (fabriqué avec PyInstaller)."""
import sys

from blablappli.app import main

if __name__ == "__main__":
    sys.exit(main())
