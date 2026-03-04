<div align="center">

# 🇮🇳 Bharat Market Intelligence System

### AI-powered Indian stock market analysis — from raw data to ranked investment picks

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-Educational-orange?style=for-the-badge)]()
[![Status](https://img.shields.io/badge/Status-Active-00e676?style=for-the-badge)]()

**6 live data sources · 8 ML/AI algorithms · Ownership intelligence · Real-time scoring**

[Quick Start](#-quick-start) · [Architecture](#-system-architecture) · [ML Engine](#-mlai-scoring-engine) · [MoneyControl](#-moneycontrol-ownership-intelligence) · [API Reference](#-api-reference) · [Deployment](#-production-deployment)

</div>

---

## ✨ What It Does

Bharat Market Intelligence pulls live data from **NSE, BSE, Groww, Zerodha Pulse, Yahoo Finance,** and **MoneyControl**, runs it through an **ML/AI scoring engine**, and ranks your stock universe by investment quality — automatically, every 5 minutes.

```
📡 Live Data  →  🤖 ML/AI Engine  →  📊 Ranked Picks  →  🌐 REST API  →  💻 React Dashboard
```

### Key Highlights

| Feature | Details |
|---------|---------|
| 🏆 **ML Scoring** | Gradient Boosting · Kalman Filter · Bayesian Sentiment · 8 algorithms total |
| 🏦 **Ownership Intel** | Promoter % · FII/DII institutional flow · Pledged shares (MoneyControl) |
| ⚡ **Real-time** | Parallel data fetching · 5-minute auto-refresh cycle |
| 🛡️ **Risk Aware** | Pledge veto · Anomaly detection · Volatility-adjusted scoring |
| 🔌 **REST API** | 8 endpoints · JSON responses · React frontend ready |
| 🐍 **Zero ML Deps** | All algorithms in pure Python stdlib — no sklearn/tensorflow needed |

---

## 📐 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND                           │
│            Dashboard  ·  Top 10  ·  Announcements           │
└────────────────────────┬─────────────────────────────────────┘
                         │  HTTP / JSON
┌────────────────────────▼─────────────────────────────────────┐
│                  FLASK API  (app.py)                         │
│   /api/top10  ·  /api/market-data  ·  /api/stock/<sym>      │
└──┬──────────┬──────────┬───────────┬────────────┬───────────┘
   │          │          │           │            │
   ▼          ▼          ▼           ▼            ▼
 NSE API   BSE API   Zerodha     Yahoo        MoneyControl
 Announce  Filings   Pulse       Finance      Ownership
 ments     Results   News        Prices       Promoter %
                                 Fundament.   FII / DII
                                 Technicals   Pledged %
   │          │          │           │            │
   └──────────┴──────────┴─────┬─────┴────────────┘
                               │
               ┌───────────────▼────────────────────┐
               │       StockAnalyzer  (v3)           │
               │                                    │
               │  ① Cross-Sectional Normaliser      │
               │  ② Kalman Filter  (RSI / Mom)      │
               │  ③ Bayesian Sentiment Model        │
               │  ④ Gradient Boosted Scorer         │
               │  ⑤ Ownership Scorer  (MC)          │
               │  ⑥ Anomaly Detector                │
               │  ⑦ Risk-Adjusted Penalty           │
               │  ⑧ Confidence Weighting            │
               └───────────────┬────────────────────┘
                               │
               ┌───────────────▼────────────────────┐
               │     In-Memory Cache  (→ Redis)      │
               └────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Google Chrome | Latest | Selenium fallback (optional) |
| Node.js | 18+ | React frontend |

### 1 · Backend

```bash
# Clone the repository
git clone https://github.com/your-username/bharat-market-intelligence.git
cd bharat-market-intelligence

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Open .env and add your ANTHROPIC_API_KEY

# Launch the server
python app.py
```

> 🟢 API live at **http://localhost:5000** — data appears in ~45 seconds

### 2 · Frontend

```bash
cd frontend
npm install
npm run dev
```

> 🟢 Dashboard at **http://localhost:3000**

---

## 📡 API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Server status + MoneyControl data coverage |
| `GET` | `/api/top10` | Top 10 ranked investment picks |
| `GET` | `/api/market-data` | Full universe with all scores |
| `GET` | `/api/stock/<symbol>` | Single stock deep-dive |
| `GET` | `/api/announcements` | NSE + BSE + Zerodha news |
| `GET` | `/api/sectors` | Sector-level aggregates |
| `GET` | `/api/indices` | NIFTY 50 + SENSEX live |
| `POST` | `/api/refresh` | Force an immediate data refresh |

### Sample Response — `/api/top10`

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
      "score": 84.7,
      "recommendation": "Strong Buy",

      "score_breakdown": {
        "fundamentals":    78.0,
        "technicals":      74.0,
        "sentiment":       80.0,
        "sector":          75.0,
        "valuation":       70.0,
        "ownership":       88.5,
        "gb_ensemble":     83.2,
        "linear_blend":    76.4,
        "data_confidence": 0.97,
        "anomaly_penalty": 1.00,
        "risk_penalty":    1.00
      },

      "promoter_pct":      72.3,
      "promoter_chg_qoq":  -0.2,
      "fii_pct":           18.6,
      "fii_chg_qoq":       1.2,
      "dii_pct":            6.1,
      "dii_chg_qoq":        0.3,
      "pledged_pct":        0.0,

      "pe": 28.4,  "roe": 47.2,  "debt_equity": 0.08,
      "rsi": 58.3, "trend": "Bullish", "momentum_1m": 4.7,
      "announcement_impact": "Positive"
    }
  ],
  "last_updated": "2025-01-15T14:30:00",
  "mc_coverage": 18
}
```

---

## 🤖 ML/AI Scoring Engine

> All 8 algorithms run in **pure Python stdlib** — no scikit-learn, TensorFlow, or PyTorch required.

### How the Final Score is Built

```
┌─────────────────────────────────────────────────────────────┐
│                  FINAL SCORE  (0 – 100)                     │
│                                                             │
│   60% × Gradient Boosted Ensemble                          │
│ + 40% × Weighted Linear Blend                              │
│                                                             │
│   × Anomaly Penalty   (0.70 – 1.00)                        │
│   × Risk Penalty      (0.80 – 1.00)                        │
│                                                             │
│   Shrunk toward 50 by Confidence Weighting                  │
└─────────────────────────────────────────────────────────────┘
```

### Factor Weights

| # | Factor | Weight | What it measures |
|---|--------|:------:|-----------------|
| 1 | **Fundamentals** | 30% | P/E · ROE · D/E · Margins · EPS Growth |
| 2 | **Technicals** | 22% | Kalman-RSI · MACD · MA crossovers · Multi-timeframe momentum |
| 3 | **Sentiment** | 18% | Bayesian model over NSE / BSE / Zerodha / Groww signals |
| 4 | **Sector** | 10% | Adaptive EMA-based sector momentum |
| 5 | **Valuation** | 10% | Peer-relative P/E · P/B · Analyst upside |
| 6 | **Ownership** | 10% | Promoter % · FII/DII flow · Pledged shares (MoneyControl) |

---

### ① Gradient Boosted Scorer
**Class:** `GradientBoostedScorer` · 3 rounds · learning rate ν = 0.30

Simulates gradient boosting without any external library — three additive rounds, each correcting the residual of the previous:

| Round | Name | What it captures |
|:-----:|------|-----------------|
| **1** | Base Linear | Weighted sum of 17 normalised features (P/E, ROE, momentum, pledge, etc.) |
| **2** | Interaction Residual | `ROE × (1/PE)` QARP · `MA × Momentum` trend · `Promoter × FII` smart money |
| **3** | Momentum Overlay | 1M price momentum · earnings growth · analyst upside · pledge drag |

```
Final ensemble = Base + ν × Residual + ν × Momentum Overlay
```

---

### ② Kalman Filter — Technical Smoothing
**Function:** `_kalman_smooth()` · Applied to RSI and 1M Momentum

Suppresses single-day noise spikes. State persists across refresh cycles — estimates improve over time.

```
Kalman Gain   K  =  P_prior / (P_prior + R_obs)
New Estimate  x̂  =  x̂_prior + K × (raw_value − x̂_prior)
New Variance  P  =  (1 − K) × P_prior
```

| Parameter | RSI | Momentum |
|-----------|:---:|:-------:|
| Observation noise | 8.0 | 5.0 |
| Process noise | 2.0 | 1.5 |

---

### ③ Bayesian Sentiment Model
**Class:** `BayesianSentiment` · Beta-Binomial conjugate

Every news signal updates a Beta distribution. Confidence shrinks sparse-data stocks toward neutral (50) so a single headline can't dominate the score.

```
Prior          →  Beta(α=2, β=2)          ← neutral starting belief
Positive news  →  α += weight
Negative news  →  β += weight
Score          →  (α / α+β) × 100         ← posterior mean in [0, 100]
```

| Signal Source | Weight | Rationale |
|--------------|:------:|-----------|
| NSE / BSE filings | 1.0 | Official regulatory disclosures |
| Zerodha Pulse | 0.8 | Curated financial journalism |
| Groww trending | 0.5 | Retail momentum indicator |

---

### ④ Cross-Sectional Z-Score Normaliser
**Class:** `CrossSectionalNormaliser` · Sector-relative peer scoring

A P/E of 18 means something very different in Banking vs FMCG. Every feature is scored relative to its **own sector's** mean and standard deviation:

```
z     =  (value − sector_mean) / sector_std
score =  50 + clip(z, −3, +3) × (50/3)     →   range [0, 100]
```

Falls back to universe-wide stats when a sector has fewer than 5 stocks.

---

### ⑤ Isolation Forest Anomaly Detector
**Class:** `AnomalyDetector` · Mahalanobis-like distance

Counts how many of 8 key features exceed **±2.5σ** from the universe mean. Catches both data errors and genuinely extreme stocks with higher uncertainty.

| Outlier Features | Penalty | Score Impact |
|:---------------:|:-------:|:-----------:|
| 0 | 1.00 | None |
| 1–2 | 0.92 | −8% |
| 3–4 | 0.82 | −18% |
| 5+ | 0.70 | −30% |

---

### ⑥ Risk-Adjusted Penalty
**Method:** `_risk_penalty()` · Floor: 0.80

Three independent risk sources each apply a multiplicative haircut:

| Risk Source | Trigger | Haircut |
|------------|---------|:-------:|
| High volatility | Beta > 1.5 (per 0.1 above) | −0.4% |
| Near 52-week high | Price in top 10% of range | −4% |
| Near 52-week low | Price in bottom 15% of range | −3% |
| Pledged shares | > 15% | −3% |
| Pledged shares | > 30% | −6% |
| Pledged shares | > 50% | −10% |

---

### ⑦ Confidence Weighting
**Method:** `_data_confidence()` · Range: [0.40, 1.00]

The less data available, the more the score shrinks toward 50 (neutral prior) — preventing thinly-covered stocks from appearing falsely confident:

```
confidence = 0.80 × (yfinance_fields_present / 10)
           + 0.20 × (moneycontrol_fields_present / 3)

