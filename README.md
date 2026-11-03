# pgsl-pdf-toolkit# PGSL PDF Toolkit

An offline desktop app for everyday PDF work: merge, reorder, rotate,
compress, convert, number and watermark PDFs, without uploading anything to
the internet. It handles English, Hindi and Punjabi documents.

Built by Piyush, Chiranton, Johan and Harsh for the PGSL course at IIT Ropar.

## What it does

| Area | Tools |
| --- | --- |
| Pages | Rotate, delete, reverse, reorder (drag or keyboard), insert pages from another PDF |
| Files | Merge several PDFs in a chosen order |
| Size | Compress with a quality slider; shows the size before and after |
| Convert | Images (JPG, PNG) to PDF, PDF pages to images |
| Stamp | Page numbers in Latin or Devanagari numerals, text watermark |
| Text | Export text, OCR for scanned pages |
| Safety | Undo, and your original file is never changed until you Save |

## Install

Download the app for your system from the
[Releases page](https://github.com/2026aim1012/pgsl-pdf-toolkit/releases).
No Python is needed.

### Windows

1. Download `PGSL-PDF-Toolkit-Windows.zip` and unzip it.
2. Open the `pgsl-pdf-toolkit` folder and double-click `pgsl-pdf-toolkit.exe`.
3. The first time, Windows may say **"Windows protected your PC"**. Click
   **More info**, then **Run anyway**. This happens because the app is not
   code-signed; it only appears once.

Keep the `.exe` inside its folder: it needs the `_internal` folder next to it.

### macOS (Apple Silicon: M1 and later)

1. Download `PGSL-PDF-Toolkit-macOS.zip` and double-click it to unzip.
2. Drag **PGSL PDF Toolkit** into your **Applications** folder.
3. The first time, **right-click** the app, choose **Open**, then **Open**
   again. (A normal double-click shows "cannot be opened because the
   developer cannot be verified", because the app is not code-signed.)
4. If macOS says the app **"is damaged"**, run this once in Terminal, then
   open it again:

   ```bash
   xattr -cr "/Applications/PGSL PDF Toolkit.app"
   ```

### Linux

1. Download `PGSL-PDF-Toolkit-Linux.tar.gz`.
2. Unpack it and start the app:

   ```bash
   tar -xzf PGSL-PDF-Toolkit-Linux.tar.gz
   ./pgsl-pdf-toolkit/pgsl-pdf-toolkit
   ```

## Using it with the keyboard

Everything works without a mouse. Press **F1** in the app for the full list.
On a Mac, use **⌘ Cmd** wherever this says Ctrl.

| Keys | Does |
| --- | --- |
| Tab / Shift+Tab | Move between controls |
| Ctrl+O | Open a PDF |
| Ctrl+Shift+O | Open a folder in the Explorer |
| ← / → or Page Up / Page Down | Previous / next page |
| Shift+← / → (in the thumbnails) | Select several pages |
| Ctrl+Shift+← / → (in the thumbnails) | Move the selected pages left / right |
| Ctrl+Z | Undo |
| Ctrl+S / Ctrl+Shift+S | Save / Save As |
| Esc | Cancel a running task |
| F8 / F9 | Show or hide the Explorer / Toolkit |

Screen readers (VoiceOver on macOS, Narrator on Windows) read out every
button and each page thumbnail.

## For developers

Run from source (needs [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-extras --dev
uv run pdf-toolkit
```

Before opening a pull request, run the same checks as CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/
```

To build the double-click app yourself, or to make a release with apps for
all three systems, see [docs/BUILDING.md](docs/BUILDING.md).
