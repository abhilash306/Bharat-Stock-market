"""
MoneyControl Scraper
====================
Fetches three high-value India-specific ownership signals that
Yahoo Finance does NOT provide:

  1. Promoter Holding %          — management skin-in-the-game
  2. FII / DII Holding Change    — institutional smart-money flow
  3. Pledged Shares %            — hidden leverage / distress risk

Strategy
--------
MoneyControl uses Cloudflare + heavy JS rendering, so we use a
three-tier approach:

  Tier 1 — MC Search API (fastest, JSON, no JS needed)
  Tier 2 — MC Shareholding page (BeautifulSoup on cached HTML)
  Tier 3 — Selenium headless browser (fallback for bot-blocked stocks)

All tiers return the same normalised dict schema so the rest of the
system never needs to know which tier was used.

Usage
-----
    mc = MoneyControlScraper()
    data = mc.fetch_ownership_bulk(stock_universe)
    # data = {"TCS": {"promoter_pct": 72.3, ...}, "INFY": {...}, ...}
"""

import logging
import time
import re
import json
import random
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MC_BASE    = "https://www.moneycontrol.com"
MC_SEARCH  = "https://www.moneycontrol.com/mccode/common/autosuggestion_v2.php"
MC_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;"
                       "q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.moneycontrol.com/",
    "DNT":             "1",
    "Connection":      "keep-alive",
}

# Jitter range (seconds) between requests to avoid rate-limiting
REQUEST_DELAY = (1.2, 2.8)

# ─────────────────────────────────────────────────────────────────────────────
# Empty / default result
# ─────────────────────────────────────────────────────────────────────────────

