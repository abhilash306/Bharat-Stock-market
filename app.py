"""
Bharat Market Intelligence - ALL-IN-ONE Server  (v3)
=====================================================
Upgrades over v2:
  · StockAnalyzer (ML/AI v3) replaces the inline score_stock() function
  · MoneyControlScraper added for promoter %, FII/DII flow, pledge risk
  · volume_ratio + momentum_3m added to yfinance technicals
  · refresh_all_data() feeds all 6 sources into StockAnalyzer.score_and_rank()
  · /api/stock/<symbol> now returns ownership fields in response
  · HTML status page shows pledge %, promoter %, and new score breakdown
Just run: python app.py
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

# ── ML/AI Scorer (v3) ─────────────────────────
from analyzer import StockAnalyzer

# ── MoneyControl Scraper ──────────────────────
# use_selenium=False keeps it lightweight; flip to True if HTML tier gets blocked
from scrapers.moneycontrol_scraper import MoneyControlScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app  = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# SINGLETONS  (created once, reused every refresh)
# ─────────────────────────────────────────────
_analyzer  = StockAnalyzer()
_mc_scraper = MoneyControlScraper(use_selenium=False, headless=True)

# ─────────────────────────────────────────────
# STOCK UNIVERSE (Nifty 50 Large Caps)
# ─────────────────────────────────────────────
STOCK_UNIVERSE = [
    {"symbol": "RELIANCE.NS",   "nse_symbol": "RELIANCE",   "name": "Reliance Industries",       "sector": "Energy"},
    {"symbol": "TCS.NS",        "nse_symbol": "TCS",         "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK.NS",   "nse_symbol": "HDFCBANK",    "name": "HDFC Bank",                 "sector": "Banking"},
    {"symbol": "INFY.NS",       "nse_symbol": "INFY",        "name": "Infosys",                   "sector": "IT"},
    {"symbol": "ICICIBANK.NS",  "nse_symbol": "ICICIBANK",   "name": "ICICI Bank",                "sector": "Banking"},
    {"symbol": "HINDUNILVR.NS", "nse_symbol": "HINDUNILVR",  "name": "Hindustan Unilever",        "sector": "FMCG"},
    {"symbol": "SBIN.NS",       "nse_symbol": "SBIN",        "name": "State Bank of India",       "sector": "Banking"},
    {"symbol": "BHARTIARTL.NS", "nse_symbol": "BHARTIARTL",  "name": "Bharti Airtel",             "sector": "Telecom"},
    {"symbol": "ITC.NS",        "nse_symbol": "ITC",         "name": "ITC Limited",               "sector": "FMCG"},
    {"symbol": "KOTAKBANK.NS",  "nse_symbol": "KOTAKBANK",   "name": "Kotak Mahindra Bank",       "sector": "Banking"},
    {"symbol": "LT.NS",         "nse_symbol": "LT",          "name": "Larsen & Toubro",           "sector": "Infrastructure"},
    {"symbol": "WIPRO.NS",      "nse_symbol": "WIPRO",       "name": "Wipro",                     "sector": "IT"},
    {"symbol": "AXISBANK.NS",   "nse_symbol": "AXISBANK",    "name": "Axis Bank",                 "sector": "Banking"},
    {"symbol": "MARUTI.NS",     "nse_symbol": "MARUTI",      "name": "Maruti Suzuki",             "sector": "Auto"},
    {"symbol": "SUNPHARMA.NS",  "nse_symbol": "SUNPHARMA",   "name": "Sun Pharmaceutical",        "sector": "Pharma"},
    {"symbol": "TITAN.NS",      "nse_symbol": "TITAN",       "name": "Titan Company",             "sector": "Consumer"},
    {"symbol": "BAJFINANCE.NS", "nse_symbol": "BAJFINANCE",  "name": "Bajaj Finance",             "sector": "Finance"},
    {"symbol": "HCLTECH.NS",    "nse_symbol": "HCLTECH",     "name": "HCL Technologies",          "sector": "IT"},
    {"symbol": "ULTRACEMCO.NS", "nse_symbol": "ULTRACEMCO",  "name": "UltraTech Cement",          "sector": "Materials"},
    {"symbol": "ADANIENT.NS",   "nse_symbol": "ADANIENT",    "name": "Adani Enterprises",         "sector": "Conglomerate"},
]

# ─────────────────────────────────────────────
# DISPLAY METADATA  (used in routes / HTML only)
# ─────────────────────────────────────────────
SECTOR_NOTE = {
    "IT":             "AI boom, strong deal wins",
    "Banking":        "Credit growth 14%, NPA falling",
    "Energy":         "Refining margins strong",
    "Telecom":        "5G monetization, ARPU up",
    "FMCG":           "Rural demand recovering",
    "Pharma":         "USFDA approvals rising",
    "Auto":           "Premium strong, EV shift",
    "Finance":        "AUM growth, retail lending",
    "Infrastructure": "Govt capex cycle",
    "Materials":      "China slowdown pressure",
    "Consumer":       "Premiumization trend",
    "Conglomerate":   "Regulatory overhang",
}

SECTOR_COLOR = {
    "IT":             "#00e5ff",
    "Banking":        "#00e676",
    "Energy":         "#ffab00",
    "FMCG":           "#ff6d00",
    "Pharma":         "#e040fb",
    "Telecom":        "#40c4ff",
    "Auto":           "#ffca28",
    "Finance":        "#69f0ae",
    "Infrastructure": "#f48fb1",
    "Materials":      "#ff5252",
    "Consumer":       "#b388ff",
    "Conglomerate":   "#ff8a65",
}

# ─────────────────────────────────────────────
# CACHE  (in-memory, thread-safe)
# ─────────────────────────────────────────────
_cache      = {}
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
    "Accept":     "application/json, text/plain, */*",
    "Referer":    "https://www.nseindia.com/",
}

def fetch_nse_announcements():
    announcements = []
    try:
        session = requests.Session()
        session.headers.update(NSE_HEADERS)
        session.get("https://www.nseindia.com", timeout=10)

        resp = session.get(
            "https://www.nseindia.com/api/corporate-announcements?index=equities",
            timeout=15)
        resp.raise_for_status()
        cutoff = datetime.now() - timedelta(days=7)

        for item in resp.json()[:50]:
            try:
                date_str = (item.get("excDate") or item.get("bcast_date") or "")[:10]
                try:    ann_date = datetime.strptime(date_str, "%d-%b-%Y")
                except:
                    try: ann_date = datetime.strptime(date_str, "%Y-%m-%d")
                    except: ann_date = datetime.now()

                if ann_date < cutoff:
                    continue

                detail = (item.get("desc") or item.get("subject") or "")[:300]
                dl     = detail.lower()
                pos_kw = ["dividend","bonus","buyback","profit","revenue up","order","approval"]
                neg_kw = ["loss","penalty","notice","investigation","default","fraud"]
                impact = "Neutral"
                if any(k in dl for k in pos_kw): impact = "Positive"
                elif any(k in dl for k in neg_kw): impact = "Negative"

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
        today  = datetime.now().strftime("%Y%m%d")
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        url    = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
                  f"?strCat=-1&strPrevDate={cutoff}&strScrip=&strSearch=P"
                  f"&strToDate={today}&strType=C&PageNo=1")
        resp = requests.get(url,
                            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/"},
                            timeout=15)
        resp.raise_for_status()

        for item in resp.json().get("Table", [])[:40]:
            detail = (item.get("HEADLINE") or item.get("NEWSSUB") or "")[:300]
            dl     = detail.lower()
            pos_kw = ["result","dividend","profit","revenue","order","approval","bonus"]
            neg_kw = ["loss","penalty","notice","investigation","default","fraud"]
            impact = "Neutral"
            if any(k in dl for k in pos_kw): impact = "Positive"
            elif any(k in dl for k in neg_kw): impact = "Negative"

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
    "Reliance":    ["reliance", "ril"],
    "TCS":         ["tcs", "tata consultancy"],
    "Infosys":     ["infosys", "infy"],
    "HDFC":        ["hdfc bank"],
    "ICICI":       ["icici bank"],
    "SBI":         ["sbi", "state bank"],
    "Airtel":      ["airtel", "bharti"],
    "ITC":         ["itc limited", " itc "],
    "Wipro":       ["wipro"],
    "Sun Pharma":  ["sun pharma", "sunpharma"],
    "Maruti":      ["maruti"],
    "Bajaj Finance":["bajaj finance"],
    "Adani":       ["adani"],
    "HCL":         ["hcl tech"],
    "Titan":       ["titan"],
}

def classify_sentiment(text):
    t   = text.lower()
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
        resp = requests.get("https://pulse.zerodha.com",
                            headers={"User-Agent": "Mozilla/5.0",
                                     "Referer": "https://pulse.zerodha.com/"},
                            timeout=15)
        resp.raise_for_status()
        soup     = BeautifulSoup(resp.text, "lxml")
        articles = soup.find_all("article") or soup.find_all("li", class_=lambda c: c and "item" in c)
        for article in articles[:30]:
            tag = article.find("h2") or article.find("h3") or article.find("a")
            if not tag: continue
            title = tag.get_text(strip=True)
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
# MONEYCONTROL SCRAPER  (NEW)
# ─────────────────────────────────────────────
def fetch_moneycontrol_data():
    """
    Fetch promoter holding %, FII/DII QoQ change, and pledged shares %
    for every stock in the universe via MoneyControlScraper.
    Returns dict keyed by nse_symbol.
    """
    try:
        data = _mc_scraper.fetch_ownership_bulk(STOCK_UNIVERSE)
        fetched = sum(1 for v in data.values() if v.get("promoter_pct") is not None)
        logger.info(f"MoneyControl: {fetched}/{len(STOCK_UNIVERSE)} stocks with ownership data")
        return data
    except Exception as e:
        logger.error(f"MoneyControl fetch error: {e}")
        return {}

# ─────────────────────────────────────────────
# YAHOO FINANCE SCRAPER  (enhanced with volume_ratio + momentum_3m)
# ─────────────────────────────────────────────
def calc_rsi(close, period=14):
    try:
        delta = close.diff()
        gain  = delta.where(delta > 0, 0).rolling(period).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs    = gain / loss
        rsi   = (100 - (100 / (1 + rs))).iloc[-1]
        return round(float(rsi), 1) if not pd.isna(rsi) else None
    except:
        return None

def fetch_single_stock(stock):
    try:
        ticker = yf.Ticker(stock["symbol"])
        info   = ticker.info or {}
        hist   = ticker.history(period="6mo", interval="1d")   # extended to 6mo for momentum_3m/6m

        price  = info.get("currentPrice") or info.get("regularMarketPrice")
        prev   = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change     = round(price - prev, 2) if price and prev else None
        change_pct = round((change / prev) * 100, 2) if change and prev else None

        tech = {}
        if not hist.empty and len(hist) >= 5:
            close  = hist["Close"]
            curr   = float(close.iloc[-1])
            ma20   = float(close.rolling(20).mean().iloc[-1])  if len(close) >= 20  else None
            ma50   = float(close.rolling(50).mean().iloc[-1])  if len(close) >= 50  else None
            ma200  = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

            ema12      = close.ewm(span=12).mean()
            ema26      = close.ewm(span=26).mean()
            macd_histo = (ema12 - ema26 - (ema12 - ema26).ewm(span=9).mean()).iloc[-1]

            # ── Momentum — 1M, 3M, 6M (NEW: 3M + 6M for multi-timeframe scorer) ──
            mom_1m = round(((curr - float(close.iloc[-21])) / float(close.iloc[-21])) * 100, 2) if len(close) >= 21 else None
            mom_3m = round(((curr - float(close.iloc[-63])) / float(close.iloc[-63])) * 100, 2) if len(close) >= 63 else None
            mom_6m = round(((curr - float(close.iloc[0]))   / float(close.iloc[0]))   * 100, 2) if len(close) >= 120 else None

            # ── Volume ratio: current vs 20-day average (NEW: used by ML scorer) ──
            vol_ratio = None
            if "Volume" in hist.columns:
                avg_vol  = hist["Volume"].rolling(20).mean().iloc[-1]
                curr_vol = hist["Volume"].iloc[-1]
                if avg_vol and avg_vol > 0:
                    vol_ratio = round(float(curr_vol) / float(avg_vol), 2)

            tech = {
                "ma20":        round(ma20,  2) if ma20  else None,
                "ma50":        round(ma50,  2) if ma50  else None,
                "ma200":       round(ma200, 2) if ma200 else None,
                "above_ma20":  curr > ma20  if ma20  else False,
                "above_ma50":  curr > ma50  if ma50  else False,
                "above_ma200": curr > ma200 if ma200 else False,
                "rsi":         calc_rsi(close),
                "macd_signal": "Bullish" if (not pd.isna(macd_histo) and macd_histo > 0) else "Bearish",
                "momentum_1m": mom_1m,
                "momentum_3m": mom_3m,   # NEW
                "momentum_6m": mom_6m,   # NEW
                "volume_ratio":vol_ratio, # NEW
                "trend": ("Bullish" if sum([
                    curr > ma20  if ma20  else False,
                    curr > ma50  if ma50  else False,
                    curr > ma200 if ma200 else False,
                ]) >= 2 else "Bearish"),
            }

        # Build sparkline (last 30 days)
        sparkline = []
        if not hist.empty:
            sparkline = [{"v": round(float(v), 2)} for v in hist["Close"].tail(30)]

        roe = info.get("returnOnEquity")
        return {
            "symbol":          stock["symbol"],
            "nse_symbol":      stock["nse_symbol"],
            "name":            info.get("longName") or stock["name"],
            "sector":          info.get("sector") or stock["sector"],
            "price":           round(price, 2) if price else None,
            "change":          change,
            "change_pct":      change_pct,
            "week52_high":     info.get("fiftyTwoWeekHigh"),
            "week52_low":      info.get("fiftyTwoWeekLow"),
            # Aliases expected by analyzer._risk_penalty()
            "52w_high":        info.get("fiftyTwoWeekHigh"),
            "52w_low":         info.get("fiftyTwoWeekLow"),
            "volume":          info.get("volume"),
            "market_cap":      info.get("marketCap"),
            "market_cap_cr":   round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else None,
            "pe":              round(float(info.get("trailingPE") or info.get("forwardPE") or 0), 1) or None,
            "pb":              info.get("priceToBook"),
            "roe":             round(roe * 100, 1) if roe else None,
            "profit_margin":   round((info.get("profitMargins") or 0) * 100, 1),
            "revenue_growth":  round((info.get("revenueGrowth") or 0) * 100, 1),
            "earnings_growth": round((info.get("earningsGrowth") or 0) * 100, 1),
            "debt_equity":     info.get("debtToEquity"),
            "eps":             info.get("trailingEps"),
            "div_yield":       round((info.get("dividendYield") or 0) * 100, 2),
            "target_price":    info.get("targetMeanPrice"),
            "recommendation":  info.get("recommendationKey"),
            "beta":            info.get("beta"),
            "sparkline":       sparkline,
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
            info = yf.Ticker(sym).info
            indices[name] = {
                "value":      info.get("regularMarketPrice"),
                "change":     info.get("regularMarketChange"),
                "change_pct": round(info.get("regularMarketChangePercent", 0), 2),
            }
        except Exception as e:
            logger.warning(f"Index error {name}: {e}")
    return indices

# ─────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────
def normalize_category(text):
    t = (text or "").lower()
    if "result" in t or "financial" in t: return "Results"
    if "dividend" in t:                   return "Dividend"
    if "sebi" in t or "penalty" in t:     return "SEBI"
    if "order" in t or "contract" in t:   return "Order"
    if "rating" in t:                     return "Rating"
    if "bulk" in t or "deal" in t:        return "Bulk Deal"
    if "board" in t:                      return "Board"
    if "shareholding" in t:               return "Shareholding"
    if "management" in t:                 return "Management"
    return "Regulatory"

# ─────────────────────────────────────────────
# MAIN DATA REFRESH  (updated for v3)
# ─────────────────────────────────────────────
def refresh_all_data():
    logger.info("🔄 Starting full data refresh (v3 — ML/AI + MoneyControl)...")

    # ── Fetch all sources in parallel ─────────────────────────────
    # MoneyControl is sequential internally (polite delay per stock)
    # so we run it in its own thread alongside the fast sources.
    with ThreadPoolExecutor(max_workers=5) as ex:
        f_yf    = ex.submit(fetch_all_stocks)
        f_nse   = ex.submit(fetch_nse_announcements)
        f_bse   = ex.submit(fetch_bse_filings)
        f_pulse = ex.submit(fetch_zerodha_news)
        f_idx   = ex.submit(fetch_indices)
        f_mc    = ex.submit(fetch_moneycontrol_data)   # NEW

        yf_data  = f_yf.result()
        nse_anns = f_nse.result()
        bse_fils = f_bse.result()
        pulse    = f_pulse.result()
        indices  = f_idx.result()
        mc_data  = f_mc.result()                       # NEW

    # ── Build all_data dict for StockAnalyzer ─────────────────────
    all_data = {
        "yfinance":           yf_data,
        "nse_announcements":  nse_anns,
        "bse_filings":        bse_fils,
        "groww_trending":     [],        # not fetched in this build; plug in GrowwScraper here if desired
        "zerodha_news":       pulse,
        "moneycontrol":       mc_data,   # NEW — promoter %, FII/DII, pledge %
    }

    # ── Score and rank via ML/AI StockAnalyzer ────────────────────
    scored = _analyzer.score_and_rank(STOCK_UNIVERSE, all_data)

    # ── Attach display-only metadata (sector colour + note) ───────
    for s in scored:
        sector = s.get("sector", "Other")
        s["sectorColor"] = SECTOR_COLOR.get(sector, "#667788")
        s["sector_note"] = SECTOR_NOTE.get(sector, "")

    result = {
        "ranked_stocks":     scored,
        "top_10":            scored[:10],
        "nse_announcements": nse_anns,
        "bse_filings":       bse_fils,
        "zerodha_news":      pulse,
        "indices":           indices,
        "last_updated":      datetime.now().isoformat(),
        "status":            "success",
        "stocks_analyzed":   len(scored),
        "mc_coverage":       sum(1 for v in mc_data.values() if v.get("promoter_pct") is not None),
    }
    cache_set("market_data", result)
    top = scored[0] if scored else {}
    logger.info(
        f"✅ Refresh done. Top pick: {top.get('name','N/A')} "
        f"(score={top.get('score',0)}, rec={top.get('recommendation','N/A')})"
    )

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
        "status":       "ok",
        "data_ready":   data is not None,
        "last_updated": data.get("last_updated") if data else None,
        "mc_coverage":  data.get("mc_coverage", 0) if data else 0,
        "timestamp":    datetime.now().isoformat(),
    })

@app.route("/api/refresh", methods=["POST", "GET"])
def manual_refresh():
    threading.Thread(target=refresh_all_data, daemon=True).start()
    return jsonify({"status": "refresh_started"})

@app.route("/api/market-data")
def get_market_data():
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading", "message": "Data loading, please wait ~45 seconds and refresh..."}), 202
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
            sectors[sec] = {
                "stocks":    [],
                "avg_score": 0,
                "note":      SECTOR_NOTE.get(sec, ""),
                "color":     SECTOR_COLOR.get(sec, "#667788"),
            }
        sectors[sec]["stocks"].append(s["name"])
        sectors[sec]["avg_score"] += s.get("score", 0)
    for sec in sectors:
        n = len(sectors[sec]["stocks"])
        sectors[sec]["avg_score"] = round(sectors[sec]["avg_score"] / n, 1)
        sectors[sec]["count"]     = n
    return jsonify(sectors)

@app.route("/api/stock/<symbol>")
def get_stock(symbol):
    data = cache_get("market_data")
    if not data:
        return jsonify({"status": "loading"}), 202
    match = next(
        (s for s in data.get("ranked_stocks", [])
         if s.get("nse_symbol", "").upper() == symbol.upper()), None)
    if not match:
        return jsonify({"error": "Stock not found"}), 404
    return jsonify(match)

# ─────────────────────────────────────────────
# HTML STATUS PAGE
# ─────────────────────────────────────────────
@app.route("/")
def index():
    data  = cache_get("market_data")
    ready = data is not None
    top   = data.get("top_10", []) if data else []

    rows = "".join(
        f"<tr>"
        f"<td>#{s['rank']}</td>"
        f"<td><b>{s['name']}</b></td>"
        f"<td>{s.get('sector','')}</td>"
        f"<td>₹{s.get('price','N/A')}</td>"
        f"<td style='color:{'green' if (s.get('change_pct') or 0) >= 0 else 'red'}'>"
        f"{s.get('change_pct','N/A')}%</td>"
        f"<td><b>{s.get('score','N/A')}</b></td>"
        f"<td style='color:{'#00e676' if s.get('recommendation','') in ('Strong Buy','Buy') else '#ffab00'}'>"
        f"<b>{s.get('recommendation','')}</b></td>"
        # Ownership columns (NEW)
        f"<td>{s.get('promoter_pct','–') if s.get('promoter_pct') is not None else '–'}%</td>"
        f"<td style='color:{'green' if (s.get('fii_chg_qoq') or 0) >= 0 else 'red'}'>"
        f"{('+' if (s.get('fii_chg_qoq') or 0) > 0 else '') + str(s.get('fii_chg_qoq','–'))}</td>"
        f"<td style='color:{'red' if (s.get('pledged_pct') or 0) > 15 else 'inherit'}'>"
        f"{s.get('pledged_pct','–') if s.get('pledged_pct') is not None else '–'}%</td>"
        # Score breakdown summary (NEW)
        f"<td style='font-size:11px;color:#888'>"
        f"F:{s.get('score_breakdown',{}).get('fundamentals','–')} "
        f"T:{s.get('score_breakdown',{}).get('technicals','–')} "
        f"O:{s.get('score_breakdown',{}).get('ownership','–')}</td>"
        f"</tr>"
        for s in top
    )

    mc_cov     = data.get("mc_coverage", 0) if data else 0
    status_col = "green" if ready else "orange"
    status_txt = (
        f"✅ Data ready — last updated {data.get('last_updated','')[:19]} "
        f"| MC ownership: {mc_cov}/{len(STOCK_UNIVERSE)} stocks"
        if ready else
        "⏳ Loading data... this page auto-refreshes every 30 seconds"
    )

    table_html = ""
    if ready:
        table_html = (
            "<h2>📊 Top 10 Investment Picks</h2>"
            "<table><tr>"
            "<th>Rank</th><th>Company</th><th>Sector</th><th>Price</th>"
            "<th>Change</th><th>Score</th><th>Signal</th>"
            "<th>Promoter%</th><th>FII Δ QoQ</th><th>Pledged%</th>"
            "<th>Breakdown</th>"
            "</tr>"
            + rows + "</table>"
        )

    return f"""
    <!DOCTYPE html><html><head>
    <title>Bharat Market Intelligence v3</title>
    <meta http-equiv="refresh" content="30">
    <style>
      body    {{ font-family: Arial, sans-serif; background: #0a0f1e; color: #c8d8e8; padding: 30px; }}
      h1      {{ color: #00bfff; }} h2 {{ color: #00e676; }}
      table   {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 13px; }}
      th      {{ background: #1a2f4a; padding: 10px; text-align: left; color: #00bfff; }}
      td      {{ padding: 8px 10px; border-bottom: 1px solid #1a2f4a; }}
      tr:hover{{ background: #0d1f35; }}
      .status {{ padding: 10px 20px; border-radius: 4px; background: #0d1f35;
                 border-left: 4px solid {status_col}; margin-bottom: 20px; }}
      .api    {{ background: #0d1f35; padding: 15px; border-radius: 4px;
                 margin-top: 20px; font-family: monospace; }}
      a       {{ color: #00bfff; }}
    </style>
    </head><body>
    <h1>🇮🇳 Bharat Market Intelligence <span style="font-size:14px;color:#888">v3 · ML/AI + MoneyControl</span></h1>
    <div class="status">{status_txt}</div>
    {table_html if ready else "<p>Data is loading... this page auto-refreshes every 30 seconds.</p>"}
    <div class="api">
      <b>API Endpoints:</b><br>
      <a href="/api/health">/api/health</a> — Server status + MC coverage<br>
      <a href="/api/top10">/api/top10</a> — Top 10 picks (JSON)<br>
      <a href="/api/market-data">/api/market-data</a> — All data<br>
      <a href="/api/announcements">/api/announcements</a> — NSE/BSE/Zerodha news<br>
      <a href="/api/indices">/api/indices</a> — NIFTY / SENSEX<br>
      <a href="/api/sectors">/api/sectors</a> — Sector breakdown<br>
      <a href="/api/refresh">/api/refresh</a> — Force refresh<br>
    </div>
    </body></html>
    """

# ─────────────────────────────────────────────
# START SERVER
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 58)
    print("  🇮🇳  BHARAT MARKET INTELLIGENCE  v3")
    print("=" * 58)
    print("  Open in browser : http://localhost:5000")
    print("  Top 10 API      : http://localhost:5000/api/top10")
    print("  ⏳  Data loads in ~45 seconds (MC ownership adds ~30s)")
    print("  📊  Auto-refreshes every 5 minutes")
    print("=" * 58 + "\n")

    threading.Thread(target=auto_refresh_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
