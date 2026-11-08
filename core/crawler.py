"""Configurable collector for public medical education listing pages only."""

import re
import time
import unicodedata
from dataclasses import dataclass
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.utils.dateparse import parse_date
from soupsieve.util import SelectorSyntaxError

from .models import CrawledMedicalData


USER_AGENT = "TCMClinicCourseProject/1.0 (public educational pages; respectful interval)"
NETWORK_UNAVAILABLE_MESSAGE = "当前网络无法访问目标数据源，请在本地网络环境重新执行。"
ZYSJ_INDEX_URL = "https://www.zysj.com.cn/lilunshuji/zhongyaoxue/index.html"
ZYSJ_ROBOTS_URL = "https://www.zysj.com.cn/robots.txt"
ZYSJ_SOURCE_NAME = "中医世家"
ZYSJ_DETAIL_PATH = re.compile(r"/lilunshuji/zhongyaoxue/\d+\.html$")


@dataclass(frozen=True)
class CrawlConfig:
    urls: tuple[str, ...]
    item_selector: str
    title_selector: str
    source_name: str
    link_selector: str = "a[href]"
    category_selector: str = ""
    symptom_selector: str = ""
    department_selector: str = ""
    date_selector: str = ""
    text_selector: str = ""
    delay: float = 1.0
    max_items: int = 100


def clean_text(value, limit):
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def normalized_category(value):
    return clean_text(unicodedata.normalize("NFKC", value or ""), 50).strip(" |/、，,。")


def normalized_date(value):
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})", value or "")
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return parse_date(f"{year:04d}-{month:02d}-{day:02d}")
    except ValueError:
        return None


def _selected_text(item, selector, limit):
    node = item.select_one(selector) if selector else None
    return clean_text(node.get_text(" ", strip=True) if node else "", limit)


def parse_listing(html, page_url, config):
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select(config.item_selector)[:config.max_items]:
        title_node = item.select_one(config.title_selector)
        link_node = item.select_one(config.link_selector)
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else "", 200)
        href = link_node.get("href", "") if link_node else ""
        source_url = urljoin(page_url, href)
        if not title or not href or urlparse(source_url).scheme not in ("http", "https"):
            continue
        raw_node = item.select_one(config.text_selector) if config.text_selector else item
        yield {
            "title": title,
            "category": normalized_category(_selected_text(item, config.category_selector, 50)),
            "symptom": _selected_text(item, config.symptom_selector, 200),
            "department_name": _selected_text(item, config.department_selector, 100),
            "source_name": clean_text(config.source_name, 100),
            "source_url": source_url[:500],
            "publish_date": normalized_date(_selected_text(item, config.date_selector, 60)),
            "raw_text": clean_text(raw_node.get_text(" ", strip=True) if raw_node else "", 3000),
        }


def crawl(config):
    """Return (created, duplicate, errors); never infer a website or fabricate rows."""
    if not config.urls or not config.item_selector or not config.title_selector or not config.source_name:
        raise ValueError("须配置公开网页 URL、条目选择器、标题选择器和来源名称。")
    if config.delay < 1 or not 1 <= config.max_items <= 100:
        raise ValueError("请求间隔至少 1 秒，每页最多 100 条。")
    for url in config.urls:
        if urlparse(url).scheme not in ("http", "https"):
            raise ValueError("仅支持 http/https 公开网页。")
    created = duplicates = 0
    errors = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        for index, url in enumerate(config.urls):
            if index:
                time.sleep(config.delay)
            try:
                response = session.get(url, timeout=12)
                response.raise_for_status()
                if "html" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError("响应不是 HTML 页面")
                for row in parse_listing(response.text, response.url, config):
                    _, was_created = CrawledMedicalData.objects.get_or_create(
                        source_url=row["source_url"], defaults={key: value for key, value in row.items() if key != "source_url"}
                    )
                    created += int(was_created)
                    duplicates += int(not was_created)
            except requests.Timeout:
                errors.append(f"{url}: {NETWORK_UNAVAILABLE_MESSAGE}")
            except (requests.RequestException, ValueError, SelectorSyntaxError) as exc:
                errors.append(f"{url}: {exc}")
    return created, duplicates, errors


