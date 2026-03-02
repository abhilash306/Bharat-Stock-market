# 🇮🇳 Bharat Market Intelligence System

A full-stack Indian stock market intelligence platform that scrapes data from **NSE, BSE, Groww, Zerodha Pulse**, and **Yahoo Finance**, then uses AI to rank the top 10 investment opportunities.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│         Dashboard · Top 10 · Announcements · AI         │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP API calls
┌──────────────────────▼──────────────────────────────────┐
│              FLASK API SERVER (app.py)                   │
│    /api/market-data · /api/top10 · /api/refresh         │
└──┬────────────┬───────────────┬──────────────┬──────────┘
   │            │               │              │
   ▼            ▼               ▼              ▼
┌──────┐  ┌─────────┐   ┌──────────┐  ┌─────────────┐
│ NSE  │  │   BSE   │   │  Groww   │  │   Zerodha   │
│ API  │  │   API   │   │  Scraper │  │  Pulse      │
└──┬───┘  └────┬────┘   └────┬─────┘  └──────┬──────┘
   │           │             │               │
   └─────┬─────┘             └──────┬────────┘
         │                         │
         ▼                         ▼
┌────────────────┐      ┌──────────────────────┐
│ Yahoo Finance  │      │   StockAnalyzer       │
│  (yfinance)    │─────▶│  Multi-Factor Scorer  │
│  Fundamentals  │      │  35% Fundamental      │
│  Technicals    │      │  25% Technical        │
│  Historical    │      │  20% Sentiment        │
└────────────────┘      │  10% Sector           │
                        │  10% Valuation        │
                        └──────────┬────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │   In-Memory Cache     │
                        │  (Redis in prod)      │
                        └──────────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Google Chrome (for Selenium-based scraping)
- Node.js 18+ (for the React frontend)

### 2. Backend Setup

```bash
# Clone / enter the backend directory
cd stock_scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Start the server
python app.py
```

The API will be live at **http://localhost:5000**

### 3. Frontend Setup

```bash
# In a new terminal
cd frontend    # (the React app from claude.ai)
npm install
npm run dev
```

Open **http://localhost:3000** — the dashboard will connect to your local backend.

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Server health check |
| `/api/market-data` | GET | All stocks with scores |
| `/api/top10` | GET | Top 10 investment picks |
| `/api/announcements` | GET | NSE + BSE filings |
| `/api/sectors` | GET | Sector-wise sentiment |
| `/api/stock/<symbol>` | GET | Single stock detail |
| `/api/refresh` | POST | Trigger manual refresh |

### Example Response - `/api/top10`
```json
{
  "top_10": [
    {
      "rank": 1,
      "name": "Tata Consultancy Services",
      "symbol": "TCS.NS",
      "sector": "IT",
      "price": 4125.50,
      "change_pct": 1.23,
      "pe": 28.4,
      "roe": 47.2,
      "debt_equity": 0.08,
      "rsi": 58.3,
      "trend": "Bullish",
      "momentum_1m": 4.7,
      "score": 82.4,
      "score_breakdown": {
        "fundamentals": 78.0,
        "technicals": 74.0,
        "sentiment": 80.0,
        "sector": 75.0,
        "valuation": 70.0
      },
      "recommendation": "Strong Buy",
      "announcement_impact": "Positive"
    }
  ],
  "last_updated": "2025-01-15T14:30:00"
}
```

---

## 📊 Scoring Methodology

### Multi-Factor Scoring (100 points total)

#### 1. Fundamental Score (35%)
| Metric | Max Points | Green Zone |
|--------|-----------|------------|
| P/E Ratio | ±15 | P/E < 15 → +15 pts |
| ROE | ±12 | ROE > 25% → +12 pts |
| Debt/Equity | ±8 | D/E < 0.3 → +8 pts |
| Profit Margin | ±8 | Margin > 20% → +8 pts |
| Earnings Growth | ±10 | Growth > 30% → +10 pts |
| Revenue Growth | ±5 | Growth > 20% → +5 pts |

#### 2. Technical Score (25%)
| Signal | Points |
|--------|--------|
| RSI 30–50 (recovery zone) | +12 |
| Price above 200-day MA | +10 |
| MACD Bullish crossover | +8 |
| 1-month momentum > 10% | +8 |
| Volume > 1.5x average | +5 |

