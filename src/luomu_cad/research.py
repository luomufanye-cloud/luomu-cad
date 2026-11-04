"""Bounded public reference collection and evidence-based Skill knowledge updates.

Remote pages are data, never executable instructions. No login automation,
challenge solving, arbitrary hosts, bulk image mirroring or numeric design rules.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import sqlite3
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from lxml import etree
from protego import Protego
from scrapling import Selector

from .research_sources import SOURCES, DISCIPLINES, DRAWING_TYPES, get_source
from .storage import ROOT, atomic_json, digest, now, workspace_lock

UA = "LuomuCADResearch/0.1 (+personal reference indexing; no model-weight training)"
MAX_BYTES = 2_500_000
STATUS_RETRY = {"ok": 7 * 86400, "blocked": 86400, "robots_denied": 86400,
                "robots_unavailable": 6 * 3600, "error": 3600, "asset_link": 30 * 86400}


def canonical_url(url):
    p = urlsplit(str(url).strip())
    if p.scheme not in {"https", "http"} or not p.hostname or p.username or p.password or p.port not in {None, 80, 443}:
        raise ValueError("Only public HTTP(S) URLs without credentials or custom ports are supported")
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid", "token", "auth", "key", "signature"}]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", urlencode(sorted(query)), ""))


def validate_url(url, *, resolve=True):
    url = canonical_url(url)
    source = get_source(url)
    if source is None:
        raise ValueError("SOURCE_NOT_APPROVED: add and review a source registry entry first")
    if not source["active"]:
        raise ValueError("SOURCE_SESSION_REQUIRED: this platform is catalogued for assisted search or authorized login, not automatic scraping")
    host = urlsplit(url).hostname
    if resolve:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Private or local network destinations are not permitted")
    return url, source


def classify(text, categories):
    lower = text.lower().replace("_", " ").replace("-", " ")
    found = [key for key, words in categories.items() if any(w.lower().replace("-", " ") in lower for w in words)]
    if categories is DRAWING_TYPES and re.search(r"\bsections?\b", lower):
        found.append("section")
    return list(dict.fromkeys(found))


def clean_text(value, limit=400):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def parse_page(url, html, source):
    """Scrapling extracts labels, figure URLs and document links, not measurements."""
    page = Selector(content=html, url=url, adaptive=False, huge_tree=False)
    title = clean_text(page.css("h1::text").get() or page.css("title::text").get(), 300)
    content = page
    for selector in (".shortcolumn", ".entry-content", ".post-content", "#mw-content-text", "article", "main", "#content"):
        selected = page.css(selector)
        if selected:
            content = selected[0]
            break
    if source["id"] == "landezine":
        # Current Landezine galleries use image anchors outside article cards.
        content = page
    text = clean_text(content.get_all_text(separator=" ", strip=True), 100000)
    disciplines = sorted(set(source["disciplines"] + classify(title + " " + text[:6000], DISCIPLINES)))
    images, seen = [], set()
    for img in content.css("img"):
        width = img.attrib.get("width", "")
        if width.isdigit() and int(width) < 80:
            continue
        raw = img.attrib.get("data-src") or img.attrib.get("data-original") or img.attrib.get("src")
        if not raw or raw.startswith(("data:", "javascript:")):
            continue
        try:
            image_url = canonical_url(urljoin(url, raw))
        except ValueError:
            continue
        if image_url in seen or any(w in urlsplit(image_url).path.lower() for w in ("logo", "avatar", "banner-ad", "pixel.gif")):
            continue
        caption = " ".join(img.xpath("ancestor::figure[1]//figcaption//text()").getall())
        if not caption:
            caption = " ".join(img.xpath("preceding-sibling::p[1]//text()").getall())
        if not caption and source["id"] == "gooood":
            caption = " ".join(img.xpath("preceding::p[1]//text()").getall())
        caption = clean_text(caption or img.attrib.get("alt") or img.attrib.get("title"), 300)
        types = classify(caption + " " + urlsplit(image_url).path, DRAWING_TYPES)
        seen.add(image_url)
        images.append({"url": image_url, "caption": caption, "drawing_types": types,
                       "verification": "caption_only" if types else "needs_visual_review", "downloaded": False})
        if len(images) >= 120:
            break
    for anchor in content.css("a[href]"):
        raw = anchor.attrib.get("href", "")
        if not re.search(r"\.(?:jpg|jpeg|png|webp|svg)(?:$|\?)", raw, re.I):
            continue
        if source["id"] == "landezine" and "rl-gallery-link" not in anchor.attrib.get("class", ""):
            continue
        try:
            target = canonical_url(urljoin(url, raw))
        except ValueError:
            continue
        if target in seen:
            continue
        caption = clean_text(anchor.attrib.get("data-rl_title") or anchor.attrib.get("title") or anchor.get_all_text(), 300)
        types = classify(caption + " " + urlsplit(target).path, DRAWING_TYPES)
        seen.add(target)
        images.append({"url": target, "caption": caption, "drawing_types": types,
                       "verification": "caption_only" if types else "needs_visual_review", "downloaded": False})
        if len(images) >= 160:
            break
    documents = []
    for link in content.css("a[href]"):
        raw = link.attrib.get("href", "")
        try:
            target = canonical_url(urljoin(url, raw))
        except ValueError:
            continue
        if re.search(r"\.(pdf|dwg|dxf|dwt|ifc|rvt)(?:$|\?)", target, re.I):
            documents.append({"url": target, "title": clean_text(link.get_all_text(), 160),
                              "format": urlsplit(target).path.rsplit(".", 1)[-1].lower(), "downloaded": False})
    image_types = {kind for image in images for kind in image["drawing_types"]}
    types = sorted(image_types | set(classify(title + " " + text[:10000], DRAWING_TYPES)))
    # Only a short reference excerpt is retained; no wholesale article text.
    record = {"url": url, "title": title or urlsplit(url).path, "source_id": source["id"],
              "publisher": source["name"], "authority": source["authority"], "disciplines": disciplines,
              "drawing_types": types, "images": images, "documents": list({d["url"]: d for d in documents}.values())[:100],
              "excerpt": text[:100], "retrieved_at": now(), "license": "not_verified_per_item",
              "review_status": "metadata_only", "remote_content_is_untrusted": True,
              "parameter_authority": False, "raw_article_saved": False}
    record["published_at"] = page.css('meta[property="article:published_time"]::attr(content)').get() or page.css("time[datetime]::attr(datetime)").get()
    record["page_license_link"] = page.css('link[rel="license"]::attr(href)').get()
    record["content_hash"] = digest({"title": title, "text": text, "images": images, "documents": documents})
    return record


def discover_links(data, base, source, limit=12):
    """RSS/Atom/sitemap only; disable external entities and network resolution."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)
    root = etree.fromstring(data, parser=parser)
    nodes = root.xpath("//*[local-name()='item']/*[local-name()='link']/text() | "
                       "//*[local-name()='entry']/*[local-name()='link']/@href | "
                       "//*[local-name()='url']/*[local-name()='loc']/text() | "
                       "//*[local-name()='sitemap']/*[local-name()='loc']/text()")
    result = []
    for value in nodes:
        try:
            target = canonical_url(urljoin(base, str(value)))
        except ValueError:
            continue
        approved = get_source(target)
        if approved and approved["id"] == source["id"] and target != base:
            result.append(target)
    return list(dict.fromkeys(result))[:limit]


