#!/usr/bin/env bash
# Launch Media Tools using the project's own virtualenv.
# Self-locating, so it works regardless of where the repo lives or what the
# current working directory is.
set -euo pipefail

here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
py="$here/.venv/bin/python"

if [[ ! -x "$py" ]]; then
    echo "Virtualenv not found at $py" >&2
    echo "Set it up first with:  cd \"$here\" && uv sync" >&2
    # If launched from a file manager (no terminal), surface the error in a dialog.
    command -v zenity >/dev/null 2>&1 && \
        zenity --error --text="Media Tools isn't set up yet.\nRun 'uv sync' in:\n$here" 2>/dev/null
    exit 1
fi

exec "$py" "$here/main.py" "$@"
