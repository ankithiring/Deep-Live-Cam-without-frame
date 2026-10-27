#!/usr/bin/env python3
"""Headless face-swap server.

Runs the same detect/swap pipeline as the local GUI's "Live" mode, but
receives webcam frames over a WebSocket from a remote, lightweight
client (see client/remote_client.py) instead of reading a local
camera. Intended for a low-end machine (e.g. a plain Windows laptop)
to get live face-swapped video without installing the full ML stack
(onnxruntime, insightface, CoreML/CUDA, ...) locally - only this
machine needs that; the client only needs a webcam, OpenCV, and
pyvirtualcam.

Protocol (one active session at a time):
  client -> server   text   {"type": "hello", "token": "...", "fps": 30}
  server -> client   text   {"type": "hello_ack", "ok": true|false, "error"?: "..."}
  client -> server   binary <source face image bytes (jpg/png)>
  server -> client   text   {"type": "face_ack", "ok": true|false, "error"?: "..."}
  (repeat) client -> server  binary <webcam frame jpg>
           server -> client  binary <swapped frame jpg>

Usage:
  python remote_server.py --token mysecret
  python remote_server.py --token mysecret --execution-provider coreml --port 8765
"""
import argparse
import asyncio
import json
import os
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import cv2
import numpy as np
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

import modules.globals
from modules.core import decode_execution_providers, suggest_default_execution_provider
from modules.face_analyser import get_one_face
from modules.face_swap_pipeline import FrameSwapPipeline

JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 85]

# Only one live session is supported at a time - this is a personal/
# home-LAN tool, not a multi-tenant service.
_session_lock = asyncio.Lock()


def _decode_image(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _encode_jpeg(frame) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, JPEG_PARAMS)
    if not ok:
        raise RuntimeError("failed to encode frame")
    return buf.tobytes()


async def _handle_client(websocket, token: str) -> None:
    if _session_lock.locked():
        await websocket.send(json.dumps({
            "type": "hello_ack", "ok": False,
            "error": "server busy: another client is already connected",
        }))
        return

    async with _session_lock:
        peer = websocket.remote_address
        print(f"[remote_server] client connected: {peer}")

        try:
            hello_raw = await websocket.recv()
            hello = json.loads(hello_raw)
        except Exception as exc:
            print(f"[remote_server] bad hello from {peer}: {exc}")
            return

        if hello.get("type") != "hello" or hello.get("token") != token:
            await websocket.send(json.dumps({
                "type": "hello_ack", "ok": False, "error": "bad token",
            }))
            print(f"[remote_server] rejected {peer}: bad token")
            return

        fps = float(hello.get("fps", 30))
        await websocket.send(json.dumps({"type": "hello_ack", "ok": True}))

        try:
            face_bytes = await websocket.recv()
        except ConnectionClosed:
            return
        if not isinstance(face_bytes, (bytes, bytearray)):
            await websocket.send(json.dumps({
                "type": "face_ack", "ok": False, "error": "expected binary image",
            }))
            return

        face_image = _decode_image(face_bytes)
        source_face = get_one_face(face_image) if face_image is not None else None
        if source_face is None:
            await websocket.send(json.dumps({
                "type": "face_ack", "ok": False, "error": "no face detected in image",
            }))
            print(f"[remote_server] {peer}: no face detected in uploaded image")
            return

        await websocket.send(json.dumps({"type": "face_ack", "ok": True}))
        print(f"[remote_server] {peer}: session starting (fps={fps:.0f})")

        pipeline = FrameSwapPipeline(fps, source_image=source_face)
        frame_count = 0
        try:
            async for message in websocket:
                if not isinstance(message, (bytes, bytearray)):
                    continue
                frame = _decode_image(message)
                if frame is None:
                    continue
                swapped = pipeline.process(frame)
                await websocket.send(_encode_jpeg(swapped))
                frame_count += 1
        except ConnectionClosed:
            pass
        finally:
            print(f"[remote_server] {peer}: session ended ({frame_count} frames)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0", help="interface to bind (default: all interfaces)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", required=True, help="shared secret the client must send to connect")
    parser.add_argument(
        "--execution-provider", nargs="+", default=[suggest_default_execution_provider()],
        help="e.g. coreml, cuda, cpu (same values as run.py)",
    )
    parser.add_argument(
        "--frame-processor", nargs="+", default=["face_swapper"],
        choices=["face_swapper", "face_enhancer", "face_enhancer_gpen256", "face_enhancer_gpen512"],
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    modules.globals.frame_processors = args.frame_processor
    modules.globals.execution_providers = decode_execution_providers(args.execution_provider)
    for enhancer_key in ("face_enhancer", "face_enhancer_gpen256", "face_enhancer_gpen512"):
        modules.globals.fp_ui[enhancer_key] = enhancer_key in args.frame_processor

    print(f"[remote_server] execution providers: {modules.globals.execution_providers}")
    print(f"[remote_server] listening on ws://{args.host}:{args.port}")

    async with serve(lambda ws: _handle_client(ws, args.token), args.host, args.port, max_size=16 * 1024 * 1024):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
