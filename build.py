#!/usr/bin/env python3
"""실시간 한국 트렌드·이슈 브리핑 (0520goeus/kr-trend-brief) — 0원·0토큰 3시간마다 자동 갱신 + IndexNow."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

SITE_NAME = "오늘의 실검·트렌드 브리핑"
SITE_URL = "https://0520goeus.github.io/kr-trend-brief"
INDEXNOW_KEY = "a91c64e2b8504f3da72e110c489b527e"
GOOGLE_FILE = "google873809343766a3b6.html"
ADSENSE_CLIENT = "ca-pub-8749404731911210"
COUPANG_TRACKING = "AF9170267"
COUPANG_WIDGET_ID = 1049499

TRENDS_RSS = "https://trends.google.com/trending/rss?geo=KR"
NEWS_ECON_RSS = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
NEWS_TECH_RSS = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko"
NS = {"ht": "https://trends.google.com/trending/rss"}

# AdSense & Daum low-quality safety filter (blocks sensitive crime/death/scandal keywords)
BLOCK_WORDS = (
    "사망", "살인", "시신", "부고", "자살", "투신", "극단적", "사고사", "성범죄", "성폭행",
    "피습", "흉기", "학대", "마약", "음주운전", "구속", "탄핵", "폭행", "화재 참사", "유기",
)

DISCLOSURE = "이 페이지는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
COUPANG_BOX = (
    '<section class="card shop">'
    f'<p class="disc">{DISCLOSURE}</p>'
    '<h3>🔥 오늘 실시간 인기 생활·디지털 특가 상품</h3>'
    '<script src="https://ads-partners.coupang.com/g.js"></script>'
    f'<script>new PartnersCoupang.G({{"id":{COUPANG_WIDGET_ID},"template":"carousel",'
    f'"trackingCode":"{COUPANG_TRACKING}","width":"100%","height":"140","tsource":""}});</script>'
    "</section>"
)


def _ssl_ctx():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def is_safe_topic(text: str) -> bool:
    return not any(w in text for w in BLOCK_WORDS)


def fetch_xml(url: str) -> ET.Element | None:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urlopen(req, timeout=15, context=_ssl_ctx()) as r:
            return ET.fromstring(r.read())
    except Exception:
        return None


def collect_live_briefings() -> list[dict]:
    items: list[dict] = []
    # 1. Google Trends Korea
    root = fetch_xml(TRENDS_RSS)
    if root is not None:
        for it in root.findall(".//item"):
            title = (it.findtext("title") or "").strip()
            if not title or not is_safe_topic(title):
                continue
            traffic = (it.findtext("ht:approx_traffic", default="급상승", namespaces=NS) or "급상승").strip()
            news = []
            for ni in it.findall("ht:news_item", NS):
                nt = (ni.findtext("ht:news_item_title", default="", namespaces=NS) or "").strip()
                ns = (ni.findtext("ht:news_item_source", default="", namespaces=NS) or "").strip()
                nu = (ni.findtext("ht:news_item_url", default="", namespaces=NS) or "").strip()
                if nt and is_safe_topic(nt):
                    news.append({"title": nt, "source": ns, "url": nu})
            if not news:
                continue
            slug = hashlib.sha1(f"{NOW.strftime('%Y%m%d')}:{title}".encode()).hexdigest()[:10]
            items.append({
                "slug": f"t-{slug}",
                "category": "실시간 급상승",
                "keyword": title,
                "traffic": traffic,
                "date": NOW.strftime("%Y-%m-%d"),
                "updated": NOW.strftime("%Y-%m-%d %H:%M KST"),
                "news": news[:4],
            })

    # 2. Google News Korea Business & Tech highlights (always AdSense-safe high-CPC topics!)
    for cat_name, feed_url in (("경제·증시 브리핑", NEWS_ECON_RSS), ("IT·테크 브리핑", NEWS_TECH_RSS)):
        nroot = fetch_xml(feed_url)
        if nroot is None:
            continue
        added = 0
        for it in nroot.findall(".//item"):
            if added >= 4:
                break
            raw_t = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if not raw_t or not is_safe_topic(raw_t):
                continue
            parts = raw_t.rsplit(" - ", 1)
            headline = parts[0].strip()
            src = parts[1].strip() if len(parts) > 1 else "주요 언론"
            slug = hashlib.sha1(f"{NOW.strftime('%Y%m%d')}:{headline}".encode()).hexdigest()[:10]
            items.append({
                "slug": f"n-{slug}",
                "category": cat_name,
                "keyword": headline[:44],
                "traffic": "주요 이슈",
                "date": NOW.strftime("%Y-%m-%d"),
                "updated": NOW.strftime("%Y-%m-%d %H:%M KST"),
                "news": [{"title": headline, "source": src, "url": link}],
            })
            added += 1
    return items


CSS = """
:root{--bg:#f8fafc;--card:#ffffff;--ink:#0f172a;--sub:#475569;--line:#e2e8f0;--accent:#2563eb;--hot:#e11d48}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.8 -apple-system,"Apple SD Gothic Neo",sans-serif}
header{background:#0f172a;color:#fff;padding:16px 20px}
.wrap{max-width:920px;margin:0 auto;padding:0 18px}
header .wrap{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
header a{color:#cbd5e1;text-decoration:none;font-size:14px;font-weight:600}
header .brand{color:#fff;font-size:19px;font-weight:800}
nav{display:flex;gap:14px;flex-wrap:wrap}
main{padding:28px 0 60px;display:grid;gap:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
h1{font-size:26px;line-height:1.35;margin:0 0 10px}h2{font-size:19px;margin:0 0 12px}h3{font-size:16.5px;margin:0 0 8px}
.sub{color:var(--sub);margin:0 0 12px}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700;background:#fee2e2;color:#be123c;margin-bottom:8px}
.badge.blue{background:#dbeafe;color:#1d4ed8}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(265px,1fr));gap:13px}
.tile{display:grid;gap:5px;padding:15px;border:1px solid var(--line);border-radius:12px;background:#fff;text-decoration:none;color:var(--ink)}
.tile:hover{border-color:var(--accent)}
.tile b{font-size:15.5px;line-height:1.4}.tile small{color:var(--sub)}
.news-list{padding-left:20px;display:grid;gap:8px}
.news-list a{color:var(--accent);text-decoration:none;font-weight:600}
.faq{background:#f8fafc;padding:14px 16px;border-left:4px solid var(--accent);border-radius:8px;margin:10px 0}
.shop .disc{font-size:12.5px;color:var(--sub);margin:0 0 8px}
footer{border-top:1px solid var(--line);padding:24px 0 44px;color:var(--sub);font-size:13.5px}
footer a{color:var(--accent);text-decoration:none}
"""


def render_page(rel: str, title: str, desc: str, body: str, json_ld: dict | None = None) -> str:
    canon = f"{SITE_URL}/" if rel == "index.html" else f"{SITE_URL}/{rel}"
    ld = f'<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>' if json_ld else ""
    page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<link rel="stylesheet" href="{SITE_URL}/style.css">{ld}<meta name="google-site-verification" content="E0MKLI_9g0wTNR9pjNKmxb_QGiA51AIK93dV9qBKumg"><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8749404731911210" crossorigin="anonymous"></script><script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebSite","name":"오늘의 실검·트렌드 브리핑","url":"https://0520goeus.github.io/kr-trend-brief/"}}</script><meta property="og:title" content="오늘의 실검·트렌드 브리핑"><meta property="og:type" content="website">
</head>
<body>
<header><div class="wrap">
  <a class="brand" href="{SITE_URL}/">⚡ {SITE_NAME}</a>
  <nav>
    <a href="{SITE_URL}/">실시간 브리핑</a>
    <a href="https://0520goeus.github.io/price-note/">생필품 가격노트</a>
    <a href="https://0520goeus.github.io/vs-pick/">가성비 VS 사전</a>
    <a href="https://0520goeus.github.io/money-calc-kr/">연봉 실수령액</a>
    <a href="https://0520goeus.github.io/benefit-calc-kr/">2026 지원금</a>
  </nav>
</div></header>
<main class="wrap">{body}<div style="margin:20px auto;max-width:960px;padding:16px 20px;border-radius:14px;background:linear-gradient(135deg,#0f172a,#0f766e);color:#fff;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;"><div><div style="font-weight:800;font-size:16px;">2026 직장인·1인셀러 무매크로 자동계산 엑셀 3종 올인원 번들</div><div style="font-size:13px;opacity:.9;margin-top:2px;">1인셀러 마진·ROAS + 내집마련 매물10개 비교 + 월급 가계부·순자산 대시보드 (즉시 다운로드)</div></div><a href="https://0520goeus.github.io/excel-store/" target="_blank" rel="noopener" style="background:#facc15;color:#0f172a;padding:10px 18px;border-radius:10px;font-weight:800;font-size:14px;text-decoration:none;white-space:nowrap;">3종 번들 즉시 다운로드 →</a></div>
</main>
<footer><div class="wrap">
  <p>자동 갱신: {NOW.strftime("%Y-%m-%d %H:%M KST")} · 출처: Google Trends Korea & 주요 언론 공식 RSS</p>
  <p>패밀리 사이트: <a href="https://0520goeus.github.io/price-note/">해뎐 가격노트</a> · <a href="https://0520goeus.github.io/elec-calc/">전기세 얼마</a> · <a href="https://0520goeus.github.io/vs-pick/">가성비 VS 사전</a> · <a href="https://0520goeus.github.io/life-fee-calc/">가전용량·직구관세</a> · <a href="https://0520goeus.github.io/money-calc-kr/">실수령액 계산기</a> · <a href="https://0520goeus.github.io/benefit-calc-kr/">지원금·실업급여</a> · <a href="https://0520goeus.github.io/seller-margin-calc/">셀러 마진 계산기</a> · <a href="https://lifefixnote-kr.blogspot.com/">생활해결 노트</a></p>
</div><div style="margin:14px auto 8px;max-width:960px;display:flex;flex-wrap:wrap;gap:6px;justify-content:center;font-size:12px;"><a href="https://0520goeus.github.io/house-calc-kr/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">부동산·대출·복비</a><a href="https://0520goeus.github.io/car-calc-kr/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">자동차세·유지비</a><a href="https://0520goeus.github.io/money-calc-kr/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">실수령액·금융</a><a href="https://0520goeus.github.io/benefit-calc-kr/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">2026 지원금</a><a href="https://0520goeus.github.io/life-fee-calc/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">평수가전·직구관세</a><a href="https://0520goeus.github.io/elec-calc/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">전기세 계산기</a><a href="https://0520goeus.github.io/vs-pick/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">가성비 VS 124종</a><a href="https://0520goeus.github.io/price-note/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">588 생필품 시세</a><a href="https://0520goeus.github.io/seller-margin-calc/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">셀러마진·엑셀</a><a href="https://0520goeus.github.io/kr-trend-brief/" style="padding:4px 9px;border-radius:6px;background:rgba(148,163,184,.18);color:inherit;text-decoration:none;">실시간 트렌드</a></div>
</footer></body></html>"""
    out = DIST / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return canon


def main() -> None:
    DATA.mkdir(exist_ok=True)
    archive_path = DATA / "archive.json"
    archive: list[dict] = json.loads(archive_path.read_text(encoding="utf-8")) if archive_path.exists() else []
    seen = {a["slug"] for a in archive}

    fresh = collect_live_briefings()
    for item in reversed(fresh):
        if item["slug"] not in seen:
            archive.insert(0, item)
            seen.add(item["slug"])
    archive = archive[:90]
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    (DIST / "style.css").write_text(CSS, encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    (DIST / GOOGLE_FILE).write_text(f"google-site-verification: {GOOGLE_FILE}", encoding="utf-8")
    (DIST / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")
    (DIST / "ads.txt").write_text(f"google.com, {ADSENSE_CLIENT.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")

    urls: list[str] = []
    tiles: list[str] = []
    rss_items: list[str] = []

    for item in archive:
        rel = f"p/{item['slug']}.html"
        kw = item["keyword"]
        title = f"[{item['date']}] {kw} — 핵심 정리·관련 보도 요약 | {SITE_NAME}"
        desc = f"{item['date']} {item['category']} 키워드 '{kw}'의 주요 언론 보도 핵심 내용과 체크포인트를 한눈에 정리했습니다."
        news_lis = "".join(
            f'<li><a href="{esc(n["url"])}" target="_blank" rel="noopener nofollow">{esc(n["title"])}</a> <small>({esc(n["source"])})</small></li>'
            for n in item["news"]
        )
        faqs = [
            (f"'{kw}' 키워드가 왜 실시간으로 주목받고 있나요?", f"{item['date']} 기준 {item['news'][0]['source']} 등 주요 매체에서 '{item['news'][0]['title']}' 관련 보도가 이어지며 검색량이 급증했습니다."),
            ("관련 원문 기사는 어디서 확인할 수 있나요?", "본문 상단의 공식 언론사 출처 링크를 통해 전체 보도 내용을 바로 확인하실 수 있습니다."),
        ]
        ld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs],
        }
        body = f"""
        <section class="card">
          <span class="badge {'blue' if item['category']!='실시간 급상승' else ''}">{esc(item['category'])} · {esc(item['traffic'])}</span>
          <h1>{esc(kw)} 핵심 정리 ({esc(item['date'])})</h1>
          <p class="sub">업데이트: {esc(item['updated'])} · 다중 언론 보도 사실 기반 자동 요약</p>
          <h2>1. 주요 보도 헤드라인 요약</h2>
          <ul class="news-list">{news_lis}</ul>
          <h2>2. 한눈에 보는 핵심 체크포인트</h2>
          <p>오늘({esc(item['date'])}) '{esc(kw)}' 이슈는 <strong>{esc(item['news'][0]['source'])}</strong> 등에서 핵심적으로 다뤄지며 검색 관심도가 높아졌습니다. 자극적인 루머 대신 위 공식 언론사의 원문 보도와 후속 발표를 함께 비교해 확인하는 것이 정확합니다.</p>
        </section>
        {COUPANG_BOX}
        <section class="card">
          <h2>자주 묻는 질문</h2>
          {"".join(f'<div class="faq"><strong>Q. {esc(q)}</strong><p class="sub" style="margin:6px 0 0">A. {esc(a)}</p></div>' for q, a in faqs)}
        </section>
        """
        canon = render_page(rel, title, desc, body, ld)
        urls.append(canon)
        tiles.append(
            f'<a class="tile" href="{canon}"><span class="badge {"blue" if item["category"]!="실시간 급상승" else ""}" style="width:fit-content">{esc(item["category"])} · {esc(item["traffic"])}</span>'
            f'<b>{esc(kw)}</b><small>{esc(item["date"])} · {esc(item["news"][0]["source"])}</small></a>'
        )
        rss_items.append(f"<item><title>{esc(title)}</title><link>{canon}</link><guid>{item['slug']}</guid><description>{esc(desc)}</description></item>")

    home_body = f"""
    <section class="card">
      <h1>오늘의 대한민국 실시간 트렌드 · 경제 · IT 핵심 브리핑</h1>
      <p class="sub">구글 트렌드 코리아 및 주요 언론 경제·IT 공식 피드에서 자극적·유해 키워드를 걸러내고 3시간마다 핵심 이슈만 정리합니다. (누적 {len(archive)}건)</p>
    </section>
    {COUPANG_BOX}
    <section class="card">
      <h2>최신 트렌드 & 이슈 브리핑</h2>
      <div class="grid">{"".join(tiles[:36])}</div>
    </section>
    """
    urls.insert(0, render_page(
        "index.html",
        f"{SITE_NAME} | 실시간 인기 검색어·경제·IT 핵심 이슈 자동 요약",
        "구글 트렌드 코리아 실시간 급상승 검색어와 경제·IT 주요 이슈를 3시간마다 자동 정리하는 브리핑 허브.",
        home_body,
    ))

    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc><lastmod>{NOW.strftime('%Y-%m-%d')}</lastmod></url>\n" for u in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )
    (DIST / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{SITE_NAME}</title>'
        f"<link>{SITE_URL}/</link><description>한국 실시간 트렌드·경제·IT 브리핑</description>{''.join(rss_items[:25])}</channel></rss>",
        encoding="utf-8",
    )
    (DIST / "urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    print(f"실시간 트렌드 브리핑 빌드 완료: 총 {len(urls)}페이지 (신규 수집 {len(fresh)}건)")


if __name__ == "__main__":
    main()
