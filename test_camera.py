"""Phase 1: verify the phone camera stream reaches the laptop.

Usage:
  1. Install "IP Webcam" on your Android phone.
  2. Start server in the app; note the URL (e.g. http://192.168.0.5:8080).
  3. Put <that-url>/video into config.VIDEO_SOURCE.
  4. Run:  python test_camera.py
  5. Press 'q' to quit.
"""
import time
import cv2

from config import VIDEO_SOURCE, DISPLAY_WIDTH


def resize_keep_aspect(frame, width: int):
    h, w = frame.shape[:2]
    if w == width:
        return frame
    scale = width / w
    return cv2.resize(frame, (width, int(h * scale)))


def main() -> int:
    print(f"Opening video source: {VIDEO_SOURCE}")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print("ERROR: could not open video source.")
        print("  - Is the phone on the same Wi-Fi as the laptop?")
        print("  - Is IP Webcam's 'Start server' pressed?")
        print("  - Does the URL end with /video ?")
        return 1

    print("Stream open. Press 'q' in the window to quit.")
    last = time.time()
    frames = 0
    fps = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed; retrying...")
            time.sleep(0.1)
            continue

        frames += 1
        now = time.time()
        if now - last >= 1.0:
            fps = frames / (now - last)
            frames = 0
            last = now

        frame = resize_keep_aspect(frame, DISPLAY_WIDTH)
        cv2.putText(frame, f"FPS: {fps:.1f}", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("Phase 1 - Camera Stream (q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
