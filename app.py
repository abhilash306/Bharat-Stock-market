"""
Bharat Market Intelligence - ALL-IN-ONE Server
Just run: python app.py
No other files needed!
"""

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────
from flask import Flask, jsonify
from flask_cors import CORS
import threading, time, logging, requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# STOCK UNIVERSE (Nifty 50 Large Caps)
# ─────────────────────────────────────────────
STOCK_UNIVERSE = [
    {"symbol": "RELIANCE.NS",  "nse_symbol": "RELIANCE",  "name": "Reliance Industries",       "sector": "Energy"},
    {"symbol": "TCS.NS",       "nse_symbol": "TCS",        "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK.NS",  "nse_symbol": "HDFCBANK",   "name": "HDFC Bank",                 "sector": "Banking"},
    {"symbol": "INFY.NS",      "nse_symbol": "INFY",       "name": "Infosys",                   "sector": "IT"},
    {"symbol": "ICICIBANK.NS", "nse_symbol": "ICICIBANK",  "name": "ICICI Bank",                "sector": "Banking"},
    {"symbol": "HINDUNILVR.NS","nse_symbol": "HINDUNILVR", "name": "Hindustan Unilever",        "sector": "FMCG"},
    {"symbol": "SBIN.NS",      "nse_symbol": "SBIN",       "name": "State Bank of India",       "sector": "Banking"},
    {"symbol": "BHARTIARTL.NS","nse_symbol": "BHARTIARTL", "name": "Bharti Airtel",             "sector": "Telecom"},
    {"symbol": "ITC.NS",       "nse_symbol": "ITC",        "name": "ITC Limited",               "sector": "FMCG"},
    {"symbol": "KOTAKBANK.NS", "nse_symbol": "KOTAKBANK",  "name": "Kotak Mahindra Bank",       "sector": "Banking"},
    {"symbol": "LT.NS",        "nse_symbol": "LT",         "name": "Larsen & Toubro",           "sector": "Infrastructure"},
    {"symbol": "WIPRO.NS",     "nse_symbol": "WIPRO",      "name": "Wipro",                     "sector": "IT"},
    {"symbol": "AXISBANK.NS",  "nse_symbol": "AXISBANK",   "name": "Axis Bank",                 "sector": "Banking"},
    {"symbol": "MARUTI.NS",    "nse_symbol": "MARUTI",     "name": "Maruti Suzuki",             "sector": "Auto"},
    {"symbol": "SUNPHARMA.NS", "nse_symbol": "SUNPHARMA",  "name": "Sun Pharmaceutical",        "sector": "Pharma"},
    {"symbol": "TITAN.NS",     "nse_symbol": "TITAN",      "name": "Titan Company",             "sector": "Consumer"},
    {"symbol": "BAJFINANCE.NS","nse_symbol": "BAJFINANCE", "name": "Bajaj Finance",             "sector": "Finance"},
    {"symbol": "HCLTECH.NS",   "nse_symbol": "HCLTECH",    "name": "HCL Technologies",          "sector": "IT"},
    {"symbol": "ULTRACEMCO.NS","nse_symbol": "ULTRACEMCO", "name": "UltraTech Cement",          "sector": "Materials"},
    {"symbol": "ADANIENT.NS",  "nse_symbol": "ADANIENT",   "name": "Adani Enterprises",         "sector": "Conglomerate"},
]

# ─────────────────────────────────────────────
# CACHE (in-memory)
# ─────────────────────────────────────────────
_cache = {}
_cache_lock = threading.RLock()

def cache_set(key, value):
    with _cache_lock:
        _cache[key] = {"value": value, "set_at": time.time()}

def cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        return entry["value"] if entry else None

# ─────────────────────────────────────────────
# NSE SCRAPER
# ─────────────────────────────────────────────
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
}

