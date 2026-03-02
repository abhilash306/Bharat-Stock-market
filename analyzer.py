"""
Stock Analyzer & Scoring Engine
Combines data from all scrapers and produces a composite investment score
for each stock using fundamental, technical, and sentiment signals.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StockAnalyzer:
    """
    Multi-factor scoring model for Indian equities.

    Score Components (total 100 points):
      - Fundamentals   : 35 pts  (P/E, ROE, D/E, margins, growth)
      - Technicals     : 25 pts  (RSI, MACD, MA trend, momentum)
      - Sentiment      : 20 pts  (news/announcement impact)
      - Sector Context : 10 pts  (sector momentum)
      - Valuation      : 10 pts  (vs peers, vs fair value)
    """

    SECTOR_WEIGHTS = {
        "IT":             {"base": 70, "trend": "up",   "note": "AI spending boom, deal wins"},
        "Banking":        {"base": 72, "trend": "up",   "note": "Credit growth 14%, NPA declining"},
        "Finance":        {"base": 68, "trend": "up",   "note": "AUM growth, retail lending"},
        "FMCG":           {"base": 60, "trend": "flat", "note": "Rural demand recovery, urban slow"},
        "Energy":         {"base": 74, "trend": "up",   "note": "Strong refining, renewables push"},
        "Pharma":         {"base": 66, "trend": "up",   "note": "USFDA approvals, US market share"},
        "Telecom":        {"base": 70, "trend": "up",   "note": "5G monetization, ARPU expansion"},
        "Auto":           {"base": 62, "trend": "flat", "note": "Premium segment strong, EV transition"},
        "Infrastructure": {"base": 68, "trend": "up",   "note": "Capex cycle, govt orders"},
        "Materials":      {"base": 50, "trend": "down", "note": "China slowdown, margin pressure"},
        "Consumer":       {"base": 64, "trend": "up",   "note": "Premiumization, wedding season"},
        "Conglomerate":   {"base": 48, "trend": "down", "note": "Regulatory overhang"},
        "Real Estate":    {"base": 58, "trend": "flat", "note": "Demand steady, rate sensitivity"},
    }

    def score_and_rank(self, stock_universe: list, all_data: dict) -> list:
        """
        Main method: score every stock and return sorted list.
        """
        yf_data  = all_data.get("yfinance", {})
        nse_anns = all_data.get("nse_announcements", [])
        bse_fils = all_data.get("bse_filings", [])
        groww    = all_data.get("groww_trending", [])
        zerodha  = all_data.get("zerodha_news", [])

        # Build lookup: company name → announcements sentiment
        ann_sentiment = self._build_announcement_sentiment(nse_anns + bse_fils)

        # Groww trending symbols (positive signal)
        groww_symbols = {g.get("symbol", "").upper() for g in groww}

        # Zerodha news mentions
        zerodha_positive = set()
        zerodha_negative = set()
        for news in zerodha:
            for company in news.get("companies", []):
                if news.get("sentiment") == "Positive":
                    zerodha_positive.add(company.upper())
                elif news.get("sentiment") == "Negative":
                    zerodha_negative.add(company.upper())

        scored_stocks = []
        for stock in stock_universe:
            sym = stock["nse_symbol"]
            yf  = yf_data.get(sym, {})

            score_breakdown = {}
            total_score = 0

            # ── 1. Fundamental Score (35 pts) ──────────────────────────
            fund_score = self._score_fundamentals(yf)
            score_breakdown["fundamentals"] = round(fund_score, 1)
            total_score += fund_score * 0.35

            # ── 2. Technical Score (25 pts) ────────────────────────────
            tech_score = self._score_technicals(yf)
            score_breakdown["technicals"] = round(tech_score, 1)
            total_score += tech_score * 0.25

            # ── 3. Sentiment Score (20 pts) ────────────────────────────
            sent_score = 50  # neutral default
            # Check announcement sentiment
            ann_imp = ann_sentiment.get(sym.upper(), "Neutral")
            if ann_imp == "Positive":
                sent_score = 80
            elif ann_imp == "Negative":
                sent_score = 20

            # Groww trending bonus
            if sym.upper() in groww_symbols:
                sent_score = min(100, sent_score + 10)

            # Zerodha news
            name_upper = stock["name"].upper()
            if any(name_upper.startswith(z) for z in zerodha_positive):
                sent_score = min(100, sent_score + 10)
            if any(name_upper.startswith(z) for z in zerodha_negative):
                sent_score = max(0, sent_score - 15)

            score_breakdown["sentiment"] = round(sent_score, 1)
            total_score += sent_score * 0.20

            # ── 4. Sector Score (10 pts) ───────────────────────────────
            sector     = yf.get("sector") or stock.get("sector", "Other")
            sec_config = self.SECTOR_WEIGHTS.get(sector, {"base": 55, "trend": "flat"})
            sec_score  = sec_config["base"]
            if sec_config["trend"] == "up":   sec_score += 5
            if sec_config["trend"] == "down": sec_score -= 5
            score_breakdown["sector"] = round(sec_score, 1)
            total_score += sec_score * 0.10

            # ── 5. Valuation Score (10 pts) ────────────────────────────
            val_score = self._score_valuation(yf, sector)
            score_breakdown["valuation"] = round(val_score, 1)
            total_score += val_score * 0.10

            # ── Final composite score (0–100) ──────────────────────────
            final_score = round(min(100, max(0, total_score)), 1)

            # Build investment recommendation
            recommendation = self._generate_recommendation(final_score, yf, stock)

            scored_stocks.append({
                **stock,
                **yf,  # Merge all YFinance data
                "name":            yf.get("name") or stock["name"],
                "sector":          sector,
                "score":           final_score,
                "score_breakdown": score_breakdown,
                "announcement_impact": ann_imp,
                "recommendation":  recommendation,
                "analyst_rating":  yf.get("recommendation", "N/A"),
                "trend":           yf.get("trend", "N/A"),
                "scored_at":       datetime.now().isoformat(),
            })

        # Sort by score descending
        scored_stocks.sort(key=lambda x: x["score"], reverse=True)

        # Add rank
        for i, s in enumerate(scored_stocks):
            s["rank"] = i + 1

        return scored_stocks

    # ─────────────────────────────────────────────────────────────────
    # Scoring sub-methods
    # ─────────────────────────────────────────────────────────────────

    def _score_fundamentals(self, yf: dict) -> float:
        """Score based on P/E, ROE, D/E, margins, and growth."""
        score = 50.0

        # P/E Ratio
        pe = yf.get("pe")
        if pe:
            if   pe < 15:  score += 15
            elif pe < 25:  score += 8
            elif pe < 35:  score += 0
            elif pe < 50:  score -= 8
            else:          score -= 15

        # Return on Equity
        roe = yf.get("roe")
        if roe:
            if   roe > 25:  score += 12
            elif roe > 15:  score += 6
            elif roe > 8:   score += 0
            elif roe > 0:   score -= 6
            else:           score -= 12

        # Debt to Equity
        de = yf.get("debt_equity")
        if de is not None:
            if   de < 0.3:  score += 8
            elif de < 0.8:  score += 4
            elif de < 1.5:  score -= 3
            else:           score -= 8

        # Profit Margin
        pm = yf.get("profit_margin")
        if pm:
            if   pm > 20:  score += 8
            elif pm > 10:  score += 4
            elif pm > 5:   score += 1
            else:          score -= 4

        # Earnings Growth
        eg = yf.get("earnings_growth")
        if eg:
            if   eg > 30:  score += 10
            elif eg > 15:  score += 5
            elif eg > 0:   score += 2
            else:          score -= 8

        # Revenue Growth
        rg = yf.get("revenue_growth")
        if rg:
            if   rg > 20:  score += 5
            elif rg > 10:  score += 2
            elif rg < 0:   score -= 5

        return min(100, max(0, score))

    def _score_technicals(self, yf: dict) -> float:
        """Score based on RSI, MACD, moving averages, momentum."""
        score = 50.0

        # RSI (Relative Strength Index)
        rsi = yf.get("rsi")
        if rsi:
            if   30 <= rsi <= 50:  score += 12   # Oversold recovery zone
            elif 50 <= rsi <= 65:  score += 8    # Healthy momentum
            elif 65 <= rsi <= 75:  score += 3    # Overbought warning
            elif rsi < 30:         score -= 5    # Deeply oversold
            else:                  score -= 10   # Extremely overbought

        # Moving Average Trend
        if yf.get("above_ma200"): score += 10
        if yf.get("above_ma50"):  score += 6
        if yf.get("above_ma20"):  score += 4

        # MACD Signal
        if yf.get("macd_signal") == "Bullish": score += 8
        else:                                   score -= 5

        # Volume ratio (above average = interest)
        vol_ratio = yf.get("volume_ratio")
        if vol_ratio:
            if   vol_ratio > 1.5:  score += 5
            elif vol_ratio > 1.0:  score += 2
            elif vol_ratio < 0.5:  score -= 5

        # 1-month momentum
        mom = yf.get("momentum_1m")
        if mom:
            if   mom > 10:  score += 8
            elif mom > 3:   score += 4
            elif mom > 0:   score += 1
            elif mom > -5:  score -= 3
            else:           score -= 8

        return min(100, max(0, score))

    def _score_valuation(self, yf: dict, sector: str) -> float:
        """Score based on current valuation vs historical & peers."""
        score = 50.0

        pe = yf.get("pe")
        pb = yf.get("pb")

        # Sector-adjusted P/E benchmarks (Indian market)
        sector_pe_median = {
            "IT": 28, "Banking": 12, "FMCG": 40, "Energy": 14,
            "Pharma": 30, "Auto": 20, "Finance": 22, "Infrastructure": 25,
            "Materials": 15, "Telecom": 35, "Consumer": 42, "Conglomerate": 30,
        }
        median_pe = sector_pe_median.get(sector, 22)
        if pe and median_pe:
            ratio = pe / median_pe
            if   ratio < 0.7:  score += 20   # Deep discount
            elif ratio < 0.9:  score += 10   # Undervalued
            elif ratio < 1.1:  score += 0    # Fair value
            elif ratio < 1.3:  score -= 8    # Premium
            else:              score -= 15   # Overvalued

        # Price-to-book
        if pb:
            if   pb < 1:   score += 10
            elif pb < 2:   score += 5
            elif pb < 4:   score += 0
            elif pb < 6:   score -= 5
            else:          score -= 10

        # Analyst target price vs current
        target = yf.get("target_price")
        price  = yf.get("price")
        if target and price:
            upside = ((target - price) / price) * 100
            if   upside > 25:  score += 15
            elif upside > 10:  score += 8
            elif upside > 0:   score += 3
            elif upside > -10: score -= 5
            else:              score -= 12

        return min(100, max(0, score))

    def _build_announcement_sentiment(self, announcements: list) -> dict:
        """Build a symbol → sentiment dict from all announcements."""
        sentiment_map = {}
        for ann in announcements:
            symbol = (ann.get("symbol") or "").upper()
            if not symbol:
                continue
            impact = ann.get("impact", "Neutral")
            # Positive overrides Neutral; Negative overrides both
            current = sentiment_map.get(symbol, "Neutral")
            if impact == "Negative":
                sentiment_map[symbol] = "Negative"
            elif impact == "Positive" and current == "Neutral":
                sentiment_map[symbol] = "Positive"
        return sentiment_map

    def _generate_recommendation(self, score: float, yf: dict, stock: dict) -> str:
        """Generate a human-readable investment recommendation."""
        pe    = yf.get("pe", 0) or 0
        roe   = yf.get("roe", 0) or 0
        trend = yf.get("trend", "Neutral")
        mom   = yf.get("momentum_1m", 0) or 0
        rec   = yf.get("recommendation", "hold") or "hold"

        if score >= 75:
            base = "Strong Buy"
        elif score >= 65:
            base = "Buy"
        elif score >= 55:
            base = "Hold"
        elif score >= 40:
            base = "Reduce"
        else:
            base = "Avoid"

        # Override with analyst consensus if available
        if rec in ("strongBuy", "strong_buy") and score >= 60:
            base = "Strong Buy"
        elif rec == "sell" and score <= 55:
            base = "Reduce"

        return base
