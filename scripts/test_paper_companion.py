"""Checks that the two published pages are self-contained and in step with their sources."""
import base64
from html.parser import HTMLParser
import io
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

import matplotlib.image as image

from build_paper_companion import ROOT, render, stored_paper_url, text_of


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.sources = []
        self.stylesheets = []
        self.ids = set()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "link":
            if attrs.get("rel") == "stylesheet":
                self.stylesheets.append(attrs.get("href"))
        elif "href" in attrs:
            self.links.append(attrs["href"])
        if "src" in attrs:
            self.sources.append(attrs["src"])


class Homepage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = (ROOT/"index.html").read_text()
        cls.fresh = render(ROOT, stored_paper_url(ROOT))

    def test_committed_page_matches_its_sources(self):
        # Images are compared separately: PNG bytes can differ between machines.
        self.assertEqual(text_of(self.committed), text_of(self.fresh))

    def test_page_needs_no_other_file_to_display(self):
        page = Page(self.committed)
        self.assertEqual(page.stylesheets, [])
        self.assertNotIn("<script", self.committed)
        self.assertNotIn("{{", self.committed)
        self.assertIn("<style>", self.committed)
        self.assertEqual(len(page.sources), 4)
        for source in page.sources:
            self.assertTrue(source.startswith("data:image/"), source[:40])

    def test_embedded_figures_are_real_images(self):
        pictures = re.findall(r'src="data:image/png;base64,([^"]+)"', self.committed)
        self.assertEqual(len(pictures), 3)
        for encoded in pictures:
            pixels = image.imread(io.BytesIO(base64.b64decode(encoded)), format="png")
            self.assertGreater(pixels.shape[0], 300)
            self.assertGreater(pixels[..., :3].std(), .03)
        self.assertLess(self.committed.index("Figure 4A:"), self.committed.index("Schematic: cellular"))

    def test_every_link_leads_somewhere(self):
        page = Page(self.committed)
        for wanted in ("explorer/index.html", "explorer/index.html#guide",
                       "paper/supporting/Supporting_Data_S1.xlsx",
                       "https://github.com/ymolkov/resp-net-paper"):
            self.assertIn(wanted, page.links)
        for href in page.links:
            link = urlsplit(href)
            if link.scheme == "https":
                continue
            self.assertFalse(link.scheme or link.netloc or link.path.startswith("/"), href)
            if link.fragment and not link.path:
                self.assertIn(link.fragment, page.ids)
            if link.path:
                self.assertTrue((ROOT/link.path).is_file(), href)

    def test_paper_link_appears_only_with_a_public_address(self):
        without = render(ROOT)
        self.assertNotIn("Read the paper", without)
        url = "https://doi.org/10.1101/companion-test"
        with_link = render(ROOT, url)
        self.assertIn("Read the paper", with_link)
        self.assertIn(url, Page(with_link).links)
        for bad in ("file:///tmp/draft.pdf", "https://www.biorxiv.org/", "https://doi.org/about",
                    "https://doi.org.example/10.1101/test", "http://doi.org/10.1101/test"):
            with self.subTest(url=bad), self.assertRaisesRegex(ValueError, "HTTPS DOI"):
                render(ROOT, bad)
        stored = stored_paper_url(ROOT)
        self.assertEqual("Read the paper" in self.committed, stored is not None)


class Atlas(unittest.TestCase):
    def test_atlas_is_one_file_beside_the_homepage(self):
        atlas = (ROOT/"explorer/index.html").read_text()
        page = Page(atlas)
        self.assertIn("../index.html", page.links)
        self.assertEqual(page.stylesheets, [])
        self.assertFalse(re.search(r"<script[^>]+src=", atlas))
        self.assertFalse((ROOT/"apps/connectome-explorer/index.html").exists())

    def test_pages_are_served_as_they_are(self):
        self.assertTrue((ROOT/".nojekyll").is_file())
        self.assertFalse((ROOT/".github/workflows").exists())


if __name__ == "__main__":
    unittest.main()
