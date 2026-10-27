"""Per-frame face-detect/swap/enhance pipeline.

Extracted from modules/ui.py's live-preview worker so the exact same
processing logic can be driven headlessly (no Qt, no local webcam) by
remote_server.py, which receives frames over the network instead of
from a local camera.
"""

import time

import cv2

import modules.globals
from modules import imread_unicode
from modules.face_analyser import (
    detect_many_faces_fast,
    detect_one_face_fast,
    ensure_landmarks,
    get_one_face,
)
from modules.gpu_processing import gpu_flip
from modules.processors.frame.core import get_frame_processors_modules


class FrameSwapPipeline:
    def __init__(self, fps: float, source_image=None):
        self._frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
        self._source_image = source_image
        # "<external>" means the source face was supplied directly (e.g. by
        # a remote client) rather than read from modules.globals.source_path.
        self._last_source_path = "<external>" if source_image is not None else None
        self._cached_target_face = None
        self._cached_many_faces = None
        self._det_count = 0
        self._det_interval = max(1, round(fps * 0.08))
        self._frame_count = 0
        self._fps = 0.0
        self._prev_time = time.time()
        self._fps_update_interval = 0.5

    def set_source_image(self, source_image) -> None:
        self._source_image = source_image
        self._last_source_path = "<external>"

    def process(self, frame):
        temp_frame = frame
        if modules.globals.live_mirror:
            temp_frame = gpu_flip(temp_frame, 1)

        if not modules.globals.map_faces:
            if (
                self._last_source_path != "<external>"
                and modules.globals.source_path
                and modules.globals.source_path != self._last_source_path
            ):
                self._last_source_path = modules.globals.source_path
                self._source_image = get_one_face(imread_unicode(modules.globals.source_path))

            self._det_count += 1
            if self._det_count % self._det_interval == 0:
                if modules.globals.many_faces:
                    self._cached_target_face = None
                    self._cached_many_faces = detect_many_faces_fast(temp_frame)
                else:
                    self._cached_target_face = detect_one_face_fast(temp_frame)
                    self._cached_many_faces = None

            cached_faces = None
            if self._cached_many_faces:
                cached_faces = self._cached_many_faces
            elif self._cached_target_face is not None:
                cached_faces = [self._cached_target_face]

            if modules.globals.mouth_mask and cached_faces:
                ensure_landmarks(temp_frame, cached_faces)

            for fp in self._frame_processors:
                if fp.NAME == "DLC.FACE-ENHANCER":
                    if modules.globals.fp_ui["face_enhancer"]:
                        temp_frame = fp.process_frame(
                            None, temp_frame, detected_faces=cached_faces
                        )
                elif fp.NAME == "DLC.FACE-ENHANCER-GPEN256":
                    if modules.globals.fp_ui.get("face_enhancer_gpen256", False):
                        temp_frame = fp.process_frame(
                            None, temp_frame, detected_faces=cached_faces
                        )
                elif fp.NAME == "DLC.FACE-ENHANCER-GPEN512":
                    if modules.globals.fp_ui.get("face_enhancer_gpen512", False):
                        temp_frame = fp.process_frame(
                            None, temp_frame, detected_faces=cached_faces
                        )
                elif fp.NAME == "DLC.FACE-SWAPPER":
                    swapped_bboxes = []
                    if modules.globals.many_faces and self._cached_many_faces:
                        result = temp_frame.copy()
                        for t_face in self._cached_many_faces:
                            result = fp.swap_face(self._source_image, t_face, result)
                            if hasattr(t_face, "bbox") and t_face.bbox is not None:
                                swapped_bboxes.append(t_face.bbox.astype(int))
                        temp_frame = result
                    elif self._cached_target_face is not None:
                        temp_frame = fp.swap_face(
                            self._source_image, self._cached_target_face, temp_frame
                        )
                        if (
                            hasattr(self._cached_target_face, "bbox")
                            and self._cached_target_face.bbox is not None
                        ):
                            swapped_bboxes.append(self._cached_target_face.bbox.astype(int))
                    temp_frame = fp.apply_post_processing(temp_frame, swapped_bboxes)
                else:
                    temp_frame = fp.process_frame(self._source_image, temp_frame)
        else:
            modules.globals.target_path = None
            for fp in self._frame_processors:
                if fp.NAME == "DLC.FACE-ENHANCER":
                    if modules.globals.fp_ui["face_enhancer"]:
                        temp_frame = fp.process_frame_v2(temp_frame)
                elif fp.NAME in ("DLC.FACE-ENHANCER-GPEN256", "DLC.FACE-ENHANCER-GPEN512"):
                    fp_key = fp.NAME.split(".")[-1].lower().replace("-", "_")
                    if modules.globals.fp_ui.get(fp_key, False):
                        temp_frame = fp.process_frame_v2(temp_frame)
                else:
                    temp_frame = fp.process_frame_v2(temp_frame)

        self._frame_count += 1
        current_time = time.time()
        if current_time - self._prev_time >= self._fps_update_interval:
            self._fps = self._frame_count / (current_time - self._prev_time)
            self._frame_count = 0
            self._prev_time = current_time

        if modules.globals.show_fps:
            cv2.putText(
                temp_frame, f"FPS: {self._fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2,
            )

        return temp_frame
