import json
import os
from http.server import BaseHTTPRequestHandler

from logo_bot.config import MAX_INPUT_MB, OUTPUT_FORMAT, OUTPUT_QUALITY


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        payload = {
            "ok": True,
            "service": "logo-overlay-bot",
            "token_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip()),
            "output_format": OUTPUT_FORMAT,
            "output_quality": OUTPUT_QUALITY,
            "max_input_mb": MAX_INPUT_MB,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        self.do_GET()
