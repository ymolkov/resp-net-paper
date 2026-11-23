"""Build the self-contained GitHub Pages artifact from the paper-only checkout."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EXPLORER = "apps/connectome-explorer"
COPIES = {
    "companion/companion.css": "assets/companion.css",
    EXPLORER + "/vendor/lucide/scan.svg": "assets/scan.svg",
    "paper/figures/inference_overview.pdf": "assets/figure-1.pdf",
    "paper/figures/expanded_circuit.pdf": "assets/figure-4.pdf",
    "paper/supporting/Supporting_Data_S1.xlsx": "downloads/Supporting_Data_S1.xlsx",
    **{p: p for p in ("LICENSE", "LICENSE-DATA.md", "THIRD_PARTY_NOTICES.md",
                       *(f"{EXPLORER}/vendor/{v}/LICENSE" for v in ("lucide", "d3")))},
}


def conductance_image(root, target):
    data = root / "data/model_analyses/coarse_connection_contrasts"
    cells = json.loads((data / "cells.json").read_text())["fixed_fall50"]
    basis = json.loads((data / "contrasts.json").read_text())["fixed_fall50"][0]
    profiles = np.asarray([c["profiles"] for c in cells if c["phenotype"] == "pre-I"])
    assert profiles.shape == (17, 2, 100)
    mean = profiles.mean(axis=0)
    offset = basis["ti"]
    fig, ax = plt.subplots(figsize=(4.4, 2.2), dpi=200)
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    fig.subplots_adjust(left=.1, right=.965, bottom=.22, top=.82)
    ax.axvspan(0, offset, color="#c1d9d4", alpha=.22)
    ax.axvline(offset, color="#658280", lw=.8, linestyle=":")
    for a, b, label in ((0, offset, "Inspiration"), (offset, 1, "Expiration")):
        ax.text((a+b)/2, 1.08, label, transform=ax.transAxes, ha="center", size=10, color="#324e50")
    x = np.arange(100) / 100
    ax.plot(x, mean[0], color="#b83e3d", lw=2.1)
    ax.plot(x, mean[1], color="#287ba5", lw=2.1, linestyle="--")
    ax.set(xlim=(0, 1), ylim=(0, 1), xticks=(0,.5,1), yticks=(0,.5,1))
    ax.set_xticklabels(("0", "Cycle phase", "1"))
    ax.set_yticklabels(("0", "0.5", "1"))
    ax.grid(axis="y", color="#d1dfdc", linewidth=.55)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=4, labelsize=9, colors="#40595b")
    fig.savefig(target, transparent=True)
    plt.close(fig)


def build(root, dest, paper_url=None, preview_pdf=None):
    if (paper_url is None) == (preview_pdf is None):
        raise ValueError("Choose either a public paper URL or a local preview PDF")
    if preview_pdf is None:
        url = urlsplit(paper_url)
        doi = r"/10\.[0-9]{4,9}/[^\s/]+(?:/[^\s/]+)*"
        valid_article = ((url.netloc == "doi.org" and re.fullmatch(doi, url.path)) or
                         (url.netloc in {"www.biorxiv.org", "biorxiv.org"}
                          and re.fullmatch("/content" + doi, url.path)))
        if url.scheme != "https" or not valid_article:
            raise ValueError("Use the paper's HTTPS DOI or bioRxiv article URL")
    else:
        with preview_pdf.open("rb") as f:
            if f.read(5) != b"%PDF-":
                raise ValueError("Preview requires a local manuscript PDF")
        paper_url = "downloads/manuscript-preview.pdf"
    if dest.resolve() == root.resolve() or root.resolve() in dest.resolve().parents:
        raise ValueError("Build the site outside the release checkout")
    allowed = set(COPIES.values()) | {"index.html", "explorer/index.html", "assets/conductance.png",
                                     "assets/figure-1.png", "assets/figure-4a.png"}
    if preview_pdf is not None:
        allowed.add(paper_url)
    if dest.exists():
        # Never package leftover files (in particular, a preview manuscript).
        for p in dest.rglob("*"):
            if p.is_symlink() or (p.is_file() and p.relative_to(dest).as_posix() not in allowed):
                raise ValueError(f"Unexpected file in site output: {p}")
    for src, dst in COPIES.items():
        path = dest / dst
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / src, path)
    if preview_pdf is not None:
        shutil.copyfile(preview_pdf, dest / paper_url)
    subprocess.run(["pdftocairo", "-png", "-singlefile", "-scale-to", "1450",
                    dest/"assets/figure-1.pdf", dest/"assets/figure-1"], check=True)
    # Published panel A between its header and the shared legend, in PDF points
    # from the top-left. Crop the original artwork, preserving all routes and widths.
    box = (6, 23, 249, 150)
    crop = [v for flag, pt in zip(("-x", "-y", "-W", "-H"), box) for v in (flag, str(6*pt))]
    subprocess.run(["pdftocairo", "-png", "-singlefile", "-r", "432", *crop,
                    dest/"assets/figure-4.pdf", dest/"assets/figure-4a"], check=True)
    conductance_image(root, dest/"assets/conductance.png")
    atlas = (root/EXPLORER/"index.html").read_text()
    brand = '<div class="brand">resp-net <span>Circuit atlas</span></div>'
    if atlas.count(brand) != 1:
        raise ValueError("Atlas masthead changed; check the companion return link")
    atlas = atlas.replace(brand, '<div class="brand"><a href="../index.html" style="color:inherit" '
                          'aria-label="Return to the paper companion">resp-net</a> <span>Circuit atlas</span></div>')
    (dest/"explorer").mkdir(exist_ok=True)
    (dest/"explorer/index.html").write_text(atlas)
    page = (root/"companion/index.html").read_text().replace("{{PAPER_URL}}", html.escape(paper_url, quote=True))
    page = page.replace("{{EXPLORER}}", "explorer/index.html" if preview_pdf is not None else "explorer/")
    (dest/"index.html").write_text(page)
    print(f"Built {'private preview' if preview_pdf else 'public-link artifact'}: {dest/'index.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--paper-url", help="Published preprint or paper DOI URL")
    mode.add_argument("--preview-pdf", type=Path, help="For local review only; never deploy this output")
    args = parser.parse_args()
    build(ROOT, args.output, args.paper_url, args.preview_pdf)
