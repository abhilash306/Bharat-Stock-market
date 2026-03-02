"""
Yahoo Finance Scraper (via yfinance library)
Most reliable data source — provides real-time prices, fundamentals,
historical data, and financial statements for NSE-listed stocks.
"""

import yfinance as yf
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class YFinanceScraper:
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def fetch_all(self, stock_universe: list) -> dict:
        """
        Fetch data for all stocks in parallel using ThreadPoolExecutor.
        Returns dict keyed by NSE symbol.
        """
        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_stock = {
                executor.submit(self._fetch_single, stock): stock
                for stock in stock_universe
            }
            for future in as_completed(future_to_stock):
                stock = future_to_stock[future]
                try:
                    data = future.result(timeout=20)
                    if data:
                        results[stock["nse_symbol"]] = data
                except Exception as e:
                    logger.warning(f"Failed to fetch {stock['symbol']}: {e}")

        logger.info(f"YFinance: fetched {len(results)}/{len(stock_universe)} stocks")
        return results

    def _fetch_single(self, stock: dict) -> dict:
        """
        Fetch comprehensive data for a single stock from Yahoo Finance.
        """
        ticker = yf.Ticker(stock["symbol"])  # e.g., "TCS.NS"

        try:
            info = ticker.info
        except Exception as e:
            logger.warning(f"yfinance info error for {stock['symbol']}: {e}")
            info = {}

        # Historical price data for technical analysis
        hist = pd.DataFrame()
        try:
            hist = ticker.history(period="3mo", interval="1d")
        except Exception:
            pass

        # Calculate technical indicators
        technicals = self._calculate_technicals(hist)

        # Quarterly financials
        financials = {}
        try:
            qf = ticker.quarterly_financials
            if qf is not None and not qf.empty:
                latest_q = qf.iloc[:, 0]
                financials = {
                    "revenue":        latest_q.get("Total Revenue"),
                    "net_income":     latest_q.get("Net Income"),
                    "gross_profit":   latest_q.get("Gross Profit"),
                    "operating_income": latest_q.get("Operating Income"),
                }
        except Exception:
            pass

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close    = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change        = (current_price - prev_close) if (current_price and prev_close) else None
        change_pct    = ((change / prev_close) * 100) if (change and prev_close) else None

        return {
            "symbol":         stock["symbol"],
            "nse_symbol":     stock["nse_symbol"],
            "name":           info.get("longName") or stock["name"],
            "sector":         info.get("sector") or stock.get("sector", ""),
            "industry":       info.get("industry", ""),

            # Price data
            "price":          round(current_price, 2) if current_price else None,
            "prev_close":     round(prev_close, 2) if prev_close else None,
            "change":         round(change, 2) if change else None,
            "change_pct":     round(change_pct, 2) if change_pct else None,
            "open":           info.get("open") or info.get("regularMarketOpen"),
            "day_high":       info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "day_low":        info.get("dayLow") or info.get("regularMarketDayLow"),
            "week52_high":    info.get("fiftyTwoWeekHigh"),
            "week52_low":     info.get("fiftyTwoWeekLow"),
            "volume":         info.get("volume") or info.get("regularMarketVolume"),
            "avg_volume":     info.get("averageVolume"),

            # Market cap
            "market_cap":     info.get("marketCap"),
            "market_cap_cr":  round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else None,  # In crores

            # Valuation ratios
            "pe":             info.get("trailingPE") or info.get("forwardPE"),
            "forward_pe":     info.get("forwardPE"),
            "pb":             info.get("priceToBook"),
            "ps":             info.get("priceToSalesTrailing12Months"),
            "ev_ebitda":      info.get("enterpriseToEbitda"),

            # Profitability
            "roe":            round(info.get("returnOnEquity", 0) * 100, 1) if info.get("returnOnEquity") else None,
            "roa":            round(info.get("returnOnAssets", 0) * 100, 1) if info.get("returnOnAssets") else None,
            "profit_margin":  round(info.get("profitMargins", 0) * 100, 1) if info.get("profitMargins") else None,
            "gross_margin":   round(info.get("grossMargins", 0) * 100, 1) if info.get("grossMargins") else None,

            # Growth
            "revenue_growth": round(info.get("revenueGrowth", 0) * 100, 1) if info.get("revenueGrowth") else None,
            "earnings_growth":round(info.get("earningsGrowth", 0) * 100, 1) if info.get("earningsGrowth") else None,

            # Balance sheet
            "debt_equity":    info.get("debtToEquity"),
            "current_ratio":  info.get("currentRatio"),
            "quick_ratio":    info.get("quickRatio"),
            "total_debt":     info.get("totalDebt"),
            "cash":           info.get("totalCash"),

            # Per share
            "eps":            info.get("trailingEps"),
            "book_value":     info.get("bookValue"),
            "div_yield":      round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "div_rate":       info.get("dividendRate"),

            # Analyst ratings
            "target_price":   info.get("targetMeanPrice"),
            "analyst_count":  info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey"),  # "buy", "hold", "sell"

            # Beta
            "beta":           info.get("beta"),

            # Technical indicators
            **technicals,

            # Quarterly financials
            "quarterly_financials": financials,

            "last_updated": datetime.now().isoformat(),
            "source": "YFinance",
        }

    def _calculate_technicals(self, hist: pd.DataFrame) -> dict:
        """
        Calculate key technical indicators from historical price data.
        """
        if hist.empty or len(hist) < 5:
            return {}

        try:
            close = hist["Close"]

            # Moving Averages
            ma20  = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
            ma50  = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
            ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

            current = close.iloc[-1]

            # RSI (14-day)
            rsi = self._calculate_rsi(close)

            # MACD
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            macd_histogram = (macd_line - signal_line).iloc[-1]

            # Volume trend (current vs 20-day avg)
            vol_ratio = None
            if "Volume" in hist.columns:
                avg_vol = hist["Volume"].rolling(20).mean().iloc[-1]
                curr_vol = hist["Volume"].iloc[-1]
                vol_ratio = round(curr_vol / avg_vol, 2) if avg_vol else None

            # Price vs 52-week high (%)
            high_52 = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
            from_52w_high = round(((current - high_52) / high_52) * 100, 2) if high_52 else None

            # Momentum (1-month return)
            one_month_ago = close.iloc[-21] if len(close) >= 21 else close.iloc[0]
            momentum_1m = round(((current - one_month_ago) / one_month_ago) * 100, 2)

            # 3-month return
            three_months_ago = close.iloc[0]
            momentum_3m = round(((current - three_months_ago) / three_months_ago) * 100, 2)

            # Trend signal
            above_ma20  = current > ma20  if ma20  else None
            above_ma50  = current > ma50  if ma50  else None
            above_ma200 = current > ma200 if ma200 else None
            bullish_count = sum(1 for x in [above_ma20, above_ma50, above_ma200] if x)

            trend = "Bullish" if bullish_count >= 2 else "Bearish" if bullish_count == 0 else "Neutral"

            return {
                "ma20":             round(ma20, 2) if ma20 else None,
                "ma50":             round(ma50, 2) if ma50 else None,
                "ma200":            round(ma200, 2) if ma200 else None,
                "above_ma20":       bool(above_ma20),
                "above_ma50":       bool(above_ma50),
                "above_ma200":      bool(above_ma200),
                "rsi":              rsi,
                "macd_histogram":   round(float(macd_histogram), 3) if not pd.isna(macd_histogram) else None,
                "macd_signal":      "Bullish" if macd_histogram > 0 else "Bearish",
                "volume_ratio":     vol_ratio,
                "from_52w_high_pct": from_52w_high,
                "momentum_1m":      momentum_1m,
                "momentum_3m":      momentum_3m,
                "trend":            trend,
            }
        except Exception as e:
            logger.debug(f"Technicals calculation error: {e}")
            return {}

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> float | None:
        """Calculate RSI indicator."""
        try:
            delta = close.diff()
            gain  = (delta.where(delta > 0, 0)).rolling(period).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs    = gain / loss
            rsi   = (100 - (100 / (1 + rs))).iloc[-1]
            return round(float(rsi), 1) if not pd.isna(rsi) else None
        except Exception:
            return None

    def fetch_market_indices(self) -> dict:
        """Fetch NIFTY 50 and SENSEX index data."""
        indices = {}
        for ticker_sym, name in [("^NSEI", "NIFTY50"), ("^BSESN", "SENSEX"), ("^NSMIDCP", "NIFTY_MIDCAP")]:
            try:
                t = yf.Ticker(ticker_sym)
                info = t.info
                indices[name] = {
                    "value":      info.get("regularMarketPrice"),
                    "change":     info.get("regularMarketChange"),
                    "change_pct": info.get("regularMarketChangePercent"),
                    "open":       info.get("regularMarketOpen"),
                    "high":       info.get("regularMarketDayHigh"),
                    "low":        info.get("regularMarketDayLow"),
                }
            except Exception as e:
                logger.warning(f"Index fetch error for {name}: {e}")
        return indices
