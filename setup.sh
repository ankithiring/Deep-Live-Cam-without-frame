#!/usr/bin/env bash
# One-time environment setup for Deep-Live-Cam on macOS/Linux.
#
# Usage:
#   git clone <this repo>
#   cd Deep-Live-Cam
#   ./setup.sh
#   python run.py   # every time you want to launch the app afterwards
#
# This only creates the virtual environment and installs Python
# dependencies. Model files (inswapper, face-enhancer, insightface
# analysis models) are downloaded automatically by run.py itself on
# first launch - no manual download needed.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON_BIN=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "Error: no python3 interpreter found. Install Python 3.11+ first." >&2
    exit 1
fi

echo "Using interpreter: $(command -v "$PYTHON_BIN") ($("$PYTHON_BIN" --version))"

if [ ! -d venv ]; then
    echo "Creating virtual environment in ./venv ..."
    "$PYTHON_BIN" -m venv venv
else
    echo "Virtual environment ./venv already exists, reusing it."
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing dependencies from requirements.txt ..."
pip install --upgrade pip
pip install -r requirements.txt

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo ""
    echo "Warning: ffmpeg not found on PATH. Video file processing needs it."
    echo "  macOS:  brew install ffmpeg"
    echo "  Linux:  sudo apt install ffmpeg   (or your distro's equivalent)"
fi

echo ""
echo "Setup complete. To run the app:"
echo "  source venv/bin/activate"
echo "  python run.py"
echo ""
echo "Notes for a new machine:"
echo "  - First launch downloads the face-swap/analysis models automatically"
echo "    (requires internet access, a few hundred MB)."
echo "  - macOS will prompt for Camera permission the first time you click"
echo "    Live - grant it to whichever app/terminal you launched this from."
echo "  - To output directly to a virtual camera (e.g. for Google Meet)"
echo "    without running OBS Studio's GUI, install OBS Studio once so its"
echo "    virtual camera driver is registered on the system, then this app"
echo "    will use it automatically."
