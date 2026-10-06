# Dev cheat sheet:

## First time on a new machine
```bash
git clone <repo-url>
cd pdf-toolkit
uv sync
uv run pdf-toolkit
```

## Before starting work
```bash
git checkout main && git pull
git checkout -b <your-branch>
```

## While working
```bash
uv add <pkg>               # add dependency
uv add --dev <pkg>         # add dev 
uv run pytest              # run tests
uv run ruff check .        # lint
```

## Before submitting a PR
```bash
git add .
git commit -m "feat: add compression slider"
git push -u origin <your-branch>
```

## → Open PR on GitHub, request review

## PR checklist
[ ] Code runs locally (uv run pdf-toolkit)  \
[ ] Tests pass (uv run pytest)              \
[ ] Lint passes (uv run ruff check .)       \
[ ] No direct pushes to main                \
[ ] At least one approval before merge

# File Structure
concise:
```
src/pdf_toolkit/
  main.py
  gui/
    explorer.py
    main_window.py
    preview.py
    session.py
    toolkit.py
    panels/
    widgets/
  core/
  resources/
tests/
```
verbose:
```
pdf-toolkit/
├── src/
│   └── pdf_toolkit/
│       ├── __init__.py
│       ├── main.py              # Entry point: QApplication + MainWindow
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── main_window.py   # QMainWindow subclass
│       │   ├── panels/          # Left "Documents" panel, right tool panel
│       │   │   ├── __init__.py
│       │   │   └── ...
│       │   └── widgets/         # Reusable custom widgets
│       │       ├── __init__.py
│       │       └── ...
│       ├── core/                # Backend logic (stubs for now)
│       │   ├── __init__.py
│       │   └── ...
│       └── resources/           # Icons, QRC files, stylesheets
│           └── ...
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── unit/
│       └── ...
├── .python-version
├── pyproject.toml
├── uv.lock
├── .gitignore
└── README.md
```
# Guidelines:

## Rules
- Python: 3.12 (exact)
- Never use `pip install`. Use `uv add`.
- Commit `uv.lock`, `pyproject.toml`, `.python-version`.
- Default window: 1280x720 (min 720p including title bar).

## Contributing

### Git
- No direct pushes to `main`.
- Branch names: just use your name.
- PRs: small, one approval, read and review.
- Run tests + lint before PR.

### AI
- Understand code before merging.
- AI is a tool, not a substitute.
- Verify AI output runs.

### PR checklist
- [ ] `uv run pdf-toolkit`
- [ ] `uv run pytest`
- [ ] `uv run ruff check .`
- [ ] PR reviewed