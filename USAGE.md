# Running Deep-Live-Cam with a virtual camera (macOS)

This covers first-time setup and the day-to-day flow for feeding a live
face-swapped video into apps like Google Meet, Zoom, or Teams.

## 1. First-time setup

```bash
git clone <this repo>
cd Deep-Live-Cam
./setup.sh
```

`setup.sh` creates a `venv` and installs everything in `requirements.txt`.
You do not need to manually download any model files — `python run.py`
downloads the face-swap and face-analysis models itself on first launch
(a few hundred MB, needs internet access once).

**Optional but recommended:** install [OBS Studio](https://obsproject.com/)
once, even if you never open it. Installing it registers a system-level
"OBS Virtual Camera" driver that this app can send frames to directly —
see step 4.

## 2. Launch the app

```bash
source venv/bin/activate
python run.py
```

The first time you click **Live**, macOS will ask for **Camera**
permission. Grant it to whichever app/terminal you launched `run.py`
from (Terminal.app, VS Code, etc. — whichever one is actually running
the Python process). If you don't get a prompt and the preview is
black, check **System Settings → Privacy & Security → Camera** and
make sure that app is enabled there, then quit and relaunch it (a
permission change doesn't apply to an already-running process).

## 3. Go live

- Click **"Select a face"** and pick your source image.
- In the **Select Camera** dropdown, pick your real camera by name
  (e.g. "MacBook Air Camera" or your external webcam). Some Macs list
  other registered devices too (iPhone Continuity Camera, OBS Virtual
  Camera, leftover virtual cameras from other software) — those are
  not real input sources and will show a black/frozen preview if
  selected.
- Click **"Live"**. After 10-30 seconds a frameless **"Live Preview"**
  window opens showing the swapped feed.
  - Drag anywhere on the video to move the window.
  - Press **Esc** to close it.

## 4. Get the feed into Google Meet / Zoom / etc.

**Option A — direct virtual camera output (no OBS GUI needed):**

If OBS Studio has been installed at least once on this Mac, the app
automatically pushes every swapped frame straight into the **"OBS
Virtual Camera"** device as soon as you go Live — you'll see
`Virtual camera active: OBS Virtual Camera` in the status line. Just
open Google Meet and select **"OBS Virtual Camera"** as your camera.
Nothing else to configure, and OBS itself never needs to be running.

**Option B — OBS Window Capture (fallback, if Option A isn't available):**

1. Open OBS Studio.
2. Sources → `+` → **Window Capture** → select the **"Live Preview"**
   window.
3. Click **Start Virtual Camera** (bottom-right of OBS).
4. In Google Meet, select **"OBS Virtual Camera"**.

Note: every time you close and reopen Live in Deep-Live-Cam, it's a
brand-new window, so you'll need to re-pick "Live Preview" in the
Window Capture source's Properties again — OBS won't follow it
automatically.

## Troubleshooting

**Preview window is black.**
Almost always one of:
- Camera permission not granted yet (see step 2).
- Wrong device selected in the dropdown — pick the one that's
  actually your physical camera by name, not a virtual one.

**Video is frozen in Google Meet but moving fine in the app itself.**
This means OBS's Window Capture source is still bound to an old,
now-closed "Live Preview" window. Re-select "Live Preview" in the
Window Capture source's Properties (Option B above), or switch to
Option A to avoid this class of issue entirely.

**App crashes/aborts when closing or restarting Live.**
Already fixed — the shutdown path now waits for background threads to
actually finish instead of timing out and letting Qt tear down a
still-running thread.

**Google Meet camera is still frozen after fixing the above.**
Toggle the camera off and back on inside Meet, or leave and rejoin the
call, so Chrome re-requests a fresh stream instead of reusing a cached
frame.
