"""Write the study homepage as one self-contained file at the repository root.

The page is generated from `companion/index.html` and `companion/companion.css`.
Its three images are made from the packaged figures and data and embedded in
the page, so `index.html` needs no other file to display. GitHub Pages serves
it, and the atlas beside it at `explorer/index.html`, straight from `main`.

No inference is run. The paper's public address is read from
`companion/paper_url.txt`; while that file has no address, the page carries no
paper link.
"""
import argparse
import base64
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = "companion/index.html"
STYLE = "companion/companion.css"
PAPER_URL = "companion/paper_url.txt"
ICON = "apps/connectome-explorer/vendor/lucide/scan.svg"
IMAGES = ("figure-4a", "figure-1", "conductance")
EMBEDDED = re.compile(r"data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+")


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
    fig.savefig(target, transparent=True, metadata={"Software": None})
    plt.close(fig)


def stored_paper_url(root):
    """The first line of companion/paper_url.txt that is not blank or a comment."""
    for line in (root / PAPER_URL).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def check_paper_url(paper_url):
    url = urlsplit(paper_url)
    doi = r"/10\.[0-9]{4,9}/[^\s/]+(?:/[^\s/]+)*"
    valid_article = ((url.netloc == "doi.org" and re.fullmatch(doi, url.path)) or
                     (url.netloc in {"www.biorxiv.org", "biorxiv.org"}
                      and re.fullmatch("/content" + doi, url.path)))
    if url.scheme != "https" or not valid_article:
        raise ValueError("Use the paper's HTTPS DOI or bioRxiv article URL")


def make_images(root, folder):
    """Figure 4A, Figure 1 and the pre-I/I conductance plot as PNG bytes."""
    subprocess.run(["pdftocairo", "-png", "-singlefile", "-scale-to", "1450",
                    root/"paper/figures/inference_overview.pdf", folder/"figure-1"], check=True)
    # Published panel A between its header and the shared legend, in PDF points
    # from the top-left. Crop the original artwork, preserving all routes and widths.
    box = (6, 23, 249, 150)
    crop = [v for flag, pt in zip(("-x", "-y", "-W", "-H"), box) for v in (flag, str(6*pt))]
    subprocess.run(["pdftocairo", "-png", "-singlefile", "-r", "432", *crop,
                    root/"paper/figures/expanded_circuit.pdf", folder/"figure-4a"], check=True)
    conductance_image(root, folder/"conductance.png")
    return {name: (folder/f"{name}.png").read_bytes() for name in IMAGES}


def data_uri(content, mime):
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def render(root, paper_url=None):
    """Return the homepage with its stylesheet, icon and images embedded."""
    if paper_url is not None:
        check_paper_url(paper_url)
    page = (root/TEMPLATE).read_text()
    page = re.sub(r"<!-- paper-link -->(.*?)<!-- /paper-link -->",
                  lambda m: m[1] if paper_url else "", page, flags=re.S)
    page = page.replace("{{PAPER_URL}}", html.escape(paper_url or "", quote=True))
    with tempfile.TemporaryDirectory() as tmp:
        images = make_images(root, Path(tmp))
    embedded = {f'src="assets/{name}.png"': f'src="{data_uri(content, "image/png")}"'
                for name, content in images.items()}
    embedded['src="assets/scan.svg"'] = f'src="{data_uri((root/ICON).read_bytes(), "image/svg+xml")}"'
    embedded['<link rel="stylesheet" href="assets/companion.css">'] = (
        f"<style>\n{(root/STYLE).read_text()}</style>")
    for reference, replacement in embedded.items():
        if page.count(reference) != 1:
            raise ValueError(f"Homepage template changed; expected one {reference}")
        page = page.replace(reference, replacement)
    if "{{" in page or "assets/" in page:
        raise ValueError("Homepage still refers to a separate asset or placeholder")
    return page


def text_of(page):
    """The page with embedded images blanked, for comparing its wording and links."""
    return EMBEDDED.sub("data:embedded", page)


def build(root, paper_url=None):
    paper_url = paper_url or stored_paper_url(root)
    (root/"index.html").write_text(render(root, paper_url))
    mode = f"linking {paper_url}" if paper_url else "without a paper link"
    print(f"Wrote {root/'index.html'} ({(root/'index.html').stat().st_size:,} bytes), {mode}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--paper-url", help="Override the address stored in companion/paper_url.txt")
    build(ROOT, parser.parse_args().paper_url)
