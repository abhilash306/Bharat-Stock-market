"""
Groww Scraper
Fetches trending stocks, top gainers/losers, and market sentiment
from Groww's public web pages.

Note: Groww doesn't have an official public API, so we scrape their
publicly accessible pages. This is for educational use only.
"""

import requests
import logging
import json
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

GROWW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://groww.in/",
}

GROWW_BASE = "https://groww.in"


class GrowwScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(GROWW_HEADERS)

    def fetch_trending(self) -> list:
        """
        Scrape Groww's trending/most-searched stocks.
        Returns list of dicts with symbol, name, price, change.
        """
        trending = []
        trending.extend(self._fetch_top_gainers())
        trending.extend(self._fetch_52week_high())
        return trending

    def _fetch_top_gainers(self) -> list:
        """Scrape Groww's top gainers page."""
        results = []
        try:
            url = f"{GROWW_BASE}/stocks/top-gainers"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Groww renders data in Next.js __NEXT_DATA__ script tag
            next_data = soup.find("script", {"id": "__NEXT_DATA__"})
            if next_data:
                payload = json.loads(next_data.string)
                # Navigate the nested JSON to find stock list
                try:
                    page_props = payload["props"]["pageProps"]
                    stocks = (
                        page_props.get("topGainers")
                        or page_props.get("stockList")
                        or page_props.get("data", {}).get("stocks", [])
                    )
                    for s in (stocks or [])[:20]:
                        results.append(self._normalize_groww_stock(s, tag="top_gainer"))
                except (KeyError, TypeError) as e:
                    logger.debug(f"Groww JSON parse error: {e}")
                    # Fall back to HTML parsing
                    results.extend(self._parse_stock_table(soup, tag="top_gainer"))
            else:
                results.extend(self._parse_stock_table(soup, tag="top_gainer"))

        except Exception as e:
            logger.error(f"Groww top gainers error: {e}")

        return [r for r in results if r]

    def _fetch_52week_high(self) -> list:
        """Scrape stocks hitting 52-week highs on Groww."""
        results = []
        try:
            url = f"{GROWW_BASE}/stocks/52-week-high"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            next_data = soup.find("script", {"id": "__NEXT_DATA__"})
            if next_data:
                payload = json.loads(next_data.string)
                try:
                    page_props = payload["props"]["pageProps"]
                    stocks = (
                        page_props.get("stocks")
                        or page_props.get("stockList")
                        or page_props.get("data", {}).get("stocks", [])
                    )
                    for s in (stocks or [])[:15]:
                        item = self._normalize_groww_stock(s, tag="52w_high")
                        if item:
                            results.append(item)
                except (KeyError, TypeError):
                    pass

        except Exception as e:
            logger.error(f"Groww 52-week high error: {e}")

        return results

    def _normalize_groww_stock(self, raw: dict, tag: str = "") -> dict:
        """Normalize a raw Groww stock dict to our standard format."""
        if not raw:
            return {}
        try:
            return {
                "symbol":     raw.get("nseScriptCode") or raw.get("symbol") or raw.get("bseScriptCode", ""),
                "name":       raw.get("companyName") or raw.get("name", ""),
                "price":      raw.get("ltp") or raw.get("currentPrice") or raw.get("price"),
                "change_pct": raw.get("dayChangePerc") or raw.get("percentChange") or raw.get("change_pct"),
                "volume":     raw.get("totalTradedVolume") or raw.get("volume"),
                "tag":        tag,
                "source":     "Groww",
            }
        except Exception:
            return {}

    def _parse_stock_table(self, soup: BeautifulSoup, tag: str) -> list:
        """Generic HTML table parser as last-resort fallback."""
        results = []
        try:
            table = soup.find("table") or soup.find("div", class_=re.compile(r"stock|gainer|table", re.I))
            if not table:
                return []
            rows = table.find_all("tr")[1:21]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    results.append({
                        "symbol":     cols[0].get_text(strip=True),
                        "name":       cols[1].get_text(strip=True) if len(cols) > 1 else "",
                        "price":      cols[2].get_text(strip=True) if len(cols) > 2 else None,
                        "change_pct": cols[3].get_text(strip=True) if len(cols) > 3 else None,
                        "tag":        tag,
                        "source":     "Groww-HTML",
                    })
        except Exception as e:
            logger.debug(f"Groww table parse error: {e}")
        return results

    def fetch_stock_detail(self, symbol: str) -> dict:
        """
        Fetch detailed stock page for a given NSE symbol from Groww.
        Returns fundamentals like P/E, P/B, market cap, etc.
        """
        try:
            url = f"{GROWW_BASE}/stocks/{symbol.lower()}"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            next_data = soup.find("script", {"id": "__NEXT_DATA__"})
            if not next_data:
                return {}

            payload = json.loads(next_data.string)
            page_props = payload.get("props", {}).get("pageProps", {})
            stock_data = page_props.get("stockData") or page_props.get("data") or {}

            fundamentals = stock_data.get("fundamentals") or stock_data.get("keyRatios") or {}

            return {
                "symbol":         symbol,
                "pe":             fundamentals.get("pe") or fundamentals.get("ttmPe"),
                "pb":             fundamentals.get("pb") or fundamentals.get("priceToBook"),
                "roe":            fundamentals.get("roe"),
                "roce":           fundamentals.get("roce"),
                "debt_equity":    fundamentals.get("debtToEquity") or fundamentals.get("d2eRatio"),
                "market_cap":     fundamentals.get("marketCap"),
                "div_yield":      fundamentals.get("dividendYield"),
                "eps":            fundamentals.get("eps") or fundamentals.get("ttmEps"),
                "revenue_growth": fundamentals.get("revenueGrowth"),
                "pat_growth":     fundamentals.get("patGrowth") or fundamentals.get("netProfitGrowth"),
                "source":         "Groww",
            }
        except Exception as e:
            logger.error(f"Groww stock detail error for {symbol}: {e}")
            return {}
