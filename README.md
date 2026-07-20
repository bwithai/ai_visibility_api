# AI VISIBILITY API - Backend

## Requirements

* [Docker](https://www.docker.com/).
* [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Quick start

**1. Install** (from project root, pick one):

```console
uv sync                                    # uv
python -m venv .venv && pip install -e .   # pip
poetry install                             # Poetry
```

**2. Run:**

```console
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\Activate.ps1         # Windows

flask --app app:create_app run
```