def fetch_nse_announcements():
    announcements = []
    try:
        session = requests.Session()
        session.headers.update(NSE_HEADERS)
        session.get("https://www.nseindia.com", timeout=10)  # Get cookie first

        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        cutoff = datetime.now() - timedelta(days=7)
        for item in data[:50]:
            try:
                date_str = (item.get("excDate") or item.get("bcast_date") or "")[:10]
                try:
                    ann_date = datetime.strptime(date_str, "%d-%b-%Y")
                except:
                    try:
                        ann_date = datetime.strptime(date_str, "%Y-%m-%d")
                    except:
                        ann_date = datetime.now()

                if ann_date < cutoff:
                    continue

                detail = (item.get("desc") or item.get("subject") or "")[:300]
                detail_lower = detail.lower()
                positive_kw = ["dividend", "bonus", "buyback", "profit", "revenue up", "order", "approval"]
                negative_kw = ["loss", "penalty", "notice", "investigation", "default", "fraud"]
                impact = "Neutral"
                if any(k in detail_lower for k in positive_kw): impact = "Positive"
                elif any(k in detail_lower for k in negative_kw): impact = "Negative"

                announcements.append({
                    "symbol":   item.get("symbol", ""),
                    "company":  item.get("comp", item.get("symbol", "")),
                    "ann_type": item.get("subject", "General"),
                    "category": normalize_category(item.get("subject", "General")),
                    "detail":   detail,
                    "date":     ann_date.strftime("%Y-%m-%d"),
                    "impact":   impact,
                    "source":   "NSE",
                })
            except:
                continue
        logger.info(f"NSE: {len(announcements)} announcements fetched")
    except Exception as e:
        logger.error(f"NSE fetch error: {e}")
    return announcements

# ─────────────────────────────────────────────
# BSE SCRAPER
# ─────────────────────────────────────────────
def fetch_bse_filings():
    filings = []
    try:
        today   = datetime.now().strftime("%Y%m%d")
        cutoff  = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?strCat=-1&strPrevDate={cutoff}&strScrip=&strSearch=P&strToDate={today}&strType=C&PageNo=1"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("Table", [])[:40]:
            detail = (item.get("HEADLINE") or item.get("NEWSSUB") or "")[:300]
            detail_lower = detail.lower()
            positive_kw = ["result", "dividend", "profit", "revenue", "order", "approval", "bonus"]
            negative_kw = ["loss", "penalty", "notice", "investigation", "default", "fraud"]
            impact = "Neutral"
            if any(k in detail_lower for k in positive_kw): impact = "Positive"
            elif any(k in detail_lower for k in negative_kw): impact = "Negative"

            filings.append({
                "symbol":   str(item.get("SCRIP_CD", "")),
                "company":  item.get("SLONGNAME", ""),
                "ann_type": item.get("CATEGORYNAME", "Filing"),
                "category": normalize_category(item.get("CATEGORYNAME", "Filing")),
                "detail":   detail,
                "date":     (item.get("NEWS_DT") or "")[:10],
                "impact":   impact,
                "source":   "BSE",
            })
        logger.info(f"BSE: {len(filings)} filings fetched")
    except Exception as e:
        logger.error(f"BSE fetch error: {e}")
    return filings

# ─────────────────────────────────────────────
# ZERODHA PULSE SCRAPER
# ─────────────────────────────────────────────
COMPANY_KEYWORDS = {
    "Reliance": ["reliance", "ril"], "TCS": ["tcs", "tata consultancy"],
    "Infosys": ["infosys", "infy"], "HDFC": ["hdfc bank"],
    "ICICI": ["icici bank"], "SBI": ["sbi", "state bank"],
    "Airtel": ["airtel", "bharti"], "ITC": ["itc limited", " itc "],
    "Wipro": ["wipro"], "Sun Pharma": ["sun pharma", "sunpharma"],
    "Maruti": ["maruti"], "Bajaj Finance": ["bajaj finance"],
    "Adani": ["adani"], "HCL": ["hcl tech"], "Titan": ["titan"],
}

def classify_sentiment(text):
    t = text.lower()
    pos = ["profit","growth","surge","rally","gain","rise","beat","record","strong","order","dividend","win"]
    neg = ["loss","decline","fall","drop","slump","miss","weak","penalty","fraud","investigation","default"]
    if sum(1 for w in pos if w in t) > sum(1 for w in neg if w in t): return "Positive"
    if sum(1 for w in neg if w in t) > sum(1 for w in pos if w in t): return "Negative"
    return "Neutral"

def extract_companies(text):
    t = text.lower()
    return [c for c, kws in COMPANY_KEYWORDS.items() if any(k in t for k in kws)]

