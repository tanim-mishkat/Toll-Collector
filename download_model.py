"""One-shot helper: download the license-plate YOLO model into ./models/.

Run once:  python download_model.py
"""
import sys
import requests
from config import PLATE_MODEL_PATH, PLATE_MODEL_URLS

HEADERS = {"User-Agent": "Mozilla/5.0 (toll-prototype)"}


def download(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Trying: {url}")
    with requests.get(url, stream=True, timeout=60,
                      allow_redirects=True, headers=HEADERS) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        written = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 15):
                f.write(chunk)
                written += len(chunk)
                if total:
                    pct = 100 * written / total
                    print(f"  {written/1e6:6.2f} MB / {total/1e6:6.2f} MB "
                          f"({pct:5.1f}%)", end="\r")
    print(f"\nSaved to {dest}")


def main() -> int:
    if PLATE_MODEL_PATH.exists():
        print(f"Model already present: {PLATE_MODEL_PATH}")
        return 0

    errors = []
    for url in PLATE_MODEL_URLS:
        try:
            download(url, PLATE_MODEL_PATH)
            return 0
        except Exception as e:
            print(f"  failed: {e}")
            errors.append((url, str(e)))
            if PLATE_MODEL_PATH.exists():
                PLATE_MODEL_PATH.unlink()

    print("\nAll auto-download sources failed:")
    for url, err in errors:
        print(f"  - {url}\n      {err}")
    print("\nManual fallback:")
    print("  1. Open any of the URLs above in a browser and save the .pt file")
    print(f"  2. Move it to: {PLATE_MODEL_PATH}")
    print("  3. Re-run: python detect_plates.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
