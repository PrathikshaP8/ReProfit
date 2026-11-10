import json
import urllib.request
from pathlib import Path

BOUNDARY = "----ReProfitBoundary"


def post_file(url: str, path: Path) -> str:
    data = path.read_bytes()
    body = (
        f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode()
        + data
        + f"\r\n--{BOUNDARY}--\r\n".encode()
    )
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode()


for name in [
    "uploads/RET-2024-011-levi.jpg",
    "uploads/RET-2024-006-hp_b.jpg",
    "uploads/RET-2024-006-Screenshot 2026-08-24 155313.png",
    "uploads/RET-2024-008-Screenshot 2026-08-24 155538.png",
]:
    path = Path(name)
    payload = json.loads(post_file("http://127.0.0.1:8000/api/returns/predict-condition", path))
    print(
        path.name,
        payload["source"],
        payload["condition"],
        payload["condition_score"],
        payload["confidence"],
    )
