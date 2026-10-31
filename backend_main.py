"""PyInstaller entry point for the Simpld backend.

Build:  pyinstaller --noconfirm --clean --name simpld-backend --onedir ^
            --console --distpath dist-backend --workpath build-backend backend_main.py

The frozen exe behaves exactly like `python -m backend.app`: it reads
SIMPLD_PORT / SIMPLD_MODEL_DIR / SIMPLD_MOCK from the environment, which the
Electron shell sets when it spawns the sidecar.
"""

import multiprocessing

from backend.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