def fetch_zerodha_news():
    news = []
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://pulse.zerodha.com/"}
        resp = requests.get("https://pulse.zerodha.com", headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        articles = soup.find_all("article") or soup.find_all("li", class_=lambda c: c and "item" in c)
        for article in articles[:30]:
            title_tag = article.find("h2") or article.find("h3") or article.find("a")
            if not title_tag: continue
            title = title_tag.get_text(strip=True)
            if len(title) < 15: continue
            news.append({
                "title":     title[:250],
                "companies": extract_companies(title),
                "sentiment": classify_sentiment(title),
                "date":      datetime.now().strftime("%Y-%m-%d"),
                "source":    "Zerodha Pulse",
            })
        logger.info(f"Zerodha: {len(news)} news items fetched")
    except Exception as e:
        logger.error(f"Zerodha fetch error: {e}")
    return news

# ─────────────────────────────────────────────
# YAHOO FINANCE SCRAPER
# ─────────────────────────────────────────────
def calc_rsi(close, period=14):
    try:
        delta = close.diff()
        gain  = delta.where(delta > 0, 0).rolling(period).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs    = gain / loss
        rsi   = (100 - (100 / (1 + rs))).iloc[-1]
        return round(float(rsi), 1) if not pd.isna(rsi) else None
    except: return None

def fetch_single_stock(stock):
    try:
        ticker = yf.Ticker(stock["symbol"])
        info   = ticker.info or {}
        hist   = ticker.history(period="3mo", interval="1d")

        # Price
        price     = info.get("currentPrice") or info.get("regularMarketPrice")
        prev      = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change    = round(price - prev, 2) if price and prev else None
        change_pct= round((change / prev) * 100, 2) if change and prev else None

        # Technicals
        tech = {}
        if not hist.empty and len(hist) >= 5:
            close  = hist["Close"]
            curr   = float(close.iloc[-1])
            ma20   = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
            ma50   = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
            ma200  = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
            ema12  = close.ewm(span=12).mean()
            ema26  = close.ewm(span=26).mean()
            macd   = (ema12 - ema26 - (ema12 - ema26).ewm(span=9).mean()).iloc[-1]
            mom1m  = round(((curr - float(close.iloc[-21])) / float(close.iloc[-21])) * 100, 2) if len(close) >= 21 else None
            tech   = {
                "ma20": round(ma20, 2) if ma20 else None,
                "ma50": round(ma50, 2) if ma50 else None,
                "ma200": round(ma200, 2) if ma200 else None,
                "above_ma20":  curr > ma20  if ma20  else False,
                "above_ma50":  curr > ma50  if ma50  else False,
                "above_ma200": curr > ma200 if ma200 else False,
                "rsi":         calc_rsi(close),
                "macd_signal": "Bullish" if (not pd.isna(macd) and macd > 0) else "Bearish",
                "momentum_1m": mom1m,
                "trend":       "Bullish" if sum([curr > ma20 if ma20 else False,
                                                  curr > ma50 if ma50 else False,
                                                  curr > ma200 if ma200 else False]) >= 2 else "Bearish",
            }

        roe = info.get("returnOnEquity")
        
        # Build sparkline from last 30 days
        sparkline = []
        if not hist.empty:
            recent = hist["Close"].tail(30)
            sparkline = [{"v": round(float(v), 2)} for v in recent]
        
        return {
            "symbol":       stock["symbol"],
            "nse_symbol":   stock["nse_symbol"],
            "name":         info.get("longName") or stock["name"],
            "sector":       info.get("sector") or stock["sector"],
            "price":        round(price, 2) if price else None,
            "change":       change,
            "change_pct":   change_pct,
            "week52_high":  info.get("fiftyTwoWeekHigh"),
            "week52_low":   info.get("fiftyTwoWeekLow"),
            "volume":       info.get("volume"),
            "market_cap":   info.get("marketCap"),
            "market_cap_cr":round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else None,
            "pe":           round(float(info.get("trailingPE") or info.get("forwardPE") or 0), 1) or None,
            "pb":           info.get("priceToBook"),
            "roe":          round(roe * 100, 1) if roe else None,
            "profit_margin":round((info.get("profitMargins") or 0) * 100, 1),
            "revenue_growth":round((info.get("revenueGrowth") or 0) * 100, 1),
            "earnings_growth":round((info.get("earningsGrowth") or 0) * 100, 1),
            "debt_equity":  info.get("debtToEquity"),
            "eps":          info.get("trailingEps"),
            "div_yield":    round((info.get("dividendYield") or 0) * 100, 2),
            "target_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
            "beta":         info.get("beta"),
            "sparkline":    sparkline,
            **tech,
        }
    except Exception as e:
        logger.warning(f"YFinance error for {stock['symbol']}: {e}")
        return None

def fetch_all_stocks():
    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_single_stock, s): s for s in STOCK_UNIVERSE}
        for f in as_completed(futures):
            stock = futures[f]
            try:
                data = f.result(timeout=25)
                if data:
                    results[stock["nse_symbol"]] = data
            except Exception as e:
                logger.warning(f"Timeout/error for {stock['symbol']}: {e}")
    logger.info(f"YFinance: {len(results)}/{len(STOCK_UNIVERSE)} stocks fetched")
    return results

