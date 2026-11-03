"""
launch.py
---------
The file PyInstaller starts the app from.

Why not start from src/pdf_toolkit/main.py directly? PyInstaller runs its
start file as a loose script, so inside main.py `__file__` would point at
the top of the bundle and `resources/style.qss` would not be found (the app
would open with no styling). Importing main as part of the `pdf_toolkit`
package instead keeps every `Path(__file__)` lookup working, exactly as
when we run `uv run pdf-toolkit`.
"""

from pdf_toolkit.main import main

if __name__ == "__main__":
    main()
