"""Check the DeepBuild website before publishing. Standard library only; makes no changes.

Run from the repository root:  python tools/check_site.py .   (add --base http://127.0.0.1:8080 to
also fetch every page from a local server, or --base https://deepbuild.tech after launch).

Checks: page structure and metadata, internal links, sitemap and robots, plus (audit 2026-10-09)
header/footer consistency, one contact address, sitemap covers every page, no external
scripts/styles/fonts/images, JSON-LD parses, security.txt valid, SVG assets inert, no secrets.

Usage:
  python check_site.py <site_dir>                           # files on disk
  python check_site.py <site_dir> --base <url>              # also fetch every page from a server
  python check_site.py <site_dir> --base <url> --validate   # also ask the W3C Nu checker (public URLs only)
Exit code 0 = no failures (warnings allowed), 1 = at least one failure.
"""
import argparse, json, pathlib, re, sys, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "deepbuild-site-check/1.0"}
fails, warns = [], []

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None; self.title = ""; self._in_title = False
        self.meta = {}; self.links = []; self.canonical = None
        self.headings = []; self.imgs_no_alt = 0; self.scripts = []; self.ids = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.add(a["id"])
        if tag == "html": self.lang = a.get("lang")
        elif tag == "title": self._in_title = True
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key: self.meta[key] = a.get("content", "")
        elif tag == "link":
            if a.get("rel") == "canonical": self.canonical = a.get("href")
            if a.get("href"): self.links.append(a["href"])
        elif tag == "a" and a.get("href"): self.links.append(a["href"])
        elif tag == "img":
            if "alt" not in a: self.imgs_no_alt += 1
            if a.get("src"): self.links.append(a["src"])
        elif tag == "script":
            self.scripts.append((a.get("type", "text/javascript"), a.get("src")))
            if a.get("src"): self.links.append(a["src"])
        elif re.fullmatch(r"h[1-6]", tag): self.headings.append(int(tag[1]))
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
    def handle_data(self, data):
        if self._in_title: self.title += data