def parse_zysj_index(html, page_url=ZYSJ_INDEX_URL, max_items=20):
    """Read the book's chapter/section list; yield medicine links only."""
    soup = BeautifulSoup(html, "html.parser")
    directory = next((ul for ul in soup.find_all("ul")
                      if len(ul.find_all("li", recursive=False)) > 10
                      and "zhongyaoxue" in str(ul)[:20000]), soup)
    chapter = section = ""
    seen = set()
    yielded = 0
    for anchor in directory.select("a[href]"):
        label = re.sub(r"\s+节$", "", clean_text(anchor.get_text(" ", strip=True), 100))
        chapter_match = re.match(r"^第[一二三四五六七八九十百\d]+章\s*(.+)$", label)
        section_match = re.match(r"^第[一二三四五六七八九十百\d]+节\s*(.+)$", label)
        if chapter_match:
            chapter, section = normalized_category(chapter_match.group(1)), ""
            continue
        if section_match:
            section = normalized_category(section_match.group(1))
            continue
        if not chapter.endswith("药") or not label or len(label) > 30:
            continue
        if any(word in label for word in ("注意事项", "其它", "其他", "应用", "功效", "目录")):
            continue
        url = urljoin(page_url, anchor.get("href", ""))
        parsed = urlparse(url)
        if parsed.netloc != urlparse(page_url).netloc or not ZYSJ_DETAIL_PATH.fullmatch(parsed.path):
            continue
        canonical = parsed._replace(fragment="", query="").geturl()
        if canonical in seen:
            continue
        seen.add(canonical)
        category = section if section.endswith("药") else chapter
        yield {"title": label, "category": category, "source_url": canonical}
        yielded += 1
        if yielded >= max_items:
            break


def parse_zysj_detail(html, expected_title=""):
    soup = BeautifulSoup(html, "html.parser")
    page_title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "", 200)
    if expected_title and page_title and expected_title not in page_title:
        return ""
    content = soup.select_one("div.content, div.article, #content")
    if content is None:
        return ""
    for node in content.select("script, style, nav, header, footer, aside, form, .nav, .related, .share, .ad, .advertisement"):
        node.decompose()
    text = clean_text(content.get_text(" ", strip=True), 3000)
    return text if len(text) >= 40 and any(word in text for word in ("药用", "功效", "性味", "归经", "临床应用")) else ""


def _fetch_public_html(session, url):
    response = session.get(url, timeout=(5, 12))
    response.raise_for_status()
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError(f"非 HTML 页面：{url}")
    for encoding in ("utf-8", "gb18030"):
        try:
            return response.content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别网页编码：{url}")


def crawl_zysj_herbs(max_items=20, delay=2.0):
    """Collect at most 20 publicly accessible herb entries, respecting robots.txt."""
    if not 1 <= max_items <= 20 or delay < 2:
        raise ValueError("中医世家单次最多采集 20 条，请求间隔至少 2 秒。")
    created = duplicates = 0
    errors = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        try:
            robots_response = session.get(ZYSJ_ROBOTS_URL, timeout=(5, 12))
            if robots_response.status_code != 404:
                robots_response.raise_for_status()
                rules = RobotFileParser()
                rules.parse(robots_response.text.splitlines())
                if not rules.can_fetch(USER_AGENT, ZYSJ_INDEX_URL):
                    raise ValueError("robots.txt 不允许访问中药学目录页。")
            else:
                rules = None
            time.sleep(delay)
            index_html = _fetch_public_html(session, ZYSJ_INDEX_URL)
        except requests.Timeout as exc:
            raise ValueError(NETWORK_UNAVAILABLE_MESSAGE) from exc
        except (requests.RequestException, ValueError) as exc:
            raise ValueError(f"中医世家目录访问失败：{type(exc).__name__}: {exc}") from exc
        entries = list(parse_zysj_index(index_html, max_items=max_items))
        if not entries:
            raise ValueError("目录已可访问，但未解析出药材详情链接；可能是页面结构变化。")
        for entry in entries:
            url = entry["source_url"]
            if rules is not None and not rules.can_fetch(USER_AGENT, url):
                errors.append(f"robots.txt 不允许访问详情页：{url}")
                continue
            if CrawledMedicalData.objects.filter(source_url=url).exists():
                duplicates += 1
                continue
            time.sleep(delay)
            try:
                raw_text = parse_zysj_detail(_fetch_public_html(session, url), entry["title"])
                if not raw_text:
                    errors.append(f"详情正文为空或页面结构变化：{url}")
                    continue
                _, was_created = CrawledMedicalData.objects.get_or_create(
                    source_url=url,
                    defaults={"title": entry["title"], "category": entry["category"],
                              "source_name": ZYSJ_SOURCE_NAME, "raw_text": raw_text},
                )
                created += int(was_created)
                duplicates += int(not was_created)
            except requests.Timeout as exc:
                raise ValueError(NETWORK_UNAVAILABLE_MESSAGE) from exc
            except (requests.RequestException, ValueError, SelectorSyntaxError) as exc:
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
    return created, duplicates, errors