final_score = confidence × model_score + (1 − confidence) × 50
```

---

### ⑧ Sigmoid Feature Transforms
**Function:** `_sigmoid()` · Replaces all hard if/elif thresholds

Every metric uses a smooth sigmoid curve — eliminating score cliffs where tiny value differences cause large score jumps:

```python
# ❌ Before — cliff: P/E 24.9 vs 25.1 = 8-point gap
if pe < 25:   score += 8
elif pe < 35: score += 0

# ✅ After — smooth gradient across the full range
pe_score = sigmoid(-(pe / sector_median - 1), k=3.0) × 100
```

---

## 🏦 MoneyControl Ownership Intelligence

> These three signals are the most powerful **India-specific** quality and risk filters available. Yahoo Finance does not provide any of them.

### Why Ownership Data Changes Everything

| Signal | The question it answers | Why it's critical |
|--------|------------------------|------------------|
| 📊 **Promoter Holding %** | Do founders still believe in the business? | High, stable holding = management conviction |
| 🏛️ **FII / DII Flow (QoQ)** | Is smart institutional money buying or selling? | Strongest leading indicator for Indian equities |
| 🚨 **Pledged Shares %** | Has the promoter borrowed against their own shares? | Hidden time-bomb — triggers forced selling in a downturn |

---

### Signal 1 · Promoter Holding %

```
base_score  = sigmoid(promoter_pct − 50, k=0.08) × 100
qoq_bonus   = sigmoid(promoter_chg_qoq, k=1.5) × 20 − 10    ← ±10 pts
final_score = base_score + qoq_bonus,  clamped to [0, 100]
```

| Promoter % | Signal | What it means |
|:----------:|:------:|--------------|
| > 65% | 🟢 Strong | Founders have not diluted — high conviction |
| 45–65% | 🟡 Healthy | Typical for Indian large-caps |
| 30–45% | 🟠 Caution | Moderate dilution — investigate why |
| < 30% | 🔴 Weak | Founders have largely exited |
| ↑ Rising QoQ | ✅ +Bonus | Insider buying — bullish signal |
| ↓ Falling QoQ | ⚠️ −Penalty | Insider selling — bearish signal |

---

### Signal 2 · FII / DII Institutional Flow

```
combined_flow  = 0.60 × fii_chg_qoq  +  0.40 × dii_chg_qoq
holding_level  = min(1.0,  (fii_pct + dii_pct) / 30)
flow_score     = sigmoid(combined_flow, k=1.0) × 100
final_score    = 0.70 × flow_score  +  0.30 × (holding_level × 100)
```

> FII gets **60% weight** — foreign institutions are more analytically driven. DII gets **40% weight** — domestic funds (mutual funds, LIC) are stickier but equally important.

| FII | DII | Signal |
|:---:|:---:|--------|
| ↑ Buying | ↑ Buying | 🟢 **Strongest** — unanimous institutional accumulation |
| ↑ Buying | → Flat | 🟢 Positive — foreign conviction |
| → Flat | ↑ Buying | 🟡 Moderate — domestic accumulation |
| ↑ Buying | ↓ Selling | 🟡 Mixed — divergent views |
| ↓ Selling | ↓ Selling | 🔴 **Weakest** — institutional exodus |

---

### Signal 3 · Pledged Shares % (Non-Linear Risk)

> ⚠️ **Pledge risk is exponential, not linear.** The gap between 0% and 10% is minor. The gap between 30% and 50% can be existential — lenders can force-sell shares and trigger a price collapse.

| Pledged % | Score | Risk Level |
|:---------:|:-----:|:----------:|
| 0% | 95 | ✅ Excellent governance |
| < 5% | 80 | ✅ Minimal — acceptable |
| 5–15% | 60 | 🟡 Elevated — monitor quarterly |
| 15–30% | 35 | 🟠 High risk — red flag |
| 30–50% | 15 | 🔴 Severe — near-distress |
| > 50% | 5 | 🚨 Extreme — avoid or exit |

---

### 🚨 The Pledge Veto Rule

Any stock with **pledged shares above 40%** is hard-capped at **"Hold"** — regardless of how strong its fundamentals or momentum look:

```python
# In _generate_recommendation() — this rule cannot be overridden
if pledged_pct > 40 and recommendation in ("Strong Buy", "Buy"):
    recommendation = "Hold"   # Pledge veto applied
