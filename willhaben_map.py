#!/usr/bin/env python3
"""Create an interactive OpenStreetMap view from a locally saved Willhaben results page.

The program deliberately does not download or crawl Willhaben. Save the search-result page
from your browser as HTML, then give that file to this program.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from pathlib import Path
from urllib.parse import urljoin

import folium
import requests
from bs4 import BeautifulSoup
from folium.plugins import MarkerCluster

BASE = "https://www.willhaben.at"
POST_TOWN = re.compile(r"\b(\d{4})\s+([A-ZÄÖÜ][^\n|,;]{1,60})", re.UNICODE)
EURO = re.compile(r"€\s*([\d.]+(?:,\d{1,2})?)")
AREA = re.compile(r"([\d.]+(?:,\d+)?)\s*m²", re.I)
AD_PATH = re.compile(r"/iad/immobilien/d/", re.I)


def compact(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_number(s: str):
    try:
        return float(s.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def best_card_text(anchor) -> str:
    """Walk upwards until a likely search-result card is found."""
    best = compact(anchor.get_text(" ", strip=True))
    node = anchor
    for _ in range(7):
        node = node.parent
        if node is None:
            break
        text = compact(node.get_text(" ", strip=True))
        if 30 <= len(text) <= 1600:
            best = text
        if EURO.search(text) and POST_TOWN.search(text):
            return text
    return best


def parse_html(path: Path) -> list[dict]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not AD_PATH.search(href):
            continue
        url = urljoin(BASE, href.split("?")[0])
        if url in found:
            continue
        text = best_card_text(a)
        mloc, mprice, marea = POST_TOWN.search(text), EURO.search(text), AREA.search(text)
        title = compact(a.get_text(" ", strip=True))
        if not title or len(title) < 5:
            title = text[:120]
        # Remove common card metadata accidentally captured in the anchor text.
        title = re.split(r"\b\d{4}\s+", title, maxsplit=1)[0].strip(" -|") or "Willhaben listing"
        location = f"{mloc.group(1)} {compact(mloc.group(2))}" if mloc else None
        # Trim text that often follows the town.
        if location:
            location = re.split(r"\s(?:\d[\d.,]*\s*m²|Kauf|Pacht|€)\b", location)[0].strip()
        found[url] = {
            "title": title[:240], "price_eur": parse_number(mprice.group(1)) if mprice else None,
            "area_m2": parse_number(marea.group(1)) if marea else None,
            "location": location, "url": url, "raw_text": text[:1200]
        }
    return list(found.values())


def load_cache(path: Path) -> dict:
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {}


def geocode(listings: list[dict], cache_path: Path, user_agent: str):
    cache = load_cache(cache_path)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    for item in listings:
        q = item.get("location")
        if not q:
            item["geocode_status"] = "missing location"
            continue
        query = f"{q}, Niederösterreich, Österreich"
        key = hashlib.sha256(query.encode()).hexdigest()
        if key in cache:
            result = cache[key]
        else:
            # Nominatim public-service policy: single-threaded and at most 1 request/second.
            response = session.get("https://nominatim.openstreetmap.org/search", params={
                "q": query, "format": "jsonv2", "limit": 1, "countrycodes": "at"
            }, timeout=30)
            response.raise_for_status()
            rows = response.json()
            result = ({"lat": float(rows[0]["lat"]), "lon": float(rows[0]["lon"]),
                       "display_name": rows[0].get("display_name")} if rows else None)
            cache[key] = result
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(1.05)
        if result:
            item.update(latitude=result["lat"], longitude=result["lon"],
                        geocoded_name=result.get("display_name"), geocode_status="ok")
        else:
            item["geocode_status"] = "not found"
    return listings


def money(v):
    return "unknown" if v is None else f"€ {v:,.0f}".replace(",", ".")


def make_map(listings: list[dict], output: Path):
    pts=[x for x in listings if x.get("latitude") is not None]
    center=[sum(x["latitude"] for x in pts)/len(pts), sum(x["longitude"] for x in pts)/len(pts)] if pts else [47.8, 16.05]
    m=folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap", control_scale=True)
    cluster=MarkerCluster(name="Properties").add_to(m)
    for x in pts:
        popup = folium.Popup(
            f'<div style="width:300px"><b>{html_escape(x["title"])}</b><br>'
            f'{html_escape(x.get("location") or "Location unknown")}<br>'
            f'{money(x.get("price_eur"))}'
            f'{(" · " + str(x["area_m2"]) + " m²") if x.get("area_m2") else ""}<br>'
            f'<a href="{html_escape(x["url"])}" target="_blank" rel="noopener">Open advertisement</a></div>',
            max_width=340)
        folium.Marker([x["latitude"], x["longitude"]], tooltip=x["title"], popup=popup,
                      icon=folium.Icon(color="blue", icon="home")).add_to(cluster)
    folium.LayerControl().add_to(m)
    m.fit_bounds([[x["latitude"], x["longitude"]] for x in pts], padding=(30,30)) if len(pts)>1 else None
    m.save(str(output))


def html_escape(s):
    import html
    return html.escape(str(s), quote=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html", type=Path, help="Locally saved Willhaben search-result HTML")
    ap.add_argument("--output", type=Path, default=Path("willhaben_map.html"))
    ap.add_argument("--json", type=Path, default=Path("listings.json"))
    ap.add_argument("--cache", type=Path, default=Path("geocode_cache.json"))
    ap.add_argument("--user-agent", default="DavidWillhabenMapPrototype/0.1 (personal local prototype; contact: replace-with-email@example.com)")
    args=ap.parse_args()
    if not args.html.exists(): ap.error(f"File not found: {args.html}")
    listings=parse_html(args.html)
    if not listings:
        print("No listing links found. The saved page structure may have changed or the page was not fully loaded.", file=sys.stderr)
        print("Scroll through the results before saving, and save as 'Webpage, HTML only'.", file=sys.stderr)
        return 2
    geocode(listings,args.cache,args.user_agent)
    args.json.write_text(json.dumps(listings,ensure_ascii=False,indent=2),encoding="utf-8")
    make_map(listings,args.output)
    ok=sum(x.get("geocode_status")=="ok" for x in listings)
    print(f"Parsed {len(listings)} listings; mapped {ok}. Output: {args.output.resolve()}")
    return 0

if __name__=="__main__": raise SystemExit(main())