def discover_listing(html, base, source, limit=12):
    """Reviewed public article indexes; only same-publisher project links."""
    page = Selector(content=html, url=base, adaptive=False, huge_tree=False)
    anchors = page.css("article a[href], h2 a[href], h3 a[href]") or page.css("a[href]")
    result = []
    for anchor in anchors:
        try:
            target = canonical_url(urljoin(base, anchor.attrib.get("href", "")))
        except ValueError:
            continue
        path = urlsplit(target).path
        approved = get_source(target)
        if not approved or approved["id"] != source["id"] or not re.search(source["article_pattern"], path):
            continue
        if re.search(r"/(?:about|contact|privacy|terms|login|search|feed|subscribe|advertise|wp-admin|wp-login|wp-content)(?:[./-]|$)", path, re.I):
            continue
        if target != base and not urlsplit(target).query and target not in result:
            result.append(target)
        if len(result) >= limit:
            break
    return result


class FetchDenied(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class Research:
    def __init__(self, root=None, *, resolver=True, min_delay=1.5):
        self.root = Path(root or ROOT / "runtime/research").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "references.sqlite3"
        self.resolver, self.min_delay = resolver, min_delay
        self.robots = {}
        self.timeout = 18
        self.client = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.1"},
                                   follow_redirects=False, timeout=self.timeout)
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS frontier(url TEXT PRIMARY KEY, source_id TEXT, role TEXT,
                    next_due REAL DEFAULT 0, priority INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS pages(url TEXT PRIMARY KEY, source_id TEXT, status TEXT,
                    data TEXT, content_hash TEXT, checked_at TEXT);
                CREATE TABLE IF NOT EXISTS host_limits(host TEXT PRIMARY KEY, last_request REAL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY, data TEXT);
            """)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def close(self):
        self.client.close()

    def enqueue(self, url, role="page", priority=0):
        url, source = validate_url(url, resolve=False)
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO frontier(url,source_id,role,priority) VALUES(?,?,?,?)",
                        (url, source["id"], role, priority))
        return url

    def seed(self):
        for source in SOURCES:
            if not source["active"]:
                continue
            priority = 10 if source["authority"].startswith(("official", "manufacturer_technical")) else 5
            for url in source.get("seeds", []):
                self.enqueue(url, priority=priority)
            for url in source.get("feeds", []):
                self.enqueue(url, "discovery", priority=1)
            for url in source.get("listings", []):
                self.enqueue(url, "listing", priority=3)

    def _raw_get(self, url):
        # The caller holds a process lock, so the persisted host throttle is shared.
        for redirect in range(4):
            url, source = validate_url(url, resolve=self.resolver)
            host = urlsplit(url).netloc
            with self.connect() as con:
                row = con.execute("SELECT last_request FROM host_limits WHERE host=?", (host,)).fetchone()
                wait = max(0, self.min_delay - (time.time() - row[0])) if row else 0
            if wait:
                time.sleep(wait)
            with self.connect() as con:
                con.execute("INSERT OR REPLACE INTO host_limits VALUES(?,?)", (host, time.time()))
            with self.client.stream("GET", url, timeout=self.timeout) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    target = canonical_url(urljoin(url, response.headers.get("location", "")))
                    approved = get_source(target)
                    if not approved or approved["id"] != source["id"]:
                        raise FetchDenied("blocked", "Cross-publisher redirect requires a reviewed source entry")
                    if not urlsplit(url).path.endswith("/robots.txt"):
                        self._check_robots(target)
                    url = target
                    continue
                data = bytearray()
                if "application/pdf" in response.headers.get("content-type", "").lower() or re.search(r"\.(pdf|dwg|dxf|ifc)$", urlsplit(url).path, re.I):
                    return response.status_code, dict(response.headers), b"", url
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise FetchDenied("error", "Response exceeds the per-page size budget")
                return response.status_code, dict(response.headers), bytes(data), url
        raise FetchDenied("error", "Too many redirects")

    def _check_robots(self, url):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            status, headers, blob, _ = self._raw_get(origin + "/robots.txt")
            if status == 404:
                self.robots[origin] = Protego.parse("")
            elif status == 200:
                self.robots[origin] = Protego.parse(blob.decode("utf-8", errors="replace"))
            else:
                raise FetchDenied("robots_unavailable", f"robots.txt HTTP {status}")
        parser = self.robots[origin]
        if not parser.can_fetch(url, UA):
            raise FetchDenied("robots_denied", "Source robots policy excludes this URL")
        delay = parser.crawl_delay(UA)
        if delay is not None:
            self.min_delay = max(self.min_delay, float(delay))
            if self.min_delay > 30:
                raise FetchDenied("robots_denied", "Required crawl delay exceeds this bounded run; defer source")

    def collect(self, url, role="page"):
        url, source = validate_url(url, resolve=self.resolver)
        checked = now()
        try:
            self._check_robots(url)
            status, headers, blob, final_url = self._raw_get(url)
            if status in {401, 403, 407, 429}:
                raise FetchDenied("blocked", f"HTTP {status}; no challenge/login bypass attempted")
            if status != 200:
                raise FetchDenied("error", f"HTTP {status}")
            typ = headers.get("content-type", "").lower()
            if "pdf" in typ or re.search(r"\.(pdf|dwg|dxf|ifc)$", urlsplit(final_url).path, re.I):
                data = {"url": final_url, "title": urlsplit(final_url).path.rsplit("/", 1)[-1],
                        "source_id": source["id"], "status": "asset_link", "downloaded": False}
                state = "asset_link"
            elif role == "listing":
                links = discover_listing(blob.decode("utf-8", errors="replace"), final_url, source)
                for target in links:
                    self.enqueue(target, "page", priority=2)
                data, state = {"url": url, "source_id": source["id"], "discovered": links}, "ok"
            elif role == "discovery" or "xml" in typ:
                links = discover_links(blob, final_url, source)
                for target in links:
                    self.enqueue(target, "discovery" if target.endswith(".xml") else "page", priority=2)
                data, state = {"url": url, "source_id": source["id"], "discovered": links}, "ok"
            else:
                # Only public page text is parsed, and only metadata is retained.
                # iter_bytes already decompresses transfer encodings; constructing
                # another Response with Content-Encoding would decompress twice.
                charset = re.search(r"charset\s*=\s*['\"]?([\w-]+)", headers.get("content-type", ""), re.I)
                encoding = charset.group(1) if charset else "utf-8"
                if encoding.lower() not in {"utf-8", "utf8", "gb18030", "gbk", "gb2312", "windows-1252", "iso-8859-1"}:
                    encoding = "utf-8"
                html = blob.decode(encoding, errors="replace")
                if re.search(r"<title>\s*(just a moment|access denied|attention required)", html, re.I):
                    raise FetchDenied("blocked", "Challenge page detected; no bypass attempted")
                data, state = parse_page(final_url, html, source), "ok"
        except FetchDenied as exc:
            state, data = exc.status, {"url": url, "source_id": source["id"], "error": str(exc)}
        except Exception as exc:
            state, data = "error", {"url": url, "source_id": source["id"], "error": f"{type(exc).__name__}: {str(exc)[:250]}"}
        data.update(status=state, checked_at=checked)
        fingerprint = data.get("content_hash", digest({k: v for k, v in data.items() if k not in {"checked_at", "retrieved_at"}}))
        with self.connect() as con:
            old = con.execute("SELECT content_hash,status FROM pages WHERE url=?", (url,)).fetchone()
            changed = old is None or old[0] != fingerprint or old[1] != state
            con.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?)",
                        (url, source["id"], state, json.dumps(data, ensure_ascii=False), fingerprint, checked))
            due = time.time() + (6 * 3600 if role in {"discovery", "listing"} and state == "ok" else STATUS_RETRY.get(state, 3600))
            con.execute("UPDATE frontier SET next_due=? WHERE url=?", (due, url))
        return {"url": url, "source_id": source["id"], "status": state, "changed": changed,
                "images": len(data.get("images", [])), "documents": len(data.get("documents", [])),
                "error": data.get("error"), "title": data.get("title")}

    def run(self, limit=12, time_budget=100):
        if isinstance(limit, bool) or not 1 <= limit <= 32 or not 10 <= time_budget <= 180:
            raise ValueError("limit must be 1..32, time_budget 10..180 seconds")
        with workspace_lock(self.root):
            self.seed()
            started, results = time.monotonic(), []
            with self.connect() as con:
                queue = con.execute("SELECT * FROM frontier WHERE next_due<=? ORDER BY next_due,priority DESC,source_id,url LIMIT 200",
                                    (time.time(),)).fetchall()
            per_source = Counter()
            for row in queue:
                remaining = time_budget - (time.monotonic() - started)
                if remaining < 6 or len(results) >= limit:
                    break
                if per_source[row["source_id"]] >= 2:
                    continue
                self.timeout = min(18, max(2, remaining / 3))
                results.append(self.collect(row["url"], row["role"]))
                per_source[row["source_id"]] += 1
            run_id = f"{int(time.time())}-{digest(results)[:8]}"
            result = {"ok": True, "run_id": run_id, "date": now(), "attempted": len(results),
                      "changed": sum(r["changed"] for r in results), "results": results,
                      "elapsed_seconds": round(time.monotonic() - started, 2), "status": self.status()}
            with self.connect() as con:
                con.execute("INSERT OR REPLACE INTO runs VALUES(?,?)", (run_id, json.dumps(result, ensure_ascii=False)))
            atomic_json(self.root / "runs" / f"{run_id}.json", result)
            result["report"] = str(self.report(run_id))
            return result

    def ingest(self, url):
        with workspace_lock(self.root):
            url = self.enqueue(url, priority=20)
            result = self.collect(url)
            result["report"] = str(self.report())
            return {"ok": result["status"] in {"ok", "asset_link"}, **result}

    def search(self, query="", discipline="", drawing_type="", limit=20):
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        if discipline and discipline not in DISCIPLINES:
            raise ValueError("Unknown discipline")
        if drawing_type and drawing_type not in DRAWING_TYPES:
            raise ValueError("Unknown drawing type")
        with self.connect() as con:
            rows = con.execute("SELECT data FROM pages WHERE status='ok' ORDER BY checked_at DESC").fetchall()
        matches = []
        for row in rows:
            data = json.loads(row[0])
            if "title" not in data or "images" not in data:
                continue
            if query.lower() not in json.dumps(data, ensure_ascii=False).lower():
                continue
            if discipline and discipline not in data.get("disciplines", []):
                continue
            if drawing_type and drawing_type not in data.get("drawing_types", []):
                continue
            matches.append(data)
            if len(matches) >= limit:
                break
        return {"ok": True, "count": len(matches), "results": matches}

    def status(self):
        with self.connect() as con:
            rows = con.execute("SELECT source_id,status,data FROM pages").fetchall()
            queue = con.execute("SELECT COUNT(*) FROM frontier WHERE next_due<=?", (time.time(),)).fetchone()[0]
            lessons = con.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
        counts, images, candidates, docs, coverage = Counter(), 0, 0, 0, Counter()
        for row in rows:
            counts[row["status"]] += 1
            item = json.loads(row["data"])
            if row["status"] == "ok" and "images" in item:
                images += len(item["images"])
                candidates += sum(bool(i.get("drawing_types")) for i in item["images"])
                docs += len(item.get("documents", []))
                coverage.update(item.get("disciplines", []))
        return {"pages_by_status": dict(counts), "image_references": images, "drawing_image_candidates": candidates, "document_links": docs,
                "due_urls": queue, "approved_lessons": lessons, "discipline_coverage": dict(coverage),
                "sources": [{"id": s["id"], "name": s["name"], "automatic": s["active"],
                             "mode": s.get("mode", "public_http"), "disciplines": s["disciplines"]} for s in SOURCES],
                "all_images_visually_verified": False, "bulk_documents_downloaded": False}

    def report(self, run_id=""):
        status = self.status()
        pages = self.search(limit=100)["results"]
        lines = ["# CAD多平台图纸资料采集", "", f"日期：{now()}", "",
                 "摘要：采集公开页面的来源、图像链接和文档链接；分类来自页面/图注，尚未逐张视觉验收。", "",
                 f"页面状态：{json.dumps(status['pages_by_status'], ensure_ascii=False)}；图像引用 {status['image_references']}，其中图注/文件名匹配图纸的候选 {status['drawing_image_candidates']}，文档链接 {status['document_links']}。", "",
                 "| 平台 | 标题 | 专业 | 图纸类型（候选） | 图像/文档 |", "| --- | --- | --- | --- | --- |"]
        for p in pages:
            title = p["title"].replace("|", " ").replace("[", "(").replace("]", ")")[:100]
            lines.append(f"| {p['publisher']} | [{title}]({p['url']}) | {', '.join(p['disciplines'])} | {', '.join(p['drawing_types']) or '待识图'} | {len(p['images'])}/{len(p['documents'])} |")
        lines += ["", "## 图纸候选链接", ""]
        for p in pages[:20]:
            candidates = [i for i in p["images"] if i["drawing_types"]][:6]
            if not candidates and not p["documents"]:
                continue
            lines += [f"### {p['publisher']}：{p['title'].replace('|', ' ')[:100]}", "",
                      f"[原页面]({p['url']})；原发布时间：{p.get('published_at') or '未识别'}；版权/单项许可待核实。", ""]
            for i in candidates:
                caption = i["caption"].replace("[", "(").replace("]", ")")[:80] or ", ".join(i["drawing_types"])
                lines.append(f"- [{caption}]({i['url']})（图注候选，尚未逐图验收）")
            for d in p["documents"][:6]:
                lines.append(f"- [{d['format'].upper()}：{d['title'][:70]}]({d['url']})（链接索引，未下载）")
        lines += ["", "## 待处理与边界", "", "HTTP 403/登录/挑战或robots限制的来源记录为阻塞；不尝试绕过。来源有图注不代表图纸完整、可施工或获再分发许可。", "",
                  "电气保护、线缆规格、结构配筋、消防等参数必须另核官方/厂家资料与项目条件，不能从案例自动采用。", "", "## 相关链接", "",
                  "[Scrapling](https://github.com/D4Vinci/Scrapling) · [研究入口说明](../../../references/drawing-research.md)"]
        path = self.root / "reports" / (f"{run_id}.md" if run_id else "latest.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def promote_lesson(self, lesson):
        """Only explicitly reviewed workflow observations, with collected provenance."""
        with workspace_lock(self.root):
            return self._promote_lesson(lesson)

    def _promote_lesson(self, lesson):
        identifier = lesson.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", identifier):
            raise ValueError("Invalid lesson id")
        if lesson.get("kind") != "workflow" or lesson.get("reviewed") is not True:
            raise ValueError("Only reviewed workflow lessons can be promoted; numeric engineering parameters are excluded")
        statement, limits = lesson.get("statement", ""), lesson.get("limits", "")
        if not isinstance(statement, str) or not 20 <= len(statement) <= 2000 or not limits:
            raise ValueError("Lesson requires a bounded original statement and explicit limits")
        sources = lesson.get("source_urls", [])
        if not isinstance(sources, list) or len(set(sources)) < 2:
            raise ValueError("At least two independently checked source URLs are required")
        sources = list(dict.fromkeys(canonical_url(u) for u in sources))
        if len(sources) < 2:
            raise ValueError("At least two distinct canonical source URLs are required")
        records = []
        with self.connect() as con:
            for url in sources:
                row = con.execute("SELECT data,status FROM pages WHERE url=?", (canonical_url(url),)).fetchone()
                if not row or row["status"] != "ok":
                    raise ValueError("Lesson sources must be successfully collected, not search snippets or blocked pages")
                record = json.loads(row["data"])
                if not record.get("content_hash") or not record.get("title"):
                    raise ValueError("Discovery feeds cannot serve as reviewed lesson evidence")
                records.append(record)
        # Reject instruction-like text that could have been copied from remote pages.
        if re.search(r"ignore (previous|all)|system prompt|api[_ -]?key|powershell|exec\(|自动执行|绕过验证|关闭安全", statement, re.I):
            raise ValueError("Remote instructions cannot be promoted into the Skill")
        if re.search(r"\d+(?:\.\d+)?\s*(?:mm²|mm|cm|MPa|kN|kW|kVA|m²|[VAΩ]\b|毫米|千瓦|伏特|安培)", statement, re.I):
            raise ValueError("Numeric engineering prescriptions cannot be automatically promoted")
        source_hashes = {r["url"]: r.get("content_hash") for r in records}
        with self.connect() as con:
            old = con.execute("SELECT data FROM lessons WHERE id=?", (identifier,)).fetchone()
        if old:
            prior = json.loads(old[0])
            if all(prior.get(k) == lesson.get(k) for k in ("statement", "limits", "kind", "title")) and prior.get("source_hashes") == source_hashes:
                return {"ok": True, "path": prior["path"], "knowledge_revision": prior["knowledge_revision"], "unchanged": True}
        content = "\n".join([f"# {lesson.get('title', identifier)}", "", f"日期：{now()}", "",
            "摘要：经审阅的绘图工作方法，附来源与适用边界；不是工程参数或规范认证。", "", statement, "",
            "## 适用边界", "", str(limits), "", "## 相关链接", "",
            *[f"- [{clean_text(r.get('title', r['url']), 160)}]({r['url']})；采集时间 {r['checked_at']}" for r in records], ""])
        path = ROOT / "references/learned" / f"{identifier}.md"
        if path.exists() and path.read_text(encoding="utf-8") != content:
            # Keep a rollback copy; no deletion or overwrite without history.
            archive = self.root / "lesson-history" / f"{identifier}-{digest(path.read_text(encoding='utf-8'))[:12]}.md"
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                archive.write_bytes(path.read_bytes())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        record = {**lesson, "source_hashes": source_hashes,
                  "path": str(path), "knowledge_revision": hashlib.sha256(content.encode()).hexdigest(), "updated": now()}
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO lessons VALUES(?,?)", (identifier, json.dumps(record, ensure_ascii=False)))
        atomic_json(self.root / "lessons" / f"{identifier}.json", record)
        return {"ok": True, "path": str(path), "knowledge_revision": record["knowledge_revision"]}