```

**Why?** A high-momentum stock with 45% pledge is one bad quarter away from a lender-triggered selloff. The ML model correctly refuses to recommend buying into that risk.

---

### 3-Tier Scraping Strategy

MoneyControl uses Cloudflare protection and heavy JS rendering. The scraper degrades gracefully:

```
┌─────────────────────────────────────────────────────────┐
│  Tier 1 — MC Search API  (JSON autocomplete)            │
│  Resolves NSE symbol → MC URL slug                      │
│  Speed: Fast ⚡  |  Success: ~85%                       │
└──────────────────────────┬──────────────────────────────┘
                           │ on failure
┌──────────────────────────▼──────────────────────────────┐
│  Tier 2 — BeautifulSoup HTML                            │
│  Parses shareholding table + embedded script JSON       │
│  Speed: Medium 🔄  |  Success: ~70%                     │
└──────────────────────────┬──────────────────────────────┘
                           │ on failure
┌──────────────────────────▼──────────────────────────────┐
│  Tier 3 — Selenium Headless Chrome  (opt-in)            │
│  Full JS render → pass page source to BeautifulSoup     │
│  Speed: Slow 🐢  |  Success: ~95%                       │
└─────────────────────────────────────────────────────────┘
```

Enable Tier 3 in `app.py`:
```python
_mc_scraper = MoneyControlScraper(use_selenium=True, headless=True)
```

---

## 🔧 Data Sources

| Source | Type | What We Fetch | Auth Required |
|--------|------|--------------|:-------------:|
| **NSE** | REST API | Corporate announcements · Board meetings | Session cookie (auto) |
| **BSE** | REST API | Filings · Financial results · Quotes | None |
| **Groww** | HTML scrape | Top gainers · 52w highs · Trending stocks | None |
| **Zerodha Pulse** | HTML scrape | Market news · Company sentiment | None |
| **Yahoo Finance** | Python library | Prices · 90+ ratios · Technicals · Analyst ratings | None |
| **MoneyControl** | 3-tier scrape | Promoter % · FII/DII flow · Pledged shares | None |

### Anti-Bot Measures & Solutions

| Site | Protection | Our Solution |
|------|-----------|-------------|
| NSE | Session cookie required | Visit homepage first to seed cookie jar |
| Groww | Next.js SPA (no server HTML) | Extract `__NEXT_DATA__` JSON blob from page source |
| MoneyControl | Cloudflare · JS rendering | 3-tier: Search API → HTML parse → Selenium |
| BSE | Occasional IP throttling | Polite random delays between requests |

---

## ⚙️ Production Deployment

### Gunicorn (recommended)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker
```bash
docker build -t bharat-market .
docker run -p 5000:5000 --env-file .env bharat-market
```

### Upgrade to Redis Cache
```python
# In app.py — replace in-memory cache with Redis:
import redis, json
r = redis.Redis(host="localhost", port=6379, db=0)