def target_file(root, path):
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0])
    p = root / path.lstrip("/")
    if path.endswith("/") or p.is_dir(): p = p / "index.html"
    return p

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site"); ap.add_argument("--base"); ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()
    root = pathlib.Path(args.site).resolve()
    pages = sorted(p for p in root.rglob("*.html") if ".git" not in p.parts)
    titles, descs, external = {}, {}, set()
    for f in pages:
        rel = "/" + f.relative_to(root).as_posix().replace("index.html", "")
        is404 = f.name == "404.html"
        pg = Page(); pg.feed(f.read_text(encoding="utf-8"))
        raw = f.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"): fails.append(f"{rel}: file starts with a UTF-8 BOM")
        if not pg.lang: fails.append(f"{rel}: <html> has no lang")
        if not pg.title.strip(): fails.append(f"{rel}: empty <title>")
        if pg.headings.count(1) != 1: fails.append(f"{rel}: expected exactly one <h1>, found {pg.headings.count(1)}")
        for prev, cur in zip(pg.headings, pg.headings[1:]):
            if cur > prev + 1: fails.append(f"{rel}: heading jumps from h{prev} to h{cur}")
        if pg.imgs_no_alt: fails.append(f"{rel}: {pg.imgs_no_alt} <img> without alt")
        for t, s in pg.scripts:
            if t == "application/ld+json": continue
            if not s: fails.append(f"{rel}: inline executable <script> - CSP blocks it; use a file under /assets/")
            elif not s.startswith("/"): fails.append(f"{rel}: external script {s} - self-host it under /assets/vendor/")
        if "viewport" not in pg.meta: fails.append(f"{rel}: no viewport meta")
        if not is404:
            for k in ("description", "og:title", "og:description", "og:url", "og:type"):
                if not pg.meta.get(k): fails.append(f"{rel}: missing meta {k}")
            if not pg.canonical: fails.append(f"{rel}: no canonical")
            elif pg.canonical != "https://deepbuild.tech" + rel:
                fails.append(f"{rel}: canonical is {pg.canonical}, expected https://deepbuild.tech{rel}")
            if pg.meta.get("og:url") and pg.meta["og:url"] != pg.canonical:
                fails.append(f"{rel}: og:url differs from canonical")
            titles.setdefault(pg.title.strip(), []).append(rel)
            descs.setdefault(pg.meta.get("description", ""), []).append(rel)
            d = pg.meta.get("description", "")
            if not 50 <= len(d) <= 170: warns.append(f"{rel}: description is {len(d)} chars (aim 50-170)")
        for href in pg.links:
            if href.startswith(("mailto:", "tel:")): continue
            if href.startswith("http://"): fails.append(f"{rel}: insecure link {href}")
            elif href.startswith("https://"):
                if not href.startswith("https://deepbuild.tech"): external.add(href)
            elif href.startswith("#"):
                if href[1:] and href[1:] not in pg.ids: fails.append(f"{rel}: anchor {href} has no target")
            else:
                link = href if href.startswith("/") else urllib.parse.urljoin(rel, href)
                if not target_file(root, link).exists(): fails.append(f"{rel}: broken internal link {href}")
    for t, where in titles.items():
        if len(where) > 1: fails.append(f"duplicate <title> '{t}' on {where}")
    for d, where in descs.items():
        if len(where) > 1: fails.append(f"duplicate description on {where}")
    sm = root / "sitemap.xml"; locs = []
    if sm.exists():
        locs = re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8"))
        for loc in locs:
            path = urllib.parse.urlparse(loc).path
            if not loc.startswith("https://deepbuild.tech/"): fails.append(f"sitemap: {loc} is not on https://deepbuild.tech")
            if not target_file(root, path).exists(): fails.append(f"sitemap: {loc} has no file")
    else: fails.append("sitemap.xml missing")
    rb = root / "robots.txt"
    if not rb.exists() or "Sitemap: https://deepbuild.tech/sitemap.xml" not in rb.read_text(encoding="utf-8"):
        fails.append("robots.txt missing or has no Sitemap line")
    for name in ("404.html", "favicon.svg", ".nojekyll"):
        if not (root / name).exists(): fails.append(f"{name} missing")

    # ---- audit 2026-10-09 additions ------------------------------------------------------
    import datetime
    heads, foots, mails = set(), set(), set()
    in_sitemap = {urllib.parse.urlparse(l).path for l in locs}
    for f in pages:
        t = f.read_text(encoding="utf-8")
        rel = "/" + f.relative_to(root).as_posix().replace("index.html", "")
        h = re.search(r"<header.*?</header>", t, re.S); ft = re.search(r"<footer.*?</footer>", t, re.S)
        if not h or not ft: fails.append(f"{rel}: missing <header> or <footer>")
        else:
            heads.add(h.group(0).replace(' aria-current="page"', "")); foots.add(ft.group(0))
        mails.update(re.findall(r"mailto:([^\"'?]+)", t))
        if f.name != "404.html" and rel not in in_sitemap: fails.append(f"{rel}: page is not in sitemap.xml")
        for m in re.finditer(r'<(script|img|link|iframe|source)\b[^>]*\b(?:src|href)="(https?:)?//', t):
            tag = m.group(0)
            if 'rel="canonical"' not in tag: fails.append(f"{rel}: external resource loaded: {tag[:80]}")
        if re.search(r"lorem ipsum|REPLACE_ME|TODO|\[placeholder\]", t, re.I): fails.append(f"{rel}: placeholder text left in page")
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
        if ld:
            try: json.loads(ld.group(1))
            except Exception as e: fails.append(f"{rel}: JSON-LD does not parse: {e}")
    if len(heads) > 1: fails.append(f"header differs between pages ({len(heads)} variants)")
    if len(foots) > 1: fails.append(f"footer differs between pages ({len(foots)} variants)")
    if len(mails) != 1: fails.append(f"expected one contact address, found {sorted(mails)}")
    st = root / ".well-known" / "security.txt"
    if st.exists():
        s = st.read_text(encoding="utf-8"); m = re.search(r"^Expires: (\S+)", s, re.M)
        if "Contact:" not in s or not m: fails.append("security.txt needs Contact and Expires")
        elif datetime.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30):
            fails.append(f"security.txt expires soon or has expired ({m.group(1)})")
    else: warns.append("no .well-known/security.txt")
    for svg in root.rglob("*.svg"):
        if ".git" in svg.parts: continue
        s = svg.read_text(encoding="utf-8")
        if re.search(r"<script|<foreignObject|<image|xlink:href|\bhref=|\bon[a-z]+=", s, re.I):
            fails.append(f"{svg.relative_to(root)}: SVG contains script, embedded image or external reference")
    secret = re.compile(r"api[_-]?key|secret|token|passw|BEGIN [A-Z ]*PRIVATE KEY|@gmail\.com|\+91[\s-]?\d", re.I)
    for f in root.rglob("*"):
        if f.is_file() and ".git" not in f.parts and f.suffix in (".html", ".css", ".js", ".txt", ".xml", ".md", ".svg", ".json") and f.name != "check_site.py":
            if secret.search(f.read_text(encoding="utf-8", errors="ignore")): fails.append(f"{f.relative_to(root)}: matches a secret/personal-data pattern")
    print(f"Consistency: {len(heads)} header, {len(foots)} footer, contact {sorted(mails)}")
    print(f"Checked {len(pages)} HTML files and {len(locs)} sitemap URLs in {root}")
    if args.base:
        base = args.base.rstrip("/")
        for loc in locs:
            path = urllib.parse.urlparse(loc).path
            code, body = fetch(base + path)
            print(f"  GET {base + path} -> {code}")
            if code != 200: fails.append(f"live: {base + path} returned {code}")
            if args.validate and code == 200:
                vurl = "https://validator.w3.org/nu/?out=json&doc=" + urllib.parse.quote(base + path, safe="")
                vcode, vbody = fetch(vurl)
                try:
                    msgs = json.loads(vbody).get("messages", [])
                    errs = [m for m in msgs if m.get("type") == "error"]
                    print(f"    W3C: {len(errs)} errors, {len(msgs) - len(errs)} other messages")
                    for m in errs: fails.append(f"W3C {path}: {m.get('message')}")
                except Exception:
                    warns.append(f"W3C check for {path} did not return JSON (HTTP {vcode})")
        code, _ = fetch(base + "/this-page-does-not-exist-deepbuild-check/")
        print(f"  GET {base}/this-page-does-not-exist-deepbuild-check/ -> {code}")
        if code != 404: fails.append(f"live: unknown path returned {code}, expected 404")
        for href in sorted(external):
            code, _ = fetch(href)
            print(f"  external {href} -> {code}")
            if code is None or code >= 400: warns.append(f"external link {href} returned {code}")
    for w in warns: print("WARN ", w)
    for f in fails: print("FAIL ", f)
    print(f"Result: {len(fails)} failures, {len(warns)} warnings")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
