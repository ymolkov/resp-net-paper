#!/usr/bin/env python3
"""Extract the unchanged vector panels of Molkov et al. (2025), Figure 1.

The publisher's CC0 figure is an illustration of the earlier method, not a
new analysis. See THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, RectangleObject

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://cdn.elifesciences.org/articles/101959/elife-101959-figures-v1.pdf"
SOURCE_SHA256 = "7f638bff67b48842019e833abfb064512a006aee2da119d4f6f8a85c69405869"
OUTPUT = ROOT / "paper/figures/conductance_reconstruction_example.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Previously downloaded publisher figures PDF")
    args = parser.parse_args()
    if args.source:
        data = args.source.read_bytes()
    else:
        with urlopen(SOURCE_URL, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Publisher PDF differs from the reviewed source; inspect before reuse")

    reader = PdfReader(BytesIO(data))
    page = reader.pages[1]
    operations = page.get_contents().operations
    starts = [i for i, (args, op) in enumerate(operations)
              if op == b"BDC" and list(args) == ["/PlacedGraphic", "/MC1"]]
    if len(starts) != 1:
        raise ValueError("Expected one Figure 1 artwork block on publisher page 2")
    start = starts[0]
    depth = 1
    end = start
    for end in range(start + 1, len(operations)):
        op = operations[end][1]
        if op in (b"BDC", b"BMC"):
            depth += 1
        elif op == b"EMC":
            depth -= 1
        if depth == 0:
            break
    if depth:
        raise ValueError("Unbalanced artwork content")

    # Preserve every drawing/text operator in the artwork, excluding the
    # journal header, original caption and footer. No panels are redrawn.
    writer = PdfWriter()
    page = writer.add_page(page)
    content = ContentStream(None, writer)
    content.operations = [([], b"q"), *operations[start + 1:end], ([], b"Q")]
    page.replace_contents(content)
    bounds = RectangleObject((36, 434, 503, 739))
    page.mediabox = bounds
    page.cropbox = RectangleObject(bounds)
    for key in ("/Annots", "/StructParents", "/PieceInfo"):
        page.pop(key, None)
    writer.add_metadata({
        "/Title": "Molkov et al. (2025), Figure 1: conductance reconstruction",
        "/Author": "Yaroslav Molkov et al.",
        "/Subject": "Reproduced vector panels; doi:10.7554/eLife.101959.4; CC0 1.0",
    })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    writer.write(OUTPUT)
    print(f"Prepared {OUTPUT.relative_to(ROOT)} from verified publisher artwork")


if __name__ == "__main__":
    main()
