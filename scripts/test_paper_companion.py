"""Integration checks for the private preview and the GitHub Pages artifact."""
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

import matplotlib.image as image

from build_paper_companion import ROOT, build


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.links = []
        self.ids = set()
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.links.append(attrs[key])


class Companion(unittest.TestCase):
    def test_preview_and_public_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pdf = base / "test-only.pdf"
            pdf.write_bytes(b"%PDF-1.4\nTest fixture, not a paper.")
            url = "https://doi.org/10.1101/companion-test"
            for preview in (True, False):
                with self.subTest(preview=preview):
                    site = base / ("preview" if preview else "public") / "resp-net-paper"
                    build(ROOT, site, preview_pdf=pdf if preview else None,
                          paper_url=None if preview else url)
                    home = site / "index.html"
                    self.assertNotIn("{{", home.read_text())
                    page = Page(home)
                    self.assertIn("explorer/index.html" if preview else "explorer/", page.links)
                    self.assertIn("downloads/manuscript-preview.pdf" if preview else url, page.links)
                    for href in page.links:
                        link = urlsplit(href)
                        if link.scheme == "https":
                            continue
                        self.assertFalse(link.scheme or link.netloc or link.path.startswith("/"), href)
                        if link.fragment and not link.path:
                            self.assertIn(link.fragment, page.ids)
                        if link.path:
                            p = site / link.path
                            self.assertTrue((p/"index.html" if p.is_dir() else p).is_file(), href)
                    self.assertIn("../index.html", Page(site/"explorer/index.html").links)
                    manuscript = site/"downloads/manuscript-preview.pdf"
                    self.assertEqual(manuscript.exists(), preview)
                    if preview:
                        self.assertEqual(manuscript.read_bytes(), pdf.read_bytes())
                        with self.assertRaisesRegex(ValueError, "Unexpected file"):
                            build(ROOT, site, paper_url=url)
                    else:
                        self.assertEqual(set(site.rglob("*.pdf")), {site/"assets/figure-1.pdf", site/"assets/figure-4.pdf"})
                    for src, dest in (("paper/figures/inference_overview.pdf", "assets/figure-1.pdf"),
                                      ("paper/figures/expanded_circuit.pdf", "assets/figure-4.pdf"),
                                      ("paper/supporting/Supporting_Data_S1.xlsx", "downloads/Supporting_Data_S1.xlsx")):
                        self.assertEqual((ROOT/src).read_bytes(), (site/dest).read_bytes())
                    self.assertLess(page.links.index("assets/figure-4a.png"), page.links.index("assets/figure-1.png"))
                    for name in ("figure-1", "figure-4a", "conductance"):
                        pixels = image.imread(site/f"assets/{name}.png")
                        self.assertGreater(pixels.shape[0], 300)
                        self.assertGreater(pixels[..., :3].std(), .03)

    def test_preprint_pending_shares_public_data_but_no_manuscript(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            build(ROOT, site, preprint_pending=True)
            page = (site/"index.html").read_text()
            for unavailable in ("overleaf.com", "manuscript-preview", "{{", "Read the paper"):
                self.assertNotIn(unavailable, page)
            self.assertFalse(list(site.rglob("*.pdf")))
            links = Page(site/"index.html").links
            self.assertIn("https://github.com/ymolkov/resp-net-paper", links)
            workbook = "downloads/Supporting_Data_S1.xlsx"
            self.assertIn(workbook, links)
            self.assertEqual((site/workbook).read_bytes(), (ROOT/"paper/supporting/Supporting_Data_S1.xlsx").read_bytes())
            self.assertTrue((site/"explorer/index.html").is_file())
            self.assertIn("explorer/index.html", Page(site/"index.html").links)
            (site/"draft.pdf").touch()
            with self.assertRaisesRegex(ValueError, "Unexpected file"):
                build(ROOT, site, preprint_pending=True)

    def test_requires_public_article_or_private_pdf(self):
        for url in (None, "file:///tmp/draft.pdf", "https://www.biorxiv.org/", "https://doi.org/about",
                    "https://doi.org.example/10.1101/test", "http://doi.org/10.1101/test"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "paper URL|HTTPS DOI"):
                build(ROOT, ROOT, paper_url=url)
        with self.assertRaisesRegex(ValueError, "outside the release checkout"):
            build(ROOT, ROOT, paper_url="https://www.biorxiv.org/content/10.1101/testv1")


if __name__ == "__main__":
    unittest.main()
