"""
BSE (Bombay Stock Exchange) Scraper
Fetches corporate filings, announcements, and financial results
from BSE's public API.
"""

import requests
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
}

BSE_API = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_BASE = "https://www.bseindia.com"


class BSEScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(BSE_HEADERS)

    def fetch_filings(self, days_back: int = 7) -> list:
        """
        Fetch recent corporate filings from BSE.
        Includes: Board results, AGM notices, investor presentations, etc.
        Returns list of filing dicts.
        """
        filings = []
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        today  = datetime.now().strftime("%Y%m%d")

        try:
            # BSE corporate announcements endpoint
            url = f"{BSE_API}/AnnSubCategoryGetData/w?strCat=-1&strPrevDate={cutoff}&strScrip=&strSearch=P&strToDate={today}&strType=C&PageNo=1"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("Table", []):
                try:
                    detail = item.get("HEADLINE", "") or item.get("NEWSSUB", "")
                    ann_type = item.get("CATEGORYNAME", "Filing")
                    date_str = item.get("NEWS_DT", "")[:10]

                    detail_lower = detail.lower()
                    positive_kw = ["result", "dividend", "profit", "revenue", "order", "approval", "bonus"]
                    negative_kw = ["loss", "penalty", "notice", "investigation", "default", "fraud"]
                    impact = "Neutral"
                    if any(kw in detail_lower for kw in positive_kw):
                        impact = "Positive"
                    elif any(kw in detail_lower for kw in negative_kw):
                        impact = "Negative"

                    filings.append({
                        "symbol":   item.get("SCRIP_CD", ""),
                        "company":  item.get("SLONGNAME", item.get("SCRIP_CD", "")),
                        "ann_type": ann_type,
                        "detail":   detail[:300],
                        "date":     date_str,
                        "impact":   impact,
                        "source":   "BSE",
                        "bse_code": item.get("SCRIP_CD", ""),
                    })
                except Exception as inner_e:
                    logger.debug(f"Skipping BSE filing: {inner_e}")
                    continue

        except Exception as e:
            logger.error(f"BSE filings API error: {e}")
            filings.extend(self._scrape_bse_web())

        return filings

    def _scrape_bse_web(self) -> list:
        """
        Fallback: Scrape BSE website directly for latest announcements.
        Uses BeautifulSoup to parse HTML.
        """
        results = []
        try:
            url = f"{BSE_BASE}/corporates/ann.html"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # BSE announcements table
            table = soup.find("table", {"id": "example1"}) or soup.find("table", class_="table")
            if table:
                rows = table.find_all("tr")[1:51]  # Skip header, max 50
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 4:
                        results.append({
                            "symbol":   cols[0].get_text(strip=True),
                            "company":  cols[1].get_text(strip=True),
                            "ann_type": cols[2].get_text(strip=True),
                            "detail":   cols[3].get_text(strip=True)[:200],
                            "date":     datetime.now().strftime("%Y-%m-%d"),
                            "impact":   "Neutral",
                            "source":   "BSE-Web",
                        })
        except Exception as e:
            logger.error(f"BSE web scrape fallback error: {e}")
        return results

    def fetch_quote(self, bse_code: str) -> dict:
        """
        Fetch real-time quote for a BSE stock.
        bse_code is the 6-digit BSE scrip code (e.g., '500325' for Reliance).
        """
        try:
            url = f"{BSE_API}/getScripHeaderData/w?Debtflag=&scripcode={bse_code}&seriesid="
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return {
                "bse_code":   bse_code,
                "price":      data.get("CurrRate"),
                "change":     data.get("Chg"),
                "change_pct": data.get("PcChg"),
                "high":       data.get("High52"),
                "low":        data.get("Low52"),
                "pe":         data.get("PE"),
                "eps":        data.get("EPS"),
                "source":     "BSE",
            }
        except Exception as e:
            logger.error(f"BSE quote fetch error for {bse_code}: {e}")
            return {}

    def fetch_financial_results(self, bse_code: str) -> dict:
        """
        Fetch latest quarterly financial results for a company.
        Returns revenue, PAT, EPS, YoY growth.
        """
        try:
            url = f"{BSE_API}/StockReachGraph/w?scripcode={bse_code}&flag=Q&fromdate=&todate=&seriesid="
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # Parse the quarterly financials
            results = []
            for quarter in data.get("Table", [])[:4]:
                results.append({
                    "period":   quarter.get("PERIOD"),
                    "revenue":  quarter.get("NETSALES"),
                    "pat":      quarter.get("PAT"),
                    "eps":      quarter.get("BASEPS"),
                })
            return {"quarters": results, "bse_code": bse_code}
        except Exception as e:
            logger.error(f"BSE financial results error for {bse_code}: {e}")
            return {}
