"""Exercise the blog's generated output with disposable Markdown fixtures.

Run with: python3 -m unittest discover -s tests -v
Set HUGO_BIN to use an alternative Hugo executable.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


ROOT = Path(__file__).resolve().parents[1]
HUGO = os.environ.get("HUGO_BIN") or shutil.which("hugo") or str(ROOT / ".tools/hugo")
ORIGIN = "https://example.org/journal/"


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.links = []
        self.ids = set()
        self.meta = {}
        self.canonical = None
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "meta":
            self.meta[attrs.get("name", attrs.get("property"))] = attrs.get("content")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag in ("link", "img", "script"):
            target = attrs.get("src", attrs.get("href"))
            if target:
                self.links.append(target)


def copy_source(destination):
    def omit_authored_posts(directory, names):
        if Path(directory) == ROOT / "content/writing":
            return [name for name in names if name != "_index.md"]
        return []

    for name in ("hugo.toml", "content", "layouts", "assets", "static", "archetypes"):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, destination / name, ignore=omit_authored_posts)
        elif source.is_file():
            shutil.copy2(source, destination / name)


def write_post(source, slug, title, date, tags=(), draft=False):
    directory = source / "content/writing"
    directory.mkdir(parents=True, exist_ok=True)
    metadata = {"title": title, "tags": list(tags), "draft": draft}
    if date is not None:
        metadata["date"] = date
    body = '\n\nA paragraph with **emphasis** and a [link](/about/).\n\n```rust\nfn main() {}\n```\n'
    (directory / f"{slug}.md").write_text(json.dumps(metadata) + body)


def build(source, output, *flags):
    return subprocess.run(
        [HUGO, "--source", str(source), "--destination", str(output),
         "--baseURL", ORIGIN, "--clock", "2026-09-08T12:00:00-03:00",
         "--panicOnWarning", *flags],
        capture_output=True, text=True,
    )


class BlogOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="personal-blog-tests-")
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source"
        cls.source.mkdir()
        copy_source(cls.source)
        write_post(cls.source, "older", "Older essay", "2026-01-01", ["life", "philosophy"])
        write_post(cls.source, "newer", "Newer essay", "2026-02-01", ["life"])
        write_post(cls.source, "untagged", "An untagged essay", "2026-03-01")
        write_post(cls.source, "private-draft", "Unpublished draft", "2026-04-01", ["draft-only"], True)
        write_post(cls.source, "future", "Future essay", "2099-01-01", ["future-only"])
        cls.output = cls.root / "production"
        cls.result = build(cls.source, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def page(self, path):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        file = self.output / path
        self.assertTrue(file.exists(), f"Missing generated page: {path}")
        return file.read_text()

    def test_archive_lists_only_published_writing_newest_first(self):
        doc = Document(self.page("writing/index.html"))
        posts = [url for url in doc.links if url.startswith("/journal/writing/") and url != "/journal/writing/"]
        self.assertEqual(posts, ["/journal/writing/untagged/", "/journal/writing/newer/", "/journal/writing/older/"])

    def test_tag_links_and_archives_follow_post_membership(self):
        links = Document(self.page("writing/older/index.html")).links
        self.assertIn("/journal/tags/life/", links)
        self.assertIn("/journal/tags/philosophy/", links)
        tagged = Document(self.page("tags/life/index.html"))
        posts = [url for url in tagged.links if url.startswith("/journal/writing/") and url != "/journal/writing/"]
        self.assertEqual(posts, ["/journal/writing/newer/", "/journal/writing/older/"])
        index = self.page("tags/index.html")
        self.assertIn('>life</a>', index)
        self.assertIn('>philosophy</a>', index)
        self.assertIn('<span>2 posts</span>', index)
        self.assertNotIn("draft-only", index)
        self.assertNotIn("future-only", index)

    def test_untagged_post_has_no_tag_metadata(self):
        source = self.page("writing/untagged/index.html")
        self.assertNotIn('class="post-tags"', source)
        self.assertIn("An untagged essay", source)

    def test_rss_contains_only_published_writing(self):
        feed = ET.fromstring(self.page("index.xml"))
        self.assertEqual([item.findtext("title") for item in feed.findall("./channel/item")],
                         ["An untagged essay", "Newer essay", "Older essay"])
        self.assertEqual(feed.findtext("./channel/item/link"), ORIGIN + "writing/untagged/")

    def test_drafts_and_future_posts_leave_no_production_artifacts(self):
        self.page("index.html")
        for route in ("writing/private-draft", "writing/future", "tags/draft-only", "tags/future-only"):
            self.assertFalse((self.output / route).exists(), route)
        sitemap = self.page("sitemap.xml")
        self.assertNotIn("private-draft", sitemap)
        self.assertNotIn("future", sitemap)

    def test_preview_includes_drafts_but_not_future_posts(self):
        self.page("index.html")
        preview = self.root / "preview"
        result = build(self.source, preview, "--buildDrafts")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((preview / "writing/private-draft/index.html").exists())
        self.assertTrue((preview / "tags/draft-only/index.html").exists())
        self.assertFalse((preview / "writing/future/index.html").exists())

    def test_posts_have_specific_metadata_and_rendered_markdown(self):
        source = self.page("writing/older/index.html")
        doc = Document(source)
        self.assertEqual(doc.canonical, ORIGIN + "writing/older/")
        self.assertIn("Older essay", doc.meta["og:title"])
        self.assertTrue(doc.meta["description"])
        self.assertEqual(doc.meta["og:type"], "article")
        self.assertIn("<strong>emphasis</strong>", source)
        self.assertIn('class="highlight"', source)

    def test_generated_internal_links_resolve_with_a_host_subpath(self):
        self.page("index.html")
        for file in self.output.rglob("*.html"):
            doc = Document(file.read_text())
            for link in doc.links:
                url = urlsplit(link)
                if url.scheme and url.scheme not in ("http", "https"):
                    continue
                if url.netloc and url.netloc != "example.org":
                    continue
                if not url.path:
                    if url.fragment:
                        self.assertIn(unquote(url.fragment), doc.ids, f"{file}: {link}")
                    continue
                self.assertTrue(url.path.startswith("/journal/"), f"Not portable: {file}: {link}")
                destination = self.output / unquote(url.path.removeprefix("/journal/"))
                if destination.is_dir():
                    destination /= "index.html"
                self.assertTrue(destination.is_file(), f"Broken link: {file}: {link}")

    def test_empty_site_has_usable_archives_and_preserves_about(self):
        source = self.root / "empty-source"
        source.mkdir()
        copy_source(source)
        output = self.root / "empty-output"
        result = build(source, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in ("index.html", "writing/index.html", "tags/index.html", "about/index.html", "404.html"):
            self.assertTrue((output / path).is_file(), path)
        self.assertIn("No posts yet", (output / "writing/index.html").read_text())
        about = (output / "about/index.html").read_text()
        for fact in ("mooze", "tivit", "mosten", "$5M ARR", "h4vismat@pm.me", "3A2E9BF5637F81A2402162FBF118DA633E261857"):
            self.assertIn(fact, about)
        self.assertEqual(ET.parse(output / "index.xml").findall("./channel/item"), [])

    def test_invalid_published_post_metadata_fails_build(self):
        self.page("index.html")
        for slug, title, date in (("missing-title", "", "2026-01-01"), ("missing-date", "A title", None)):
            with self.subTest(slug=slug):
                source = self.root / slug
                source.mkdir()
                copy_source(source)
                write_post(source, slug, title, date)
                result = build(source, self.root / (slug + "-output"))
                self.assertNotEqual(result.returncode, 0, "Invalid post should fail the build")
                self.assertIn(slug, result.stdout + result.stderr)

    def test_production_rebuild_removes_withdrawn_posts(self):
        source = self.root / "withdrawal-source"
        source.mkdir()
        copy_source(source)
        output = self.root / "withdrawal-output"
        write_post(source, "withdrawn", "An essay", "2026-01-01", ["withdrawn-tag"])
        result = build(source, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((output / "writing/withdrawn/index.html").is_file())
        write_post(source, "withdrawn", "An essay", "2026-01-01", ["withdrawn-tag"], True)
        result = build(source, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((output / "writing/withdrawn/index.html").exists())
        self.assertFalse((output / "tags/withdrawn-tag/index.html").exists())

    def test_rss_preserves_punctuation_without_invalid_xml(self):
        source = self.root / "punctuation-source"
        source.mkdir()
        copy_source(source)
        output = self.root / "punctuation-output"
        write_post(source, "punctuation", 'Tea & <thoughts> "today"', "2026-01-01", ["art & life"])
        result = build(source, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        item = ET.parse(output / "index.xml").find("./channel/item")
        self.assertEqual(item.findtext("title"), 'Tea & <thoughts> "today"')
        self.assertEqual(item.findtext("category"), "art & life")
        self.assertIn("<strong>emphasis</strong>", item.findtext("description"))


if __name__ == "__main__":
    unittest.main()