#### 3. Sentiment Score (20%)
- NSE/BSE announcement: Positive → 80/100, Negative → 20/100
- Groww trending stock → +10 pts
- Zerodha Pulse positive news → +10 pts
- Zerodha Pulse negative news → -15 pts

#### 4. Sector Score (10%)
- Each sector has a base score (48–75)
- Adjusted by current sector trend (up/flat/down)

#### 5. Valuation Score (10%)
- P/E vs sector median
- Price vs analyst target price
- Price-to-Book ratio

---

## 🔧 Data Sources Detail

### NSE (National Stock Exchange)
- **API**: `https://www.nseindia.com/api/`
- **What**: Corporate announcements, board meetings, real-time quotes
- **Auth**: Session cookie (auto-handled)
- **Rate limit**: ~30 requests/minute

### BSE (Bombay Stock Exchange)
- **API**: `https://api.bseindia.com/BseIndiaAPI/api/`
- **What**: Corporate filings, financial results, historical data
- **Auth**: None required for basic endpoints
- **Rate limit**: ~20 requests/minute

### Groww
- **Method**: Selenium + BeautifulSoup scraping
- **URL**: `https://groww.in/stocks/`
- **What**: Top gainers, 52-week highs, trending stocks, fundamentals
- **Auth**: None (public pages)
- **Note**: Uses Next.js `__NEXT_DATA__` JSON extraction

### Zerodha Pulse
- **URL**: `https://pulse.zerodha.com`
- **What**: Aggregated market news with company tags
- **Method**: BeautifulSoup HTML scraping
- **Auth**: None (public feed)

### Yahoo Finance (yfinance)
- **Library**: `yfinance` Python package
- **What**: Real-time prices, 90+ fundamental ratios, historical OHLCV, analyst ratings, financial statements
- **Auth**: None (free)
- **Rate limit**: Generous (parallel fetching supported)

---

## 🛡️ Anti-Bot Measures & Solutions

| Site | Issue | Solution in Code |
|------|-------|-----------------|
| NSE | Requires session cookie | `_init_session()` visits homepage first |
| NSE | Bot detection on API | Realistic browser headers + session |
| Groww | Next.js SPA | Extract `__NEXT_DATA__` JSON from HTML |
| Zerodha | Dynamic content | BeautifulSoup on server-rendered HTML |
| BSE | IP blocking | Retry logic + delay between requests |

### If you're getting blocked:
```python
# Add delays between requests in scrapers
import time
time.sleep(1.5)  # Add between each request

# Or use rotating proxies:
proxies = {"http": "http://proxy:port", "https": "https://proxy:port"}
session.get(url, proxies=proxies)
```

---

## ⚙️ Production Deployment

```bash
# Use gunicorn instead of Flask dev server
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Or with Docker
docker build -t bharat-market .
docker run -p 5000:5000 --env-file .env bharat-market
```

### For production, upgrade to Redis cache:
```python
# In cache.py, replace DataCache with:
import redis
r = redis.Redis(host='localhost', port=6379, db=0)
r.setex(key, ttl, json.dumps(value))
```

---

## ⚠️ Disclaimers

1. **Not Financial Advice**: This tool is for educational/research purposes only. Always consult a SEBI-registered advisor before investing.
2. **Data Accuracy**: Scraped data may have delays or gaps. Yahoo Finance data is generally reliable but not real-time.
3. **Legal Note**: Scraping websites must comply with their Terms of Service. This code is for educational use only.
4. **Market Risk**: Stock investments carry risk. Past performance ≠ future results.

---

## 📁 File Structure

```
stock_scraper/
├── app.py                    # Flask API server (entry point)
├── analyzer.py               # Multi-factor scoring engine
├── cache.py                  # In-memory cache
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── README.md                 # This file
└── scrapers/
    ├── __init__.py
    ├── nse_scraper.py        # NSE corporate announcements
    ├── bse_scraper.py        # BSE filings & results
    ├── groww_scraper.py      # Groww trending & fundamentals
    ├── zerodha_scraper.py    # Zerodha Pulse news
    └── yfinance_scraper.py   # Yahoo Finance (primary data)
```