def _empty(symbol: str) -> dict:
    return {
        "symbol":            symbol,
        "promoter_pct":      None,   # % held by promoters (latest quarter)
        "promoter_chg_qoq":  None,   # quarter-on-quarter change in promoter %
        "fii_pct":           None,   # FII holding %
        "fii_chg_qoq":       None,   # QoQ FII change (+ = buying, - = selling)
        "dii_pct":           None,   # DII holding %
        "dii_chg_qoq":       None,   # QoQ DII change
        "pledged_pct":       None,   # % of promoter shares pledged
        "public_pct":        None,   # retail / public holding %
        "mc_slug":           None,   # MoneyControl URL slug
        "fetched_at":        datetime.now().isoformat(),
        "source":            "MoneyControl",
        "fetch_tier":        None,   # "api" | "html" | "selenium" | "failed"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main scraper class
# ─────────────────────────────────────────────────────────────────────────────

class MoneyControlScraper:
    """
    Fetches ownership data from MoneyControl for a universe of NSE stocks.
    Gracefully degrades: API → HTML scrape → Selenium → returns empty dict.
    """

    def __init__(self, use_selenium: bool = False, headless: bool = True):
        """
        Parameters
        ----------
        use_selenium : bool
            Enable Selenium Tier-3 fallback (requires Chrome + chromedriver).
            Set False in CI / serverless environments.
        headless : bool
            Run Chrome in headless mode when Selenium is enabled.
        """
        self.use_selenium = use_selenium
        self.headless     = headless
        self._driver      = None

        self.session = requests.Session()
        self.session.headers.update(MC_HEADERS)
        self._warm_session()

        # Symbol → MC slug cache (avoids repeated search API calls)
        self._slug_cache: dict = {}

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def fetch_ownership_bulk(self, stock_universe: list) -> dict:
        """
        Fetch ownership data for all stocks.

        Parameters
        ----------
        stock_universe : list of dicts, each having at least
            {"nse_symbol": "TCS", "name": "Tata Consultancy Services"}

        Returns
        -------
        dict keyed by nse_symbol → ownership dict
        """
        results = {}
        total = len(stock_universe)
        for i, stock in enumerate(stock_universe):
            sym  = stock["nse_symbol"]
            name = stock.get("name", sym)
            logger.info(f"[MC] Fetching {i+1}/{total}: {sym}")
            try:
                data = self.fetch_ownership_single(sym, name)
                results[sym] = data
            except Exception as e:
                logger.error(f"[MC] Unexpected error for {sym}: {e}")
                results[sym] = _empty(sym)
            # Polite delay between requests
            time.sleep(random.uniform(*REQUEST_DELAY))

        logger.info(f"[MC] Done. {sum(1 for v in results.values() if v['promoter_pct'] is not None)}"
                    f"/{total} stocks fetched successfully.")
        return results

    def fetch_ownership_single(self, nse_symbol: str, company_name: str = "") -> dict:
        """
        Fetch ownership for a single stock.
        Tries Tier 1 → 2 → 3 in order.
        """
        result = _empty(nse_symbol)

        # ── Tier 1: resolve MC slug via search API ─────────────────
        slug = self._resolve_slug(nse_symbol, company_name)
        if not slug:
            result["fetch_tier"] = "failed"
            logger.warning(f"[MC] Could not resolve slug for {nse_symbol}")
            return result

        result["mc_slug"] = slug

        # ── Tier 2: HTML scrape of shareholding page ────────────────
        ownership = self._scrape_shareholding_html(slug)
        if ownership:
            result.update(ownership)
            result["fetch_tier"] = "html"
            return result

        # ── Tier 3: Selenium fallback ───────────────────────────────
        if self.use_selenium:
            ownership = self._scrape_shareholding_selenium(slug)
            if ownership:
                result.update(ownership)
                result["fetch_tier"] = "selenium"
                return result

        result["fetch_tier"] = "failed"
        return result

    # ─────────────────────────────────────────────────────────────────
    # Tier 1 — Search API (resolve slug)
    # ─────────────────────────────────────────────────────────────────

    def _resolve_slug(self, nse_symbol: str, company_name: str) -> str | None:
        """
        Use MC's autocomplete API to find the stock's URL slug.
        e.g. "TCS" → "tata-consultancy-services/TCS"
        """
        if nse_symbol in self._slug_cache:
            return self._slug_cache[nse_symbol]

        # Try by NSE symbol first, then by company name
        queries = [nse_symbol]
        if company_name and company_name != nse_symbol:
            queries.append(company_name[:30])

        for q in queries:
            try:
                resp = self.session.get(
                    MC_SEARCH,
                    params={"classic": "true", "query": q, "type": 1,
                            "format": "json", "ex": "N"},
                    timeout=10,
                )
                resp.raise_for_status()
                # MC returns JSONP-like or plain JSON depending on version
                text = resp.text.strip()
                # Strip JSONP wrapper if present
                if text.startswith("(") and text.endswith(")"):
                    text = text[1:-1]
                items = json.loads(text)
                for item in (items if isinstance(items, list) else []):
                    # Match on NSE symbol
                    if str(item.get("nse_id", "")).upper() == nse_symbol.upper():
                        slug = item.get("link_src", "").strip("/")
                        if slug:
                            self._slug_cache[nse_symbol] = slug
                            return slug
                # Fallback: take first result
                if items and isinstance(items, list) and items[0].get("link_src"):
                    slug = items[0]["link_src"].strip("/")
                    self._slug_cache[nse_symbol] = slug
                    return slug
            except Exception as e:
                logger.debug(f"[MC] Search API error for {q}: {e}")

        # Last resort: construct slug heuristically
        slug = self._heuristic_slug(nse_symbol)
        if slug:
            self._slug_cache[nse_symbol] = slug
        return slug

    def _heuristic_slug(self, nse_symbol: str) -> str | None:
        """
        Known slugs for large-caps as a hardcoded fallback.
        Extend this dict with your own universe.
        """
        known = {
            "TCS":          "tata-consultancy-services/TCS",
            "INFY":         "infosys/IT",
            "RELIANCE":     "reliance-industries/RI",
            "HDFCBANK":     "hdfc-bank/HDF02",
            "ICICIBANK":    "icici-bank/ICI02",
            "SBIN":         "state-bank-of-india/SBI",
            "BHARTIARTL":   "bharti-airtel/BAR",
            "ITC":          "itc/ITC",
            "WIPRO":        "wipro/WIT",
            "SUNPHARMA":    "sun-pharmaceutical-industries/SUNP",
            "MARUTI":       "maruti-suzuki-india/MS",
            "BAJFINANCE":   "bajaj-finance/BAF",
            "HCLTECH":      "hcl-technologies/HCL",
            "TITAN":        "titan-company/TITA",
            "NTPC":         "ntpc/NTPC",
            "POWERGRID":    "power-grid-corporation-of-india/PGRI",
            "ONGC":         "oil-natural-gas-corporation/ONGC",
            "ADANIENT":     "adani-enterprises/ADAE",
            "ULTRACEMCO":   "ultratech-cement/UTC",
            "NESTLEIND":    "nestle-india/NES",
            "AXISBANK":     "axis-bank/AB",
            "KOTAKBANK":    "kotak-mahindra-bank/KTMB",
            "LT":           "larsen-and-toubro/LT",
            "ASIANPAINT":   "asian-paints/AP",
            "HINDUNILVR":   "hindustan-unilever/HLL",
        }
        return known.get(nse_symbol.upper())

    # ─────────────────────────────────────────────────────────────────
    # Tier 2 — HTML scrape (BeautifulSoup)
    # ─────────────────────────────────────────────────────────────────

    def _scrape_shareholding_html(self, slug: str) -> dict | None:
        """
        Scrape the MoneyControl shareholding page for a stock.
        URL pattern: /stocks/companyinfo/shareholding/<slug>/
        """
        url = f"{MC_BASE}/stocks/companyinfo/shareholding/{slug}/"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            if resp.status_code in (403, 429):
                logger.warning(f"[MC] Rate limited / blocked: {url}")
                return None
            soup = BeautifulSoup(resp.text, "lxml")
            return self._parse_shareholding_soup(soup)
        except requests.exceptions.HTTPError as e:
            logger.debug(f"[MC] HTML HTTP error for {slug}: {e}")
            return None
        except Exception as e:
            logger.debug(f"[MC] HTML scrape error for {slug}: {e}")
            return None

    def _parse_shareholding_soup(self, soup: BeautifulSoup) -> dict | None:
        """
        Parse shareholding table from MC HTML.
        Returns partial ownership dict or None if parsing fails.
        """
        try:
            result = {}

            # ── Strategy A: look for structured data table ──────────
            # MC renders quarterly shareholding in a table with class
            # "mctable1" or "shareholding-table"
            tables = soup.find_all("table", class_=re.compile(
                r"mctable|shareholding|sh-table", re.I))

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                    if len(cells) < 2:
                        continue
                    label = cells[0].lower()
                    # Most recent quarter value is cells[1]
                    val = _parse_pct(cells[1])
                    prev_val = _parse_pct(cells[2]) if len(cells) > 2 else None

                    if "promoter" in label and "pledge" not in label:
                        result["promoter_pct"]     = val
                        if prev_val is not None and val is not None:
                            result["promoter_chg_qoq"] = round(val - prev_val, 2)
                    elif "foreign" in label or "fii" in label or "f.i.i" in label:
                        result["fii_pct"]     = val
                        if prev_val is not None and val is not None:
                            result["fii_chg_qoq"] = round(val - prev_val, 2)
                    elif "domestic inst" in label or "dii" in label or "d.i.i" in label:
                        result["dii_pct"]     = val
                        if prev_val is not None and val is not None:
                            result["dii_chg_qoq"] = round(val - prev_val, 2)
                    elif "public" in label and "promoter" not in label:
                        result["public_pct"] = val
                    elif "pledge" in label:
                        result["pledged_pct"] = val

            if result:
                return result

            # ── Strategy B: parse inline JSON (MC embeds data in <script>) ──
            for script in soup.find_all("script"):
                text = script.string or ""
                if "promoterHolding" in text or "shareholdingData" in text:
                    parsed = self._extract_json_from_script(text)
                    if parsed:
                        return parsed

            return None

        except Exception as e:
            logger.debug(f"[MC] Soup parse error: {e}")
            return None

    def _extract_json_from_script(self, script_text: str) -> dict | None:
        """
        Extract shareholding data embedded as JSON in a <script> block.
        MC sometimes serialises data as window.__INITIAL_STATE__ or similar.
        """
        try:
            # Find JSON blob containing shareholding keys
            patterns = [
                r'shareholdingData\s*[:=]\s*(\{.*?\})\s*[,;]',
                r'promoterHolding\s*[:=]\s*(\{.*?\})\s*[,;]',
                r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})',
            ]
            for pattern in patterns:
                match = re.search(pattern, script_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    return self._normalise_json_shareholding(data)
        except Exception as e:
            logger.debug(f"[MC] Script JSON extraction error: {e}")
        return None

    def _normalise_json_shareholding(self, data: dict) -> dict | None:
        """
        Normalise whatever JSON structure MC uses into our standard schema.
        MC changes field names occasionally, so we try multiple key variants.
        """
        result = {}
        try:
            # Promoter holding
            for key in ("promoterHolding", "promoter", "promoter_holding"):
                val = _deep_get(data, key)
                if val is not None:
                    result["promoter_pct"] = _safe_float(val)
                    break

            # FII
            for key in ("fiiHolding", "fii", "foreign_institutional"):
                val = _deep_get(data, key)
                if val is not None:
                    result["fii_pct"] = _safe_float(val)
                    break

            # DII
            for key in ("diiHolding", "dii", "domestic_institutional"):
                val = _deep_get(data, key)
                if val is not None:
                    result["dii_pct"] = _safe_float(val)
                    break

            # Pledged
            for key in ("pledgedShares", "pledged", "pledged_pct", "pledgePercentage"):
                val = _deep_get(data, key)
                if val is not None:
                    result["pledged_pct"] = _safe_float(val)
                    break

        except Exception:
            pass
        return result or None

    # ─────────────────────────────────────────────────────────────────
    # Tier 3 — Selenium headless browser
    # ─────────────────────────────────────────────────────────────────

    def _scrape_shareholding_selenium(self, slug: str) -> dict | None:
        """
        Use Selenium Chrome to scrape a fully JS-rendered MC page.
        Only called when Tier 2 fails AND use_selenium=True.
        """
        try:
            driver = self._get_driver()
            if driver is None:
                return None

            url = f"{MC_BASE}/stocks/companyinfo/shareholding/{slug}/"
            driver.get(url)
            time.sleep(3)   # wait for JS render

            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # Wait for shareholding table to appear
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "table.mctable1, .shareholding-table, table")
                    )
                )
            except Exception:
                pass

            soup = BeautifulSoup(driver.page_source, "lxml")
            return self._parse_shareholding_soup(soup)

        except Exception as e:
            logger.error(f"[MC] Selenium error for {slug}: {e}")
            return None

    def _get_driver(self):
        """Lazy-init Selenium Chrome driver."""
        if self._driver is not None:
            return self._driver
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            opts = Options()
            if self.headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_argument(f"user-agent={MC_HEADERS['User-Agent']}")

            self._driver = webdriver.Chrome(options=opts)
            return self._driver
        except ImportError:
            logger.warning("[MC] selenium not installed — Tier 3 disabled.")
            self.use_selenium = False
            return None
        except Exception as e:
            logger.error(f"[MC] Chrome driver init failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _warm_session(self):
        """Visit MC homepage to get cookies (helps avoid bot detection)."""
        try:
            self.session.get(MC_BASE, timeout=10)
        except Exception:
            pass

    def close(self):
        """Clean up Selenium driver if running."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __del__(self):
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
# Utility functions
# ─────────────────────────────────────────────────────────────────────────────

def _parse_pct(text: str) -> float | None:
    """Extract a percentage float from a table cell string."""
    try:
        cleaned = re.sub(r"[^\d.\-]", "", str(text))
        return round(float(cleaned), 2) if cleaned else None
    except (ValueError, TypeError):
        return None


def _safe_float(v) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _deep_get(d: dict, key: str):
    """Search for a key at any nesting level in a dict."""
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            found = _deep_get(v, key)
            if found is not None:
                return found
    elif isinstance(d, list):
        for item in d:
            found = _deep_get(item, key)
            if found is not None:
                return found
    return None
