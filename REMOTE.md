# Running the face-swap on a different, more capable machine

This lets a low-end Windows laptop (or any machine without a GPU and
without the full ML stack installed) get live face-swapped video from
a more capable machine on the same network — e.g. this Mac. The low-end
machine only needs OpenCV, numpy, websockets, and pyvirtualcam; it
never loads onnxruntime, insightface, or any model file.

**How it works:** the low-end machine ("client") captures its own
webcam, sends each frame over a WebSocket to the capable machine
("server"), which runs the real detect/swap pipeline and sends the
swapped frame back. The client then pushes that into a local virtual
camera, exactly like the built-in direct-virtual-camera mode, so Zoom/
Meet/Teams on the client machine can select it.

This is **not** a hosted/cloud service and shares nothing with any
third party — both machines are yours, talking directly to each other
over your own network. (If a link, token, or `.exe` claiming to offer
this as a hosted service shows up from anywhere else, don't run it —
see the warning at the bottom.)

## 1. On the capable machine (server)

```bash
source venv/bin/activate
python remote_server.py --token <pick-a-shared-secret>
```

By default it listens on all interfaces, port 8765, and picks the
best available execution provider (CoreML on Apple Silicon, etc. —
override with `--execution-provider`). Find this machine's LAN IP
(e.g. `ipconfig getifaddr en0` on macOS) — the client needs it.

Only one client session is supported at a time.

## 2. On the low-end machine (client)

```bash
cd client
python -m venv venv
# Windows: venv\Scripts\activate       macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

python remote_client.py --list-cameras   # find your camera's index
python remote_client.py \
  --server ws://<server-ip>:8765 \
  --token <the-same-shared-secret> \
  --face path\to\your_face.jpg \
  --camera <index-from-above>
```

A small preview window opens (press `q` or Esc to stop); status line
in the terminal confirms which virtual camera device is active. Select
that device as the camera in Zoom/Meet/Teams.

## Notes and limits

- Both machines must be reachable over the network (same LAN, or a VPN
  between them) — this streams raw video, it is not designed to be
  exposed directly to the public internet.
- Network round-trip adds latency per frame beyond what the fully
  local mode has — fine on a home LAN, noticeably worse over distance.
- The `--token` is a shared secret, not real authentication/encryption
  (traffic is unencrypted WebSocket, `ws://` not `wss://`) — treat it
  as "keep randoms on my LAN from connecting," not as securing
  sensitive data over an untrusted network.
- If the client's virtual camera doesn't show up, install OBS Studio
  once on the client machine (even without opening it) so its virtual
  camera driver gets registered — same requirement as the local mode.

## A warning, since this came up

A fake product using almost this exact pitch ("just run a link + an
`.exe`, no setup needed") turned out to upload the victim's ID photo
to an unofficial server before doing anything else — not a real
face-swap tool, a credential/identity-harvesting lure. The setup
above only talks to a server you started yourself, on a machine you
control, with its source fully readable in this repository. Don't
replace the server address with someone else's, and don't run a
`.exe`/binary from an unverified source claiming to do this for you.
