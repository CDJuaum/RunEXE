import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "website"


def _read(name: str) -> str:
    return (SITE / name).read_text(encoding="utf-8")


def test_homepage_exposes_search_and_social_metadata():
    html = _read("index.html")

    assert '<link rel="canonical" href="https://runexe.rrmtools.uk/">' in html
    assert 'name="robots" content="index,follow,max-image-preview:large' in html
    assert 'property="og:title"' in html
    assert 'property="og:image"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert "run windows exe apps on linux" in html.lower()


def test_homepage_software_application_schema_matches_release():
    html = _read("index.html")
    match = re.search(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        html,
        re.DOTALL,
    )
    assert match is not None

    data = json.loads(match.group(1))
    app = next(item for item in data["@graph"] if item["@type"] == "SoftwareApplication")

    assert app["name"] == "RunEXE"
    assert app["softwareVersion"] == "1.1.0"
    assert app["operatingSystem"] == "Linux"
    assert app["applicationCategory"] == "UtilitiesApplication"
    assert app["offers"]["price"] == "0"
    assert app["downloadUrl"].endswith("/releases/latest")


def test_indexable_pages_use_canonical_clean_urls_and_sitemap():
    guide = _read("guide.html")
    privacy = _read("privacy.html")

    assert '<link rel="canonical" href="https://runexe.rrmtools.uk/guide">' in guide
    assert 'name="robots" content="index,follow,max-image-preview:large' in guide
    assert '"@type": "TechArticle"' in guide
    assert 'name="robots" content="noindex,follow"' in privacy

    tree = ET.parse(SITE / "sitemap.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in tree.findall("s:url/s:loc", ns)]
    assert urls == ["https://runexe.rrmtools.uk/", "https://runexe.rrmtools.uk/guide"]
