"""
Zerodha Pulse / Varsity Scraper
Fetches market news, educational content tags, and sector news
from Zerodha Pulse (pulse.zerodha.com) — Zerodha's public news aggregator.
"""

import requests
import logging
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

logger = logging.getLogger(__name__)

ZERODHA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://pulse.zerodha.com/",
}

PULSE_BASE = "https://pulse.zerodha.com"
KITE_BASE  = "https://kite.zerodha.com"


class ZerodhaScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(ZERODHA_HEADERS)

    def fetch_news(self) -> list:
        """
        Scrape Zerodha Pulse for latest market news and company-specific news.
        Pulse aggregates news from Economic Times, LiveMint, Business Standard, etc.
        Returns list of news items with company tags and sentiment.
        """
        news_items = []
        news_items.extend(self._fetch_pulse_feed())
        news_items.extend(self._fetch_pulse_company_news())
        return news_items

    def _fetch_pulse_feed(self) -> list:
        """
        Fetch the main Zerodha Pulse news feed.
        Pulse shows market news aggregated from multiple sources.
        """
        results = []
        try:
            resp = self.session.get(PULSE_BASE, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Pulse renders articles in <article> or list items
            articles = (
                soup.find_all("article") or
                soup.find_all("li", class_=re.compile(r"news|article|item", re.I)) or
                soup.find_all("div", class_=re.compile(r"news-item|article-card", re.I))
            )

            for article in articles[:40]:
                try:
                    # Extract title
                    title_tag = (
                        article.find("h2") or article.find("h3") or
                        article.find("a", class_=re.compile(r"title|headline", re.I)) or
                        article.find("a")
                    )
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    if not title or len(title) < 10:
                        continue

                    # Extract link
                    link_tag = article.find("a", href=True)
                    link = link_tag["href"] if link_tag else ""
                    if link and not link.startswith("http"):
                        link = PULSE_BASE + link

                    # Extract date
                    time_tag = article.find("time") or article.find(class_=re.compile(r"date|time", re.I))
                    date_str = ""
                    if time_tag:
                        date_str = time_tag.get("datetime", time_tag.get_text(strip=True))

                    # Extract source
                    source_tag = article.find(class_=re.compile(r"source|publisher", re.I))
                    source = source_tag.get_text(strip=True) if source_tag else "Unknown"

                    # Detect mentioned companies
                    companies = self._extract_company_mentions(title)

                    # Sentiment analysis on headline
                    sentiment = self._classify_sentiment(title)

                    results.append({
                        "title":     title[:250],
                        "link":      link,
                        "date":      date_str or datetime.now().strftime("%Y-%m-%d"),
                        "source":    source,
                        "companies": companies,
                        "sentiment": sentiment,
                        "origin":    "Zerodha Pulse",
                    })
                except Exception as inner_e:
                    logger.debug(f"Pulse article parse error: {inner_e}")
                    continue

        except Exception as e:
            logger.error(f"Zerodha Pulse feed error: {e}")

        return results

    def _fetch_pulse_company_news(self) -> list:
        """
        Fetch news filtered by specific large-cap companies.
        Pulse allows filtering by company tags.
        """
        results = []
        companies_to_check = [
            "reliance", "tcs", "infosys", "hdfc", "icici",
            "sbi", "bharti-airtel", "itc", "wipro", "sun-pharma"
        ]

        for company in companies_to_check[:5]:  # Limit to avoid rate limiting
            try:
                url = f"{PULSE_BASE}/?q={company}"
                resp = self.session.get(url, timeout=12)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                articles = soup.find_all("article") or soup.find_all("li", class_=re.compile(r"news|item", re.I))
                for article in articles[:5]:
                    title_tag = article.find("h2") or article.find("h3") or article.find("a")
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        if title and len(title) > 15:
                            results.append({
                                "title":     title[:250],
                                "date":      datetime.now().strftime("%Y-%m-%d"),
                                "companies": [company.replace("-", " ").title()],
                                "sentiment": self._classify_sentiment(title),
                                "origin":    f"Zerodha Pulse ({company})",
                            })
            except Exception as e:
                logger.debug(f"Pulse company news error for {company}: {e}")
                continue

        return results

    def _extract_company_mentions(self, text: str) -> list:
        """
        Extract mentioned company names from a news headline.
        Uses simple keyword matching against known large-caps.
        """
        companies_map = {
            "Reliance":   ["reliance", "ril"],
            "TCS":        ["tcs", "tata consultancy"],
            "Infosys":    ["infosys", "infy"],
            "HDFC":       ["hdfc bank", "hdfcbank"],
            "ICICI":      ["icici bank", "icicibank"],
            "SBI":        ["sbi", "state bank"],
            "Airtel":     ["airtel", "bharti"],
            "ITC":        ["itc limited", "itc ltd"],
            "Wipro":      ["wipro"],
            "Sun Pharma": ["sun pharma", "sunpharma"],
            "Maruti":     ["maruti", "suzuki"],
            "Bajaj":      ["bajaj finance", "bajfinance"],
            "Adani":      ["adani"],
            "HCL":        ["hcl tech", "hcltech"],
            "Titan":      ["titan"],
        }
        text_lower = text.lower()
        found = []
        for company, keywords in companies_map.items():
            if any(kw in text_lower for kw in keywords):
                found.append(company)
        return found

    def _classify_sentiment(self, text: str) -> str:
        """Simple rule-based sentiment classifier for financial news."""
        text_lower = text.lower()
        positive = [
            "profit", "growth", "surge", "rally", "gain", "rise", "beat",
            "outperform", "upgrade", "buy", "bullish", "record", "high",
            "strong", "robust", "wins", "order", "partnership", "dividend"
        ]
        negative = [
            "loss", "decline", "fall", "drop", "slump", "miss", "downgrade",
            "sell", "bearish", "weak", "concern", "risk", "penalty", "fraud",
            "investigation", "sebi", "default", "crisis", "cut"
        ]
        pos_score = sum(1 for w in positive if w in text_lower)
        neg_score = sum(1 for w in negative if w in text_lower)
        if pos_score > neg_score:
            return "Positive"
        elif neg_score > pos_score:
            return "Negative"
        return "Neutral"
