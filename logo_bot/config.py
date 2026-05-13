from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
LOGO_DIR = BASE_DIR / "assets" / "logos"
OUTPUT_SIZE = (1080, 1350)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
MAX_INPUT_MB = int(os.getenv("MAX_INPUT_MB", "20"))
MAX_INPUT_BYTES = MAX_INPUT_MB * 1024 * 1024
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "JPEG").strip().upper()
OUTPUT_QUALITY = int(os.getenv("OUTPUT_QUALITY", "95"))
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "3600"))


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    left_logo: str
    right_logo: str

    def logo_path(self, side: str) -> Path:
        if side == "left":
            return LOGO_DIR / self.left_logo
        if side == "right":
            return LOGO_DIR / self.right_logo
        raise ValueError(f"Unsupported side: {side}")

    @property
    def is_ready(self) -> bool:
        return self.logo_path("left").exists() and self.logo_path("right").exists()


CHANNELS: dict[str, Channel] = {
    "sportcore": Channel("sportcore", "Sportcore", "sportcore_left.png", "sportcore_right.png"),
    "sportcorefinds": Channel(
        "sportcorefinds",
        "Sportcore Finds",
        "sportcorefinds_left.png",
        "sportcorefinds_right.png",
    ),
    "musiccore": Channel("musiccore", "Music Core", "musiccore_left.png", "musiccore_right.png"),
    "bolshe": Channel("bolshe", "Больше", "bolshe_left.png", "bolshe_right.png"),
}

SIDES = {
    "left": "слева",
    "right": "справа",
}


def get_channel(key: str) -> Channel | None:
    return CHANNELS.get(key)


def output_extension_and_mime() -> tuple[str, str]:
    if OUTPUT_FORMAT == "PNG":
        return "png", "image/png"
    return "jpg", "image/jpeg"

