from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2


class SourceOpenError(RuntimeError):
    pass


@dataclass
class SourceInfo:
    kind: str
    requested_width: int | None = None
    requested_height: int | None = None
    requested_fps: int | None = None
    width: int = 0
    height: int = 0
    fps: float = 0.0
    observed_fps: float = 0.0
    frame_count: int = 0


class OpenCVSource:
    def __init__(self, kind: str = "video", path: str | Path | None = None,
                 camera_index: int = 0, loop: bool = False):
        self.kind, self.path, self.camera_index, self.loop = kind, Path(path) if path else None, camera_index, loop
        self.capture: cv2.VideoCapture | None = None
        self.info = SourceInfo(kind, 1280 if kind == "webcam" else None, 720 if kind == "webcam" else None, 60 if kind == "webcam" else None)
        self._read_count = 0
        self._started = 0.0

    def open(self) -> SourceInfo:
        if self.kind == "video":
            if self.path is None or not self.path.is_file():
                raise SourceOpenError(f"Video does not exist: {self.path}")
            self.capture = cv2.VideoCapture(str(self.path))
        else:
            self.capture = cv2.VideoCapture(self.camera_index)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.capture.set(cv2.CAP_PROP_FPS, 60)
        if self.capture is None or not self.capture.isOpened():
            self.release()
            target = str(self.path) if self.kind == "video" else f"webcam index {self.camera_index}"
            raise SourceOpenError(f"Could not open {target}. Check the path or camera connection.")
        self.info.width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.info.height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.info.fps = float(self.capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self.info.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._read_count, self._started = 0, time.perf_counter()
        return self.info

    def read(self):
        if self.capture is None:
            raise SourceOpenError("Source is not open")
        ok, frame = self.capture.read()
        if not ok and self.loop and self.kind == "video":
            self.restart()
            ok, frame = self.capture.read()
        if ok:
            self._read_count += 1
            elapsed = time.perf_counter() - self._started
            if elapsed > 0.5:
                self.info.observed_fps = self._read_count / elapsed
        return ok, frame

    def restart(self):
        if self.capture is not None and self.kind == "video":
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._read_count, self._started = 0, time.perf_counter()

    def release(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def __iter__(self) -> Iterator:
        while True:
            ok, frame = self.read()
            if not ok:
                return
            yield frame
