# 🇮🇳 Bharat Market Intelligence System

A full-stack Indian stock market intelligence platform that scrapes data from **NSE, BSE, Groww, Zerodha Pulse**, and **Yahoo Finance**, then uses advanced **ML/AI algorithms** to rank the top 10 investment opportunities.

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
┌────────────────┐      ┌──────────────────────────────────┐
│ Yahoo Finance  │      │        StockAnalyzer (ML/AI)      │
│  (yfinance)    │─────▶│  Gradient Boosted Ensemble        │
│  Fundamentals  │      │  Kalman Filter (Technicals)       │
│  Technicals    │      │  Bayesian Sentiment Model         │
│  Historical    │      │  Cross-Sectional Normaliser       │
└────────────────┘      │  Anomaly Detector                 │
                        │  Risk-Adjusted Scoring            │
                        └──────────────┬───────────────────┘
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
cd frontend
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
        "valuation": 70.0,
        "gb_ensemble": 81.2,
        "linear_blend": 76.4,
        "data_confidence": 0.94,
        "anomaly_penalty": 1.0,
        "risk_penalty": 0.97
      },
      "recommendation": "Strong Buy",
      "announcement_impact": "Positive"
    }
  ],
  "last_updated": "2025-01-15T14:30:00"
}
```

---

## 🤖 ML/AI Scoring Engine (analyzer.py)

The scoring engine uses **7 advanced ML/AI algorithms** layered on top of the traditional factor model. All algorithms are implemented in pure Python stdlib — no heavy ML dependencies required.

### Algorithm Overview

```
Raw Data (yfinance + scrapers)
        │
        ▼
┌─────────────────────────────────┐
│  Cross-Sectional Normaliser     │  ← Peer-relative Z-scores per sector
└────────────────┬────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌──────────────┐  ┌───────────────────┐
│ Kalman Filter│  │ Bayesian Sentiment │
│ (RSI, Mom)   │  │ (Beta-Binomial)    │
└──────┬───────┘  └────────┬──────────┘
       │                   │
       └─────────┬─────────┘
                 ▼
┌────────────────────────────────────┐
│   Gradient Boosted Scorer (3 rds)  │
│   Round 1: Linear base model       │
│   Round 2: QARP interaction boost  │
│   Round 3: Momentum overlay        │
└───────────────┬────────────────────┘
                │
    ┌───────────┴──────────┐
    ▼                      ▼
┌──────────────┐   ┌───────────────────┐
│  Anomaly     │   │  Risk Penalty     │
│  Detector    │   │  (Beta + 52w pos) │
└──────┬───────┘   └────────┬──────────┘
       │                    │
       └──────────┬──────────┘
                  ▼
┌─────────────────────────────────────┐
│  Confidence Weighting               │
│  (data completeness shrinkage)      │
└─────────────────┬───────────────────┘
                  ▼
           Final Score (0–100)
```

---

### 1. 🔁 Gradient Boosted Additive Scorer
**Class:** `GradientBoostedScorer`

Simulates a 3-round gradient boosting process with learning rate **ν = 0.30**:

| Round | What it models | Key signals |
|-------|---------------|-------------|
| **Round 1** — Base Learner | Weighted linear combination of 14 normalised features | ROE, P/E, D/E, momentum, upside |
| **Round 2** — Residual Learner | Non-linear feature interactions | `high ROE × low P/E` (QARP), `above MA × momentum` |
| **Round 3** — Momentum Overlay | Short-term price + earnings acceleration | 1M momentum, earnings growth, analyst upside |

The final score blends **60% GB model + 40% traditional weighted linear** to balance ML accuracy with interpretability.

---

### 2. 📡 Kalman Filter (Technical Smoothing)
**Function:** `_kalman_smooth()`

Applied to **RSI** and **1-month momentum** to suppress single-day noise spikes.

```
Kalman Gain  K  = P_prior / (P_prior + R_obs)
Posterior    x̂  = x̂_prior + K × (observation − x̂_prior)
Variance     P  = (1 − K) × P_prior
```

- **Process noise** = 1.5–2.0 (allows the estimate to drift with the market)
- **Observation noise** = 5.0–8.0 (how much we trust each new data point)
- State persists across calls within a session, so estimates improve over time

---

### 3. 🎲 Bayesian Sentiment Model
**Class:** `BayesianSentiment`

Uses a **Beta-Binomial conjugate model** instead of hardcoded +10/−15 point rules:

```
Prior:       Beta(α=2, β=2)   → neutral belief
Positive signal → α += weight
Negative signal → β += weight
Posterior mean  = α / (α + β) → mapped to [0, 100]
```

**Confidence shrinkage:** Stocks with sparse news are pulled toward 50 (neutral prior). Stocks with many consistent signals get sharp, confident scores.

| Signal Source | Weight |
|--------------|--------|
| NSE/BSE filings | 1.0 |
| Zerodha Pulse news | 0.8 |
| Groww trending | 0.5 |

---

### 4. 📊 Cross-Sectional Z-Score Normaliser
**Class:** `CrossSectionalNormaliser`

Every feature is normalised against its **sector peer group** (falls back to universe-wide stats when sector N < 5):

```
z = (value − sector_mean) / sector_std
score = 50 + clip(z, −3, +3) × (50/3)
```

This means a P/E of 18 is scored differently in **Banking** (cheap) vs **FMCG** (below median) — as it should be.

---

### 5. 🚨 Anomaly Detector
**Class:** `AnomalyDetector`

Inspired by **Isolation Forest** — counts how many of 8 key features fall beyond **±2.5σ** from the universe mean:

| Outlier Features | Penalty |
|-----------------|---------|
| 0 | 1.00 (no penalty) |
| 1–2 | 0.92 (−8%) |
| 3–4 | 0.82 (−18%) |
| 5+ | 0.70 (−30%) |

Flags both data errors (e.g. P/E = 0.001) and genuine extreme stocks that carry higher uncertainty.

---

### 6. 📉 Risk-Adjusted Penalty
**Method:** `_risk_penalty()`

Applies a volatility-based multiplicative haircut (floor = 0.85):

- **High Beta (> 1.5):** Each 0.1 above 1.5 → −0.4% penalty
- **Near 52-week high (> 90% range):** −4% (momentum risk)
- **Near 52-week low (< 15% range):** −3% (falling knife caution)

---

### 7. 🎯 Confidence Weighting
**Method:** `_data_confidence()`

Measures what fraction of 10 important fields are populated. Scores are **shrunk toward 50** (the uninformed prior) for thinly-covered stocks:

```
confidence = 0.4 + 0.6 × (fields_present / 10)
final_score = confidence × model_score + (1 − confidence) × 50
```

This prevents a stock with only 3/10 fields from appearing artificially confident.

---

### 8. 📐 Sigmoid Feature Transforms
**Function:** `_sigmoid()`

All hard `if/elif` thresholds from the original model are replaced with **smooth sigmoid curves**:

```python
# Old (cliff at P/E = 25):
if pe < 25: score += 8
elif pe < 35: score += 0

