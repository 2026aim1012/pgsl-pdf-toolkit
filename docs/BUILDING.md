# Building the app

This turns the project into a normal app people can double-click, with no
Python needed. We use PyInstaller with the recipe in `pdf-toolkit.spec`.

**PyInstaller only builds for the system it runs on.** A Mac makes the Mac
app, Windows makes the Windows `.exe`, and Linux makes the Linux app. To get
all three, build on each system, or let GitHub Actions do it (coming in
`.github/workflows/build.yml`).

## Build on your own computer

From the project folder:

```bash
uv sync --all-extras --dev                    # installs PyInstaller too
uv run pyinstaller pdf-toolkit.spec --noconfirm
uv run python packaging/check_build.py --run  # checks the result
```

The first build takes a few minutes. You get:

| System  | Where the app is                                   |
| ------- | -------------------------------------------------- |
| macOS   | `dist/PGSL PDF Toolkit.app`                        |
| Windows | `dist/pgsl-pdf-toolkit/pgsl-pdf-toolkit.exe`       |
| Linux   | `dist/pgsl-pdf-toolkit/pgsl-pdf-toolkit`           |

On Windows and Linux, share the whole `dist/pgsl-pdf-toolkit` folder (zip
it), not just the program file: the program needs the `_internal` folder
next to it.

## What `check_build.py` tells you

- The **size** of the build.
- Whether these made it in: the style sheet, the Devanagari font (page
  numbers in Hindi), the PDFium library (page previews) and the OCR models.
- With `--run`: whether the app starts and stays open for 10 seconds. If it
  crashes, it prints the error to paste into a GitHub issue.

## Opening the app the first time

The app is not code-signed (that costs money), so the system warns once:

- **macOS:** "cannot be opened because the developer cannot be verified".
  Right-click the app, choose **Open**, then **Open** again.
- **Windows:** "Windows protected your PC". Click **More info**, then
  **Run anyway**.

## If something goes wrong

| What you see | Likely cause | Fix |
| --- | --- | --- |
| App opens with no colours or styling | `resources/` not in the build | Check `datas` in `pdf-toolkit.spec` |
| Blank page previews, or a PDFium error | PDFium library missing | `check_build.py` shows "MISSING PDFium"; check `binaries` in the spec |
| `ModuleNotFoundError: No module named ...` | PyInstaller missed an import | Add the module name to `hiddenimports` in the spec |
| macOS: "is damaged and can't be opened" | macOS quarantine on a downloaded app | Run `xattr -cr "PGSL PDF Toolkit.app"` once |
| Build is very large | The OCR library (ONNX Runtime + OpenCV) | Expected for now; note the size in the issue |