# ─────────────────────────────────────────────
# MARKET INDICES
# ─────────────────────────────────────────────
def fetch_indices():
    indices = {}
    for sym, name in [("^NSEI", "NIFTY50"), ("^BSESN", "SENSEX")]:
        try:
            t    = yf.Ticker(sym)
            info = t.info
            indices[name] = {
                "value":      info.get("regularMarketPrice"),
                "change":     info.get("regularMarketChange"),
                "change_pct": round(info.get("regularMarketChangePercent", 0), 2),
            }
        except Exception as e:
            logger.warning(f"Index error {name}: {e}")
    return indices

# ─────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────
SECTOR_BASE = {
    "IT": 72, "Banking": 70, "Finance": 68, "FMCG": 60,
    "Energy": 74, "Pharma": 66, "Telecom": 70, "Auto": 62,
    "Infrastructure": 68, "Materials": 50, "Consumer": 64, "Conglomerate": 48,
}
SECTOR_TREND = {
    "IT": "up", "Banking": "up", "Energy": "up", "Telecom": "up",
    "Infrastructure": "up", "Finance": "up", "Consumer": "up",
    "FMCG": "flat", "Auto": "flat", "Pharma": "up",
    "Materials": "down", "Conglomerate": "down",
}
SECTOR_NOTE = {
    "IT": "AI boom, strong deal wins", "Banking": "Credit growth 14%, NPA falling",
    "Energy": "Refining margins strong", "Telecom": "5G monetization, ARPU up",
    "FMCG": "Rural demand recovering", "Pharma": "USFDA approvals rising",
    "Auto": "Premium strong, EV shift", "Finance": "AUM growth, retail lending",
    "Infrastructure": "Govt capex cycle", "Materials": "China slowdown pressure",
    "Consumer": "Premiumization trend", "Conglomerate": "Regulatory overhang",
}
SECTOR_PE = {
    "IT": 28, "Banking": 12, "FMCG": 40, "Energy": 14,
    "Pharma": 30, "Auto": 20, "Finance": 22, "Infrastructure": 25,
    "Materials": 15, "Telecom": 35, "Consumer": 42, "Conglomerate": 30,
}
SECTOR_COLOR = {
    "IT": "#00e5ff", "Banking": "#00e676", "Energy": "#ffab00",
    "FMCG": "#ff6d00", "Pharma": "#e040fb", "Telecom": "#40c4ff",
    "Auto": "#ffca28", "Finance": "#69f0ae", "Infrastructure": "#f48fb1",
    "Materials": "#ff5252", "Consumer": "#b388ff", "Conglomerate": "#ff8a65",
}

def normalize_category(text):
    t = (text or "").lower()
    if "result" in t or "financial" in t: return "Results"
    if "dividend" in t: return "Dividend"
    if "sebi" in t or "penalty" in t: return "SEBI"
    if "order" in t or "contract" in t: return "Order"
    if "rating" in t: return "Rating"
    if "bulk" in t or "deal" in t: return "Bulk Deal"
    if "board" in t: return "Board"
    if "shareholding" in t: return "Shareholding"
    if "management" in t: return "Management"
    return "Regulatory"