# New (smooth gradient):
pe_score = sigmoid(-(pe/sector_median - 1), k=3.0) × 100
```

This eliminates score cliffs where P/E = 24.9 vs 25.1 produced wildly different outputs.

---

## 📊 Scoring Methodology

### Multi-Factor Scoring (100 points total)

| Component | Weight | Method |
|-----------|--------|--------|
| Fundamentals | 35% | Sigmoid-normalised P/E, ROE, D/E, margins, growth |
| Technicals | 25% | Kalman-smoothed RSI + multi-timeframe momentum |
| Sentiment | 20% | Bayesian Beta-Binomial model |
| Sector | 10% | Adaptive EMA trend momentum |
| Valuation | 10% | Peer-relative cross-sectional z-scores |

Final score = **60% Gradient Boosted ensemble + 40% weighted linear blend**, then multiplied by anomaly penalty, risk penalty, and confidence weight.

---

## 🔧 Data Sources Detail

### NSE (National Stock Exchange)
- **API**: `https://www.nseindia.com/api/`
- **What**: Corporate announcements, board meetings, real-time quotes
- **Auth**: Session cookie (auto-handled)

### BSE (Bombay Stock Exchange)
- **API**: `https://api.bseindia.com/BseIndiaAPI/api/`
- **What**: Corporate filings, financial results, historical data

### Groww
- **Method**: BeautifulSoup scraping + Next.js `__NEXT_DATA__` JSON extraction
- **What**: Top gainers, 52-week highs, trending stocks

### Zerodha Pulse
- **URL**: `https://pulse.zerodha.com`
- **What**: Aggregated market news with company tags and sentiment

### Yahoo Finance (yfinance)
- **Library**: `yfinance` Python package
- **What**: Real-time prices, 90+ fundamental ratios, historical OHLCV, analyst ratings

---

## 🛡️ Anti-Bot Measures & Solutions

| Site | Issue | Solution |
|------|-------|----------|
| NSE | Requires session cookie | `_init_session()` visits homepage first |
| Groww | Next.js SPA | Extract `__NEXT_DATA__` JSON from HTML |
| BSE | IP blocking | Retry logic + delay between requests |

---

## ⚙️ Production Deployment

```bash
# Use gunicorn instead of Flask dev server
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Or with Docker
docker build -t bharat-market .
docker run -p 5000:5000 --env-file .env bharat-market
```

---

## 📁 File Structure

```
stock_scraper/
├── app.py                    # Flask API server (entry point)
├── analyzer.py               # ML/AI scoring engine (v2)
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

---

## ⚠️ Disclaimers

1. **Not Financial Advice**: This tool is for educational/research purposes only. Always consult a SEBI-registered advisor before investing.
2. **Data Accuracy**: Scraped data may have delays or gaps. Yahoo Finance data is generally reliable but not real-time.
3. **Legal Note**: Scraping websites must comply with their Terms of Service. This code is for educational use only.
4. **Market Risk**: Stock investments carry risk. Past performance ≠ future results.
