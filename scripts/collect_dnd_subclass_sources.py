"""Collect public source pages for review; fetching is not rule verification."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/tmp/trpg-subclass-source-cache")
BOOKS = {"phb2014": "玩家手册", "scag": "剑湾冒险者指南",
         "xgte": "珊娜萨的万事指南", "tcoe": "塔莎的万事坩埚", "phb2024": "玩家手册2024"}
CLASSES = {"artificer": "奇械师", "barbarian": "野蛮人", "bard": "吟游诗人",
           "cleric": "牧师", "druid": "德鲁伊", "fighter": "战士", "monk": "武僧",
           "paladin": "圣武士", "ranger": "游侠", "rogue": "游荡者", "sorcerer": "术士",
           "warlock": "邪术师", "wizard": "法师"}


def matches_class(path, source, class_id):
    parent, filename = path.rsplit("/", 2)[-2:]
    names = [CLASSES[class_id]]
    if class_id == "warlock":
        names.append("魔契师")
    if source == "scag" and class_id == "wizard" and filename == "过时内容-剑咏.htm":
        return True
    return any(parent == name or parent.startswith(name + "（") or parent.startswith(name + "(")
               or (source == "scag" and filename.startswith(name + "-")) for name in names)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.parts = []
        self.anchor = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "a":
            self.anchor = [dict(attrs).get("href", ""), []]
        if tag in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "a" and self.anchor is not None:
            self.links.append((self.anchor[0], "".join(self.anchor[1]).strip()))
            self.anchor = None
        if tag in {"p", "div", "h1", "h2", "h3", "h4", "h5", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.anchor is not None:
                self.anchor[1].append(data)

    def text(self):
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def fetch(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = sha256(url.encode()).hexdigest()
    raw_path, text_path = CACHE / (key + ".html"), CACHE / (key + ".txt")
    if raw_path.exists():
        raw = raw_path.read_bytes()
    else:
        encoded = urllib.parse.quote(url, safe=":/?=&%#")
        request = urllib.request.Request(encoded, headers={"User-Agent": "TRPG-resource-review/1.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
        raw_path.write_bytes(raw)
    parser = PageParser()
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = raw.decode("gb18030")
    parser.feed(decoded)
    text_path.write_text(parser.text(), encoding="utf-8")
    return parser, text_path, sha256(raw).hexdigest()


def collect(book_filter=None):
    pages = {}
    for version in ("5E", "5R"):
        if book_filter and (version == "5R") != (book_filter == "phb2024"):
            continue
        index = f"https://dndlogs.com/{version}/webhelpcontents.htm"
        try:
            parser, _, _ = fetch(index)
        except Exception as exc:
            print(f"Index unavailable: {index}: {exc}", flush=True)
            continue
        for href, label in parser.links:
            url = urllib.parse.unquote(urllib.parse.urljoin(index, href).split("#")[0])
            path = urllib.parse.urlparse(url).path
            for source, book in BOOKS.items():
                if book_filter and source != book_filter:
                    continue
                if f"/topics/{book}/" not in path:
                    continue
                for class_id in CLASSES:
                    if matches_class(path, source, class_id):
                        pages[url] = {"url": url, "label": label, "source": source, "class_id": class_id}
    def read(record):
        try:
            parser, path, digest = fetch(record["url"])
            return {**record, "fetch_status": "ok", "cache_text": str(path),
                    "sha256": digest, "characters": len(parser.text())}
        except Exception as exc:
            return {**record, "fetch_status": "failed", "error": str(exc)}
    output = CACHE / "index.json"
    records = {row["url"]: row for row in json.loads(output.read_text())} if output.exists() else {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(read, record) for record in pages.values()]
        for future in as_completed(futures):
            record = future.result()
            records[record["url"]] = record
            output.write_text(json.dumps(list(records.values()), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{record['fetch_status']}: {record['source']} {record['label']}", flush=True)
    print(f"Collected {len(records)} candidate pages; {sum(r['fetch_status']=='ok' for r in records.values())} fetched; index: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", choices=BOOKS)
    args = parser.parse_args()
    collect(args.book)