def cache_set(key, value):
    r.setex(key, 300, json.dumps(value))   # 5-min TTL

def cache_get(key):
    val = r.get(key)
    return json.loads(val) if val else None
```

---

## 📁 Project Structure

```
bharat-market-intelligence/
│
├── app.py                          ← Flask server · all routes · refresh loop
├── analyzer.py                     ← ML/AI scoring engine (v3)
├── README.md
├── requirements.txt
├── .env.example
│
└── scrapers/
    ├── __init__.py
    ├── nse_scraper.py              ← NSE corporate announcements
    ├── bse_scraper.py              ← BSE filings & financial results
    ├── groww_scraper.py            ← Groww trending stocks
    ├── zerodha_scraper.py          ← Zerodha Pulse market news
    ├── yfinance_scraper.py         ← Yahoo Finance (primary data source)
    └── moneycontrol_scraper.py     ← Ownership intelligence (NEW v3)
```

---

## ⚠️ Disclaimers

> **Not Financial Advice** — This platform is built for educational and research purposes only. Always consult a SEBI-registered investment advisor before making any investment decisions.

| | Note |
|-|------|
| 📊 | **Data accuracy** — Scraped data may have delays. Yahoo Finance is reliable but not tick-level real-time |
| ⚖️ | **Legal** — Web scraping must comply with each site's Terms of Service. This code is for educational use only |
| 📉 | **Market risk** — All stock investments carry risk. Past performance does not guarantee future results |
| 🤖 | **AI limitations** — ML scores are probabilistic signals, not guarantees. Always cross-check before acting |

---

<div align="center">

Built with ❤️ for Indian investors

**NSE · BSE · Groww · Zerodha · Yahoo Finance · MoneyControl**

</div>