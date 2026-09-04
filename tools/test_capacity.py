#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont

from build_font import (
    QR_CONFIGS,
    SUPPORTED_CODES,
    bytes_from_bits,
    configure_qr,
    data_bits_for_text,
    rs_encode,
)


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def shape(font_path: Path, text: str) -> list[str]:
    font_data = font_path.read_bytes()
    font = hb.Font(hb.Face(font_data))
    glyph_order = TTFont(font_path).getGlyphOrder()
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer, {"rlig": True})
    return [glyph_order[item.codepoint] for item in buffer.glyph_infos]


def payload(length: int) -> str:
    return "".join(chr(SUPPORTED_CODES[i % len(SUPPORTED_CODES)]) for i in range(length))


def check_closed_block(label: str, length: int) -> None:
    configure_qr(label)
    text = payload(length)
    glyphs = shape(DIST / f"qrfont-{label}.ttf", f"[{text}]")

    expected_bytes = [f"byte_{i:02d}_{ord(ch):03d}" for i, ch in enumerate(text)]
    actual_bytes = [name for name in glyphs if name.startswith("byte_")]
    assert actual_bytes == expected_bytes, (label, length, actual_bytes[-3:])

    expected_parity = rs_encode(bytes_from_bits(data_bits_for_text(text)))
    actual_parity = [
        int(name.split("_", 1)[1])
        for name in glyphs
        if name.startswith("s") and name[1:2].isdigit()
    ]
    assert actual_parity == expected_parity, (label, length, actual_parity)

    assert f"count_{length:02d}" in glyphs
    assert f"tail_{length:02d}" in glyphs
    assert f"qr_base_{length:02d}" in glyphs
    assert not any(
        name == "open_delim"
        or name == "close_delim"
        or name.startswith("len_")
        or name.startswith("char_")
        for name in glyphs
    ), (label, length, glyphs[-4:])


def check_incomplete_block(label: str) -> None:
    text = payload(QR_CONFIGS[label]["max_len"])
    glyphs = shape(DIST / f"qrfont-{label}.ttf", f"[{text}")
    assert glyphs[0] == "open_delim", (label, glyphs[:3])
    assert not any(name == "header_bits" for name in glyphs), label


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all",
        action="store_true",
        help="check every supported length instead of boundary cases",
    )
    args = parser.parse_args()

    for label, config in QR_CONFIGS.items():
        maximum = config["max_len"]
        lengths = range(maximum + 1) if args.all else range(max(0, maximum - 5), maximum + 1)
        for length in lengths:
            check_closed_block(label, length)
        check_incomplete_block(label)
        print(f"QR Font {label}: verified through {maximum} characters")


if __name__ == "__main__":
    main()
