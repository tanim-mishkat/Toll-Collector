"""Phase 2: detect license plates in the live camera feed and OCR them.

Pipeline per frame:
  YOLOv8 plate detector -> crop -> EasyOCR -> dedupe -> draw + log.

Usage:
  python download_model.py      # once
  python detect_plates.py

Press 'q' to quit.
"""
import re
import time
import threading
from collections import deque

import cv2
import numpy as np
import requests
from ultralytics import YOLO
import easyocr

from config import (
    VIDEO_SOURCE, FRAME_SKIP, MIN_OCR_CONFIDENCE,
    DEDUPE_WINDOW_SEC, PLATE_MODEL_PATH, DISPLAY_WIDTH,
    BACKEND_URL, GANTRY_ID,
)

PLATE_CLEAN_RE = re.compile(r"[^A-Z0-9\-]")


def clean_plate_text(text: str) -> str:
    """Normalize OCR output to uppercase alnum + dash."""
    return PLATE_CLEAN_RE.sub("", text.upper().replace(" ", "-"))


class PlateDeduper:
    """Suppress the same plate being logged within DEDUPE_WINDOW_SEC."""

    def __init__(self, window_sec: int):
        self.window = window_sec
        self.seen: dict[str, float] = {}

    def should_log(self, plate: str) -> bool:
        now = time.time()
        self.seen = {p: t for p, t in self.seen.items()
                     if now - t < self.window}
        if plate in self.seen:
            return False
        self.seen[plate] = now
        return True


def report_event(plate: str, confidence: float) -> None:
    """Fire-and-forget POST to the backend. Runs in a thread so the
    camera loop never blocks on the network."""
    def _post():
        try:
            from config import API_KEY
            r = requests.post(
                f"{BACKEND_URL}/toll-events",
                json={
                    "plate": plate,
                    "gantry_id": GANTRY_ID,
                    "ocr_confidence": confidence,
                },
                headers={"X-API-Key": API_KEY},
                timeout=3,
            )
            if r.ok:
                data = r.json()
                amt = data["event"]["amount_bdt"]
                owner = data["vehicle"]["owner_name"]
                print(f"    -> BDT {amt:.0f} charged to {owner} "
                      f"(event #{data['event']['id']})")
            else:
                print(f"    -> backend {r.status_code}: {r.text[:120]}")
        except requests.RequestException as e:
            print(f"    -> backend unreachable ({e.__class__.__name__}); "
                  f"is run_server.py running?")
    threading.Thread(target=_post, daemon=True).start()


def load_models():
    if not PLATE_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Plate model missing: {PLATE_MODEL_PATH}\n"
            f"Run: python download_model.py"
        )
    print(f"Loading plate detector: {PLATE_MODEL_PATH.name}")
    detector = YOLO(str(PLATE_MODEL_PATH))

    print("Loading EasyOCR (downloads ~100MB on first run)...")
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return detector, reader


def ocr_plate(reader, crop: np.ndarray) -> tuple[str, float]:
    """OCR a plate crop. Concatenates multi-line text top-to-bottom so
    two-line BD plates ('DHAKA-METRO-GA-11' / '11-1234') become one string.
    """
    if crop.size == 0:
        return "", 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0,
                      interpolation=cv2.INTER_CUBIC)
    results = reader.readtext(gray, detail=1, paragraph=False)
    if not results:
        return "", 0.0

    # Sort by Y of each block's top-left corner, then concat non-empty parts.
    results.sort(key=lambda r: r[0][0][1])
    parts: list[str] = []
    confs: list[float] = []
    for _, text, conf in results:
        if conf < 0.2:
            continue
        cleaned = clean_plate_text(text)
        if cleaned:
            parts.append(cleaned)
            confs.append(float(conf))
    if not parts:
        return "", 0.0
    combined = "-".join(parts).strip("-")
    return combined, sum(confs) / len(confs)


def resize_keep_aspect(frame, width: int):
    h, w = frame.shape[:2]
    if w == width:
        return frame
    scale = width / w
    return cv2.resize(frame, (width, int(h * scale)))


def annotate(frame, box, text: str, conf: float):
    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    label = f"{text} ({conf:.2f})" if text else "plate?"
    y_text = max(y1 - 8, 18)
    cv2.putText(frame, label, (x1, y_text),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def main() -> int:
    detector, reader = load_models()
    deduper = PlateDeduper(DEDUPE_WINDOW_SEC)

    print(f"Opening video source: {VIDEO_SOURCE}")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print("ERROR: could not open video source. See test_camera.py hints.")
        return 1

    print("Running. Press 'q' to quit.\n")
    frame_idx = 0
    last_detections: deque = deque(maxlen=8)  # keep recent boxes for display

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        frame_idx += 1
        do_detect = frame_idx % FRAME_SKIP == 0

        if do_detect:
            last_detections.clear()
            results = detector.predict(frame, verbose=False, conf=0.35)[0]
            for box in results.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(int, box)
                # Pad the box so two-line plates + any missed edge end up
                # in the crop. Vertical pad is larger since BD plates stack.
                bw, bh = x2 - x1, y2 - y1
                pad_x = int(0.08 * bw)
                pad_y = int(0.30 * bh)
                x1 = max(x1 - pad_x, 0)
                y1 = max(y1 - pad_y, 0)
                x2 = min(x2 + pad_x, frame.shape[1])
                y2 = min(y2 + pad_y, frame.shape[0])
                crop = frame[y1:y2, x1:x2]
                text, conf = ocr_plate(reader, crop)
                last_detections.append(((x1, y1, x2, y2), text, conf))

                if text and conf >= MIN_OCR_CONFIDENCE:
                    if deduper.should_log(text):
                        ts = time.strftime("%H:%M:%S")
                        print(f"[{ts}] PLATE: {text:<20} conf={conf:.2f}")
                        report_event(text, conf)

        for box, text, conf in last_detections:
            annotate(frame, box, text, conf)

        display = resize_keep_aspect(frame, DISPLAY_WIDTH)
        cv2.imshow("Phase 2 - Plate Detection (q to quit)", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