def score_stock(stock, yf_data, ann_sentiment, zerodha_pos, zerodha_neg):
    d = yf_data.get(stock["nse_symbol"], {})
    sector = d.get("sector") or stock["sector"]

    # 1. Fundamentals (35%)
    f = 50.0
    pe = d.get("pe")
    if pe:
        if pe < 15: f += 15
        elif pe < 25: f += 8
        elif pe < 35: f += 0
        elif pe < 50: f -= 8
        else: f -= 15
    roe = d.get("roe")
    if roe:
        if roe > 25: f += 12
        elif roe > 15: f += 6
        elif roe > 0: f -= 2
        else: f -= 12
    de = d.get("debt_equity")
    if de is not None:
        if de < 30: f += 8
        elif de < 80: f += 4
        elif de < 150: f -= 3
        else: f -= 8
    pm = d.get("profit_margin")
    if pm:
        if pm > 20: f += 8
        elif pm > 10: f += 4
        elif pm < 0: f -= 8
    eg = d.get("earnings_growth")
    if eg:
        if eg > 30: f += 10
        elif eg > 15: f += 5
        elif eg < 0: f -= 8

    # 2. Technicals (25%)
    t = 50.0
    rsi = d.get("rsi")
    if rsi:
        if 30 <= rsi <= 50: t += 12
        elif 50 <= rsi <= 65: t += 8
        elif rsi < 30: t -= 5
        elif rsi > 75: t -= 10
    if d.get("above_ma200"): t += 10
    if d.get("above_ma50"):  t += 6
    if d.get("above_ma20"):  t += 4
    if d.get("macd_signal") == "Bullish": t += 8
    else: t -= 5
    mom = d.get("momentum_1m")
    if mom:
        if mom > 10: t += 8
        elif mom > 3: t += 4
        elif mom < -5: t -= 8

    # 3. Sentiment (20%)
    s = 50.0
    sym_upper = stock["nse_symbol"].upper()
    ann_imp = ann_sentiment.get(sym_upper, "Neutral")
    if ann_imp == "Positive": s = 80
    elif ann_imp == "Negative": s = 20
    name_upper = stock["name"].upper()
    if any(name_upper.startswith(z.upper()) for z in zerodha_pos): s = min(100, s + 10)
    if any(name_upper.startswith(z.upper()) for z in zerodha_neg): s = max(0, s - 15)

    # 4. Sector (10%)
    sec_base  = SECTOR_BASE.get(sector, 55)
    sec_trend = SECTOR_TREND.get(sector, "flat")
    sec_score = sec_base + (5 if sec_trend == "up" else -5 if sec_trend == "down" else 0)

    # 5. Valuation (10%)
    v = 50.0
    median_pe = SECTOR_PE.get(sector, 22)
    if pe and median_pe:
        ratio = pe / median_pe
        if ratio < 0.7: v += 20
        elif ratio < 0.9: v += 10
        elif ratio < 1.1: v += 0
        elif ratio < 1.3: v -= 8
        else: v -= 15
    target = d.get("target_price")
    price  = d.get("price")
    if target and price:
        upside = ((target - price) / price) * 100
        if upside > 25: v += 15
        elif upside > 10: v += 8
        elif upside > 0: v += 3
        else: v -= 8

    total = (
        min(100, max(0, f)) * 0.35 +
        min(100, max(0, t)) * 0.25 +
        min(100, max(0, s)) * 0.20 +
        min(100, max(0, sec_score)) * 0.10 +
        min(100, max(0, v)) * 0.10
    )
    total = round(min(100, max(0, total)), 1)

    rec = "Avoid"
    if total >= 75: rec = "Strong Buy"
    elif total >= 65: rec = "Buy"
    elif total >= 55: rec = "Hold"
    elif total >= 40: rec = "Reduce"

    return {
        **stock, **d,
        "name":   d.get("name") or stock["name"],
        "sector": sector,
        "sectorColor": SECTOR_COLOR.get(sector, "#667788"),
        "score":  total,
        "score_breakdown": {
            "fundamentals": round(min(100, max(0, f)), 1),
            "technicals":   round(min(100, max(0, t)), 1),
            "sentiment":    round(min(100, max(0, s)), 1),
            "sector":       round(min(100, max(0, sec_score)), 1),
            "valuation":    round(min(100, max(0, v)), 1),
        },
        "announcement_impact": ann_imp,
        "sector_note":       SECTOR_NOTE.get(sector, ""),
        "recommendation":    rec,
    }

