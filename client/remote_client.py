#!/usr/bin/env python3
"""Thin remote client for Deep-Live-Cam's remote_server.py.

Runs on a low-end machine with no GPU and none of the heavy ML
dependencies (onnxruntime, insightface, etc.) - only OpenCV, numpy,
websockets and pyvirtualcam. It captures the local webcam, sends each
frame over the network to a remote_server.py instance (running the
real face-swap pipeline on a more capable machine), and feeds the
swapped frames it gets back into a local virtual camera that apps
like Zoom/Google Meet/Teams can select directly.

Setup:
  pip install -r requirements.txt
  python remote_client.py --server ws://<server-ip>:8765 --token mysecret --face my_face.jpg

Then select "OBS Virtual Camera" (or your virtual-cam backend's name)
as the camera in your video-call app.
"""
import argparse
import asyncio
import json
import os
import sys
import time

import cv2
import numpy as np
from cv2_enumerate_cameras import enumerate_cameras
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

try:
    import pyvirtualcam
except ImportError:
    pyvirtualcam = None

# modules/video_capture.py lives in the repo root's modules/ package.
# Reusing it gets us the same cross-platform camera-open logic (and
# bug fixes) as the main GUI app, instead of a second copy of it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.video_capture import VideoCapturer  # noqa: E402

JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 85]


def list_cameras() -> None:
    import platform
    if platform.system() == "Darwin":
        cams = list(enumerate_cameras(cv2.CAP_AVFOUNDATION))
    elif platform.system() == "Windows":
        cams = list(enumerate_cameras(cv2.CAP_DSHOW))
    else:
        cams = list(enumerate_cameras())
    if not cams:
        print("No cameras found.")
        return
    print("Available cameras:")
    for cam in cams:
        print(f"  {cam.index}: {cam.name}")


def _encode_jpeg(frame) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, JPEG_PARAMS)
    if not ok:
        raise RuntimeError("failed to encode frame")
    return buf.tobytes()


def _decode_image(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


async def run_client(args: argparse.Namespace) -> None:
    with open(args.face, "rb") as f:
        face_bytes = f.read()

    cap = VideoCapturer(args.camera)
    if not cap.start(args.width, args.height, args.fps):
        print("Failed to open local camera.")
        return

    vcam = None
    if pyvirtualcam is not None:
        try:
            vcam = pyvirtualcam.Camera(
                width=cap.actual_width, height=cap.actual_height,
                fps=max(1, round(cap.actual_fps)),
            )
            print(f"[remote_client] virtual camera active: {vcam.device}")
        except Exception as exc:
            print(f"[remote_client] virtual camera unavailable, preview-only: {exc}")

    print(f"[remote_client] connecting to {args.server} ...")
    async with connect(args.server, max_size=16 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "hello", "token": args.token, "fps": cap.actual_fps}))
        hello_ack = json.loads(await ws.recv())
        if not hello_ack.get("ok"):
            print(f"[remote_client] server rejected connection: {hello_ack.get('error')}")
            return

        await ws.send(face_bytes)
        face_ack = json.loads(await ws.recv())
        if not face_ack.get("ok"):
            print(f"[remote_client] server rejected face image: {face_ack.get('error')}")
            return

        print("[remote_client] session started. Press Ctrl+C to stop"
              + ("" if args.no_preview else ", or 'q'/Esc in the preview window."))

        frame_count = 0
        t0 = time.time()
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                try:
                    await ws.send(_encode_jpeg(frame))
                    reply = await ws.recv()
                except ConnectionClosed:
                    print("[remote_client] server connection closed.")
                    break

                swapped = _decode_image(reply)
                if swapped is None:
                    continue

                if vcam is not None:
                    try:
                        vcam.send(cv2.cvtColor(swapped, cv2.COLOR_BGR2RGB))
                    except Exception as exc:
                        print(f"[remote_client] virtual camera send failed: {exc}")

                if not args.no_preview:
                    cv2.imshow("Deep-Live-Cam (remote)", swapped)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break

                frame_count += 1
                if frame_count % 100 == 0:
                    elapsed = time.time() - t0
                    print(f"[remote_client] {frame_count} frames, {frame_count / elapsed:.1f} fps avg")
        except KeyboardInterrupt:
            pass
    cap.release()
    if vcam is not None:
        vcam.close()
    if not args.no_preview:
        cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--server", help="e.g. ws://192.168.1.50:8765")
    parser.add_argument("--token", help="shared secret, must match the server's --token")
    parser.add_argument("--face", help="path to a local image of the face to swap in")
    parser.add_argument("--camera", type=int, default=0, help="camera index (see --list-cameras)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-preview", action="store_true", help="skip the local cv2.imshow preview window")
    parser.add_argument("--list-cameras", action="store_true", help="list available cameras and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_cameras:
        list_cameras()
        return
    missing = [name for name in ("server", "token", "face") if getattr(args, name) is None]
    if missing:
        print(f"Missing required arguments: {', '.join('--' + m for m in missing)}")
        sys.exit(1)
    asyncio.run(run_client(args))


if __name__ == "__main__":
    main()
