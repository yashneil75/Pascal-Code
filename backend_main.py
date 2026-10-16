"""PyInstaller entry point for the Pascal Code backend.

Build:  pyinstaller --noconfirm --clean --name pascal-backend --onedir ^
            --console --distpath dist-backend --workpath build-backend backend_main.py

The frozen exe behaves exactly like `python -m backend.app`: it reads
PASCAL_PORT / PASCAL_MODEL_DIR / PASCAL_MOCK from the environment, which the
Electron shell sets when it spawns the sidecar.
"""

import multiprocessing

from backend.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
