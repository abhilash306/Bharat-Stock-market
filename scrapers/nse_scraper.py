"""
NSE (National Stock Exchange) Scraper
Fetches corporate announcements, board meeting results, and company filings
from NSE's public API endpoints.
"""

import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

NSE_BASE = "https://www.nseindia.com"
NSE_API  = "https://www.nseindia.com/api"


class NSEScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NSE_HEADERS)
        self._init_session()

    def _init_session(self):
        """
        NSE requires a session cookie obtained by visiting the homepage first.
        This sets up the cookie jar.
        """
        try:
            self.session.get(NSE_BASE, timeout=10)
            logger.info("NSE session initialized")
        except Exception as e:
            logger.warning(f"NSE session init failed: {e}")

    def fetch_announcements(self, days_back: int = 7) -> list:
        """
        Fetch recent corporate announcements from NSE.
        Endpoint: /api/corporate-announcements
        Returns list of dicts with keys:
          symbol, company, ann_type, detail, date, impact_estimate
        """
        announcements = []

        try:
            # NSE Corporate Announcements API
            url = f"{NSE_API}/corporate-announcements?index=equities"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            cutoff = datetime.now() - timedelta(days=days_back)

            for item in data:
                try:
                    ann_date_str = item.get("excDate") or item.get("bcast_date") or ""
                    try:
                        ann_date = datetime.strptime(ann_date_str[:10], "%d-%b-%Y")
                    except Exception:
                        try:
                            ann_date = datetime.strptime(ann_date_str[:10], "%Y-%m-%d")
                        except Exception:
                            ann_date = datetime.now()

                    if ann_date < cutoff:
                        continue

                    ann_type = item.get("subject", "General")
                    detail   = item.get("desc") or item.get("details") or ann_type

                    # Simple positive/negative sentiment detection
                    positive_keywords = ["dividend", "bonus", "buyback", "profit", "revenue up",
                                         "acquisition", "order win", "approval", "upgrade"]
                    negative_keywords = ["loss", "penalty", "sebi notice", "downgrade",
                                         "investigation", "fraud", "default"]
                    detail_lower = detail.lower()
                    impact = "Neutral"
                    if any(kw in detail_lower for kw in positive_keywords):
                        impact = "Positive"
                    elif any(kw in detail_lower for kw in negative_keywords):
                        impact = "Negative"

                    announcements.append({
                        "symbol":  item.get("symbol", ""),
                        "company": item.get("comp", item.get("symbol", "")),
                        "ann_type": ann_type,
                        "detail":  detail[:300],
                        "date":    ann_date.strftime("%Y-%m-%d"),
                        "impact":  impact,
                        "source":  "NSE",
                    })
                except Exception as inner_e:
                    logger.debug(f"Skipping NSE announcement item: {inner_e}")
                    continue

        except Exception as e:
            logger.error(f"NSE announcements fetch error: {e}")
            # Fallback to board meetings endpoint
            announcements.extend(self._fetch_board_meetings())

        return announcements

    def _fetch_board_meetings(self) -> list:
        """Fallback: fetch upcoming/recent board meeting results."""
        results = []
        try:
            url = f"{NSE_API}/corporate-board-meetings?index=equities"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data[:30]:
                results.append({
                    "symbol":   item.get("symbol", ""),
                    "company":  item.get("company", item.get("symbol", "")),
                    "ann_type": "Board Meeting",
                    "detail":   item.get("purpose", "Board meeting scheduled"),
                    "date":     item.get("bm_date", "")[:10],
                    "impact":   "Neutral",
                    "source":   "NSE",
                })
        except Exception as e:
            logger.error(f"NSE board meetings fallback error: {e}")
        return results

    def fetch_quote(self, symbol: str) -> dict:
        """
        Fetch real-time quote for a single NSE symbol.
        e.g. symbol = 'TCS'
        """
        try:
            url = f"{NSE_API}/quote-equity?symbol={symbol}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            price_info = data.get("priceInfo", {})
            metadata   = data.get("metadata", {})
            return {
                "symbol":       symbol,
                "price":        price_info.get("lastPrice"),
                "change":       price_info.get("change"),
                "change_pct":   price_info.get("pChange"),
                "high":         price_info.get("intraDayHighLow", {}).get("max"),
                "low":          price_info.get("intraDayHighLow", {}).get("min"),
                "week52_high":  price_info.get("weekHighLow", {}).get("max"),
                "week52_low":   price_info.get("weekHighLow", {}).get("min"),
                "volume":       metadata.get("totalTradedVolume"),
                "market_cap":   metadata.get("pdSectorPe"),
                "pe":           metadata.get("pdSymbolPe"),
                "source":       "NSE",
            }
        except Exception as e:
            logger.error(f"NSE quote fetch error for {symbol}: {e}")
            return {}

    def fetch_market_status(self) -> dict:
        """Check if market is open/closed."""
        try:
            resp = self.session.get(f"{NSE_API}/marketStatus", timeout=8)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"NSE market status error: {e}")
            return {}