# ─────────────────────────────────────────────
# MAIN DATA REFRESH
# ─────────────────────────────────────────────
def refresh_all_data():
    logger.info("🔄 Starting full data refresh...")

    # Fetch from all sources in parallel
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_yf    = ex.submit(fetch_all_stocks)
        f_nse   = ex.submit(fetch_nse_announcements)
        f_bse   = ex.submit(fetch_bse_filings)
        f_pulse = ex.submit(fetch_zerodha_news)
        f_idx   = ex.submit(fetch_indices)

        yf_data  = f_yf.result()
        nse_anns = f_nse.result()
        bse_fils = f_bse.result()
        pulse    = f_pulse.result()
        indices  = f_idx.result()

    # Build sentiment lookups
    ann_sentiment = {}
    for ann in nse_anns + bse_fils:
        sym = (ann.get("symbol") or "").upper()
        if not sym: continue
        imp = ann.get("impact", "Neutral")
        if imp == "Negative": ann_sentiment[sym] = "Negative"
        elif imp == "Positive" and ann_sentiment.get(sym) != "Negative":
            ann_sentiment[sym] = "Positive"

    zerodha_pos = set()
    zerodha_neg = set()
    for news in pulse:
        for company in news.get("companies", []):
            if news.get("sentiment") == "Positive": zerodha_pos.add(company)
            elif news.get("sentiment") == "Negative": zerodha_neg.add(company)

    # Score all stocks
    scored = [
        score_stock(s, yf_data, ann_sentiment, zerodha_pos, zerodha_neg)
        for s in STOCK_UNIVERSE
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(scored):
        s["rank"] = i + 1

    result = {
        "ranked_stocks":      scored,
        "top_10":             scored[:10],
        "nse_announcements":  nse_anns,
        "bse_filings":        bse_fils,
        "zerodha_news":       pulse,
        "indices":            indices,
        "last_updated":       datetime.now().isoformat(),
        "status":             "success",
        "stocks_analyzed":    len(scored),
    }
    cache_set("market_data", result)
    logger.info(f"✅ Refresh done. Top pick: {scored[0]['name'] if scored else 'N/A'} ({scored[0]['score'] if scored else 0})")

def auto_refresh_loop():
    while True:
        try:
            refresh_all_data()
        except Exception as e:
            logger.error(f"Refresh error: {e}")
        logger.info("⏳ Next refresh in 5 minutes...")
        time.sleep(300)

# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────
@app.route("/api/health")
def health():
    data = cache_get("market_data")
    return jsonify({
        "status": "ok",
        "data_ready": data is not None,
        "last_updated": data.get("last_updated") if data else None,
        "timestamp": datetime.now().isoformat(),
    })

@app.route("/api/refresh", methods=["POST", "GET"])
def manual_refresh():
    threading.Thread(target=refresh_all_data, daemon=True).start()
    return jsonify({"status": "refresh_started"})

@app.route("/api/market-data")
def get_market_data():
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading", "message": "Data loading, please wait 30 seconds and refresh..."}), 202
    return jsonify(data)

@app.route("/api/top10")
def get_top10():
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading"}), 202
    return jsonify({"top_10": data.get("top_10", []), "last_updated": data.get("last_updated")})

@app.route("/api/announcements")
def get_announcements():
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading"}), 202
    return jsonify({
        "nse":   data.get("nse_announcements", []),
        "bse":   data.get("bse_filings", []),
        "pulse": data.get("zerodha_news", []),
        "last_updated": data.get("last_updated"),
    })

@app.route("/api/indices")
def get_indices():
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading"}), 202
    return jsonify(data.get("indices", {}))

@app.route("/api/sectors")
def get_sectors():
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading"}), 202
    sectors = {}
    for s in data.get("ranked_stocks", []):
        sec = s.get("sector", "Other")
        if sec not in sectors:
            sectors[sec] = {"stocks": [], "avg_score": 0, "note": SECTOR_NOTE.get(sec, "")}
        sectors[sec]["stocks"].append(s["name"])
        sectors[sec]["avg_score"] += s.get("score", 0)
    for sec in sectors:
        n = len(sectors[sec]["stocks"])
        sectors[sec]["avg_score"] = round(sectors[sec]["avg_score"] / n, 1)
        sectors[sec]["count"] = n
    return jsonify(sectors)

@app.route("/api/stock/<symbol>")
def get_stock(symbol):
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading"}), 202
    match = next((s for s in data.get("ranked_stocks", []) if s.get("nse_symbol", "").upper() == symbol.upper()), None)
    if not match:
        return jsonify({"error": "Stock not found"}), 404
    return jsonify(match)

# Simple HTML status page at root
@app.route("/")
def index():
    data = cache_get("market_data")
    ready = data is not None
    top = data.get("top_10", []) if data else []
    rows = "".join(
        f"<tr><td>#{s['rank']}</td><td><b>{s['name']}</b></td><td>{s.get('sector','')}</td>"
        f"<td>₹{s.get('price','N/A')}</td><td style='color:{'green' if (s.get('change_pct') or 0)>=0 else 'red'}'>"
        f"{s.get('change_pct','N/A')}%</td><td><b>{s.get('score','N/A')}</b></td>"
        f"<td style='color:green'><b>{s.get('recommendation','')}</b></td></tr>"
        for s in top
    )
    status_color = "green" if ready else "orange"
    status_text  = f"✅ Data ready — last updated {data.get('last_updated','')[:19]}" if ready else "⏳ Loading data... please wait ~30 seconds"
    return f"""
    <!DOCTYPE html><html><head>
    <title>Bharat Market Intelligence</title>
    <meta http-equiv="refresh" content="30">
    <style>
      body {{ font-family: Arial, sans-serif; background: #0a0f1e; color: #c8d8e8; padding: 30px; }}
      h1 {{ color: #00bfff; }} h2 {{ color: #00e676; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
      th {{ background: #1a2f4a; padding: 12px; text-align: left; color: #00bfff; }}
      td {{ padding: 10px 12px; border-bottom: 1px solid #1a2f4a; }}
      tr:hover {{ background: #0d1f35; }}
      .status {{ padding: 10px 20px; border-radius: 4px; background: #0d1f35; border-left: 4px solid {status_color}; margin-bottom: 20px; }}
      .api {{ background: #0d1f35; padding: 15px; border-radius: 4px; margin-top: 20px; font-family: monospace; }}
      a {{ color: #00bfff; }}
    </style>
    </head><body>
    <h1>🇮🇳 Bharat Market Intelligence</h1>
    <div class="status">{status_text}</div>
    {"<h2>📊 Top 10 Investment Picks</h2><table><tr><th>Rank</th><th>Company</th><th>Sector</th><th>Price</th><th>Change</th><th>Score</th><th>Signal</th></tr>" + rows + "</table>" if ready else "<p>Data is loading... this page auto-refreshes every 30 seconds.</p>"}
    <div class="api">
      <b>API Endpoints:</b><br>
      <a href="/api/health">/api/health</a> — Server status<br>
      <a href="/api/top10">/api/top10</a> — Top 10 picks (JSON)<br>
      <a href="/api/market-data">/api/market-data</a> — All data<br>
      <a href="/api/announcements">/api/announcements</a> — NSE/BSE news<br>
      <a href="/api/indices">/api/indices</a> — NIFTY/SENSEX<br>
      <a href="/api/refresh">/api/refresh</a> — Force refresh<br>
    </div>
    </body></html>
    """
# ─────────────────────────────────────────────
# START SERVER
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🇮🇳  BHARAT MARKET INTELLIGENCE SERVER")
    print("="*55)
    print("  Open in browser: http://localhost:5000")
    print("  Top 10 API:      http://localhost:5000/api/top10")
    print("  ⏳ Data loads in ~30 seconds after start")
    print("  📊 Auto-refreshes every 5 minutes")
    print("="*55 + "\n")

    # Start background data loader
    threading.Thread(target=auto_refresh_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, debug=False)