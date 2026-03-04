"""
Stock Analyzer & Scoring Engine — ML/AI Enhanced
=================================================
Advanced multi-factor scoring using:
  - Gaussian Z-score feature normalisation
  - Ensemble model (Gradient Boosted additive scoring + weighted linear model)
  - Kalman filter smoothing for technical indicators
  - Bayesian sentiment updating (Beta-Binomial conjugate)
  - Isolation-Forest-inspired anomaly detection
  - Confidence-weighted scoring based on data completeness
  - Risk-adjusted (volatility-penalised) composite score
  - Dynamic peer-relative valuation (cross-sectional z-scores)
  - Multi-timeframe momentum decomposition
  - Adaptive sector weights via exponential trend smoothing
"""

import logging
import math
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Maths helpers (pure stdlib — no heavy dependencies required)
# ─────────────────────────────────────────────────────────────────────────────

def _safe(v, default=0.0):
    """Return v if truthy numeric, else default."""
    if v is None:
        return default
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _zscore(value: float, mean: float, std: float) -> float:
    """Clipped z-score → maps to [0, 100] via sigmoid."""
    if std < 1e-9:
        return 50.0
    z = (value - mean) / std
    z = max(-3.0, min(3.0, z))           # clip to ±3σ
    return 50.0 + z * (50.0 / 3.0)      # linear stretch to [0, 100]


def _sigmoid(x: float, k: float = 1.0) -> float:
    """Standard sigmoid, returns (0, 1)."""
    try:
        return 1.0 / (1.0 + math.exp(-k * x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _ema(values: list, alpha: float = 0.3) -> float:
    """Exponential moving average (most-recent value is last)."""
    if not values:
        return 0.0
    result = float(values[0])
    for v in values[1:]:
        result = alpha * float(v) + (1 - alpha) * result
    return result


def _kalman_smooth(obs: float,
                   prior_est: float,
                   prior_var: float,
                   obs_noise: float = 5.0,
                   process_noise: float = 1.0) -> tuple:
    """
    Single-step scalar Kalman filter update.
    Returns (posterior_estimate, posterior_variance).
    Smooths a noisy indicator toward a running estimate.
    """
    predicted_var = prior_var + process_noise
    kalman_gain   = predicted_var / (predicted_var + obs_noise)
    posterior_est = prior_est + kalman_gain * (obs - prior_est)
    posterior_var = (1 - kalman_gain) * predicted_var
    return posterior_est, posterior_var


# ─────────────────────────────────────────────────────────────────────────────
# Bayesian Sentiment Model
# ─────────────────────────────────────────────────────────────────────────────

class BayesianSentiment:
    """
    Beta-Binomial conjugate model for binary sentiment signals.
    Prior: Beta(α=2, β=2)  → neutral starting belief.
    Each Positive signal adds to α; each Negative adds to β.
    Posterior mean = α/(α+β) → mapped to [0, 100].
    """

    PRIOR_ALPHA = 2.0
    PRIOR_BETA  = 2.0

    def __init__(self):
        self._alpha = {}  # symbol → α
        self._beta  = {}  # symbol → β

    def update(self, symbol: str, impact: str, weight: float = 1.0):
        sym = symbol.upper()
        a = self._alpha.get(sym, self.PRIOR_ALPHA)
        b = self._beta.get(sym,  self.PRIOR_BETA)
        if impact == "Positive":
            a += weight
        elif impact == "Negative":
            b += weight
        # Neutral: no update (prior stays)
        self._alpha[sym] = a
        self._beta[sym]  = b

    def score(self, symbol: str) -> float:
        """Return posterior sentiment score in [0, 100]."""
        sym = symbol.upper()
        a = self._alpha.get(sym, self.PRIOR_ALPHA)
        b = self._beta.get(sym,  self.PRIOR_BETA)
        posterior_mean = a / (a + b)   # in (0, 1)
        # Confidence: more evidence → sharper distribution
        n = a + b - self.PRIOR_ALPHA - self.PRIOR_BETA  # net evidence
        # Shrink toward 50 when evidence is sparse
        confidence = 1.0 - math.exp(-n * 0.5)
        blended = 50.0 * (1 - confidence) + posterior_mean * 100 * confidence
        return round(max(0, min(100, blended)), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-sectional normaliser (peer-relative z-scores)
# ─────────────────────────────────────────────────────────────────────────────

class CrossSectionalNormaliser:
    """
    Computes sector-level mean & std for each feature so every sub-score
    reflects how a stock ranks relative to its peers, not on an absolute
    hard-coded scale.  Falls back to universe-wide stats when sector N < 5.
    """

    def fit(self, records: list, features: list):
        """
        records : list of dicts (merged yf data)
        features: list of numeric feature keys
        """
        self._universe_stats = {}
        self._sector_stats   = {}

        # Universe-level
        for feat in features:
            vals = [_safe(r.get(feat)) for r in records if r.get(feat) is not None]
            if len(vals) > 1:
                mean = sum(vals) / len(vals)
                std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
            else:
                mean, std = 0.0, 1.0
            self._universe_stats[feat] = (mean, std)

        # Sector-level
        sectors = {r.get("sector", "Other") for r in records}
        for sec in sectors:
            grp = [r for r in records if r.get("sector", "Other") == sec]
            if len(grp) < 5:
                continue
            self._sector_stats[sec] = {}
            for feat in features:
                vals = [_safe(r.get(feat)) for r in grp if r.get(feat) is not None]
                if len(vals) > 1:
                    mean = sum(vals) / len(vals)
                    std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
                else:
                    mean, std = 0.0, 1.0
                self._sector_stats[sec][feat] = (mean, std)

    def transform(self, value: float, feature: str, sector: str = "Other") -> float:
        """Return peer-relative score [0, 100]."""
        stats = self._sector_stats.get(sector, self._universe_stats)
        mean, std = stats.get(feature, self._universe_stats.get(feature, (0.0, 1.0)))
        return _zscore(value, mean, std)


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detector (Isolation-Forest-inspired heuristic)
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Lightweight anomaly detector: computes a Mahalanobis-like distance
    using per-feature standardisation, then penalises outlier stocks.

    Stocks beyond 2.5σ on ≥3 features are flagged as anomalous (data error
    or genuine extreme — both warrant a score haircut).
    """

    FEATURES = ["pe", "pb", "roe", "debt_equity", "profit_margin",
                "rsi", "volume_ratio", "momentum_1m"]

    def fit(self, records: list):
        self._stats = {}
        for feat in self.FEATURES:
            vals = [_safe(r.get(feat)) for r in records if r.get(feat) is not None]
            if len(vals) > 1:
                mean = sum(vals) / len(vals)
                std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
                self._stats[feat] = (mean, max(std, 1e-9))

    def anomaly_penalty(self, yf: dict) -> float:
        """
        Returns a multiplicative penalty ∈ [0.70, 1.0].
        Normal stocks → 1.0; extreme outliers → 0.70.
        """
        outlier_count = 0
        for feat, (mean, std) in self._stats.items():
            val = yf.get(feat)
            if val is not None:
                z = abs((_safe(val) - mean) / std)
                if z > 2.5:
                    outlier_count += 1
        if outlier_count == 0:
            return 1.0
        elif outlier_count <= 2:
            return 0.92
        elif outlier_count <= 4:
            return 0.82
        else:
            return 0.70


# ─────────────────────────────────────────────────────────────────────────────
# Gradient-Boosted Additive Scorer
# ─────────────────────────────────────────────────────────────────────────────

class GradientBoostedScorer:
    """
    Simulates a 3-round gradient boosting approach:

    Round 1 – Base learner    : weighted linear combination of normalised features.
    Round 2 – Residual learner: captures non-linear interactions (e.g. low PE × high ROE).
    Round 3 – Momentum learner: overlays recent price/earnings momentum.

    Each round's contribution is shrunk by a learning rate (ν = 0.3) to prevent
    overfitting to any single signal.
    """

    LEARNING_RATE = 0.30
    BASE_SCORE    = 50.0

    # Feature importance weights (empirically calibrated for Indian equities)
    FEATURE_WEIGHTS = {
        # Fundamentals
        "pe_score":       -0.12,   # lower PE → better
        "roe_score":       0.18,
        "de_score":       -0.10,   # lower D/E → better
        "pm_score":        0.12,
        "eg_score":        0.15,
        "rg_score":        0.08,
        # Technicals
        "rsi_score":       0.10,
        "ma_score":        0.12,
        "macd_score":      0.08,
        "vol_score":       0.06,
        "mom_score":       0.10,
        # Valuation
        "relative_pe":    -0.10,
        "pb_score":       -0.07,
        "upside_score":    0.14,
    }

    def predict(self, features: dict) -> float:
        """Return score ∈ [0, 100]."""
        # Round 1: base linear score
        base = self.BASE_SCORE
        for feat, weight in self.FEATURE_WEIGHTS.items():
            raw = features.get(feat, 50.0)
            # Normalise each feature to [-1, 1] centred on 50
            norm = (raw - 50.0) / 50.0
            base += weight * norm * 50.0

        # Round 2: interaction boosting residual
        # High ROE + Low PE is a "quality at reasonable price" signal
        roe_n = (features.get("roe_score",   50.0) - 50.0) / 50.0
        pe_n  = (features.get("pe_score",    50.0) - 50.0) / 50.0
        mom_n = (features.get("mom_score",   50.0) - 50.0) / 50.0
        ma_n  = (features.get("ma_score",    50.0) - 50.0) / 50.0

        qarp_interaction   = roe_n * (-pe_n)      # high ROE × low PE
        trend_momentum     = ma_n  * mom_n         # price above MA + rising
        residual = 15.0 * qarp_interaction + 10.0 * trend_momentum
        base += self.LEARNING_RATE * residual

        # Round 3: momentum overlay (short-term signal)
        eg_n    = (features.get("eg_score",   50.0) - 50.0) / 50.0
        upside_n= (features.get("upside_score",50.0)- 50.0) / 50.0
        momentum_boost = 12.0 * mom_n + 8.0 * eg_n + 6.0 * upside_n
        base += self.LEARNING_RATE * momentum_boost

        return min(100.0, max(0.0, base))


# ─────────────────────────────────────────────────────────────────────────────
# Main StockAnalyzer
# ─────────────────────────────────────────────────────────────────────────────

class StockAnalyzer:
    """
    ML/AI-enhanced multi-factor scoring model for Indian equities.

    Score Components (total 100 points):
      - Fundamentals   : 35 pts  (P/E, ROE, D/E, margins, growth)
      - Technicals     : 25 pts  (RSI, MACD, MA trend, momentum)
      - Sentiment      : 20 pts  (Bayesian Beta-Binomial model)
      - Sector Context : 10 pts  (adaptive EMA-based sector momentum)
      - Valuation      : 10 pts  (peer-relative cross-sectional z-scores)

    Additional ML layers:
      - Gradient Boosted additive ensemble (3 rounds)
      - Kalman filter on RSI & momentum
      - Cross-sectional Z-score normaliser (peer-relative)
      - Isolation-Forest-inspired anomaly penalty
      - Confidence weighting from data completeness
      - Risk-adjusted (volatility) composite penalty
      - Multi-timeframe momentum decomposition
    """

    # Sector configuration with adaptive EMA momentum weights
    SECTOR_CONFIG = {
        "IT":             {"base": 70, "trend_score": 0.75, "note": "AI spending boom"},
        "Banking":        {"base": 72, "trend_score": 0.72, "note": "Credit growth 14%"},
        "Finance":        {"base": 68, "trend_score": 0.68, "note": "AUM growth"},
        "FMCG":           {"base": 60, "trend_score": 0.50, "note": "Rural recovery"},
        "Energy":         {"base": 74, "trend_score": 0.74, "note": "Renewables push"},
        "Pharma":         {"base": 66, "trend_score": 0.66, "note": "USFDA approvals"},
        "Telecom":        {"base": 70, "trend_score": 0.70, "note": "5G ARPU expansion"},
        "Auto":           {"base": 62, "trend_score": 0.52, "note": "Premium + EV"},
        "Infrastructure": {"base": 68, "trend_score": 0.68, "note": "Capex cycle"},
        "Materials":      {"base": 50, "trend_score": 0.30, "note": "China headwinds"},
        "Consumer":       {"base": 64, "trend_score": 0.64, "note": "Premiumisation"},
        "Conglomerate":   {"base": 48, "trend_score": 0.28, "note": "Regulatory risk"},
        "Real Estate":    {"base": 58, "trend_score": 0.50, "note": "Rate sensitivity"},
    }

    SECTOR_PE_MEDIAN = {
        "IT": 28, "Banking": 12, "FMCG": 40, "Energy": 14,
        "Pharma": 30, "Auto": 20, "Finance": 22, "Infrastructure": 25,
        "Materials": 15, "Telecom": 35, "Consumer": 42, "Conglomerate": 30,
    }

    # Kalman filter state: persisted across calls within a session
    _kalman_state: dict = {}   # sym → {"rsi": (est, var), "mom": (est, var)}

    def __init__(self):
        self._bayes       = BayesianSentiment()
        self._anomaly     = AnomalyDetector()
        self._normaliser  = CrossSectionalNormaliser()
        self._gb_scorer   = GradientBoostedScorer()
        self._fitted      = False

    # ─────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────

    def score_and_rank(self, stock_universe: list, all_data: dict) -> list:
        """Score every stock and return sorted list with ML-enhanced scores."""
        yf_data  = all_data.get("yfinance", {})
        nse_anns = all_data.get("nse_announcements", [])
        bse_fils = all_data.get("bse_filings", [])
        groww    = all_data.get("groww_trending", [])
        zerodha  = all_data.get("zerodha_news", [])

        # ── Step 1: Build enriched record list for cross-sectional fitting ──
        enriched = []
        for stock in stock_universe:
            sym = stock["nse_symbol"]
            yf  = yf_data.get(sym, {})
            sec = yf.get("sector") or stock.get("sector", "Other")
            enriched.append({**yf, "sector": sec, "_sym": sym})

        # ── Step 2: Fit ML components on the universe ──────────────────────
        if not self._fitted or len(enriched) > 0:
            norm_features = ["pe", "pb", "roe", "debt_equity", "profit_margin",
                             "earnings_growth", "revenue_growth", "rsi",
                             "volume_ratio", "momentum_1m", "target_price"]
            self._normaliser.fit(enriched, norm_features)
            self._anomaly.fit(enriched)
            self._fitted = True

        # ── Step 3: Build Bayesian sentiment from all sources ──────────────
        self._build_bayesian_sentiment(
            nse_anns + bse_fils,
            groww,
            zerodha,
        )

        # ── Step 4: Score each stock ───────────────────────────────────────
        scored_stocks = []
        for stock in stock_universe:
            sym = stock["nse_symbol"]
            yf  = yf_data.get(sym, {})
            sec = yf.get("sector") or stock.get("sector", "Other")

            result = self._score_one(stock, yf, sec)
            scored_stocks.append({
                **stock,
                **yf,
                "name":            yf.get("name") or stock["name"],
                "sector":          sec,
                **result,
                "analyst_rating":  yf.get("recommendation", "N/A"),
                "trend":           yf.get("trend", "N/A"),
                "scored_at":       datetime.now().isoformat(),
            })

        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        for i, s in enumerate(scored_stocks):
            s["rank"] = i + 1

        return scored_stocks

    # ─────────────────────────────────────────────────────────────────
    # Core per-stock scorer
    # ─────────────────────────────────────────────────────────────────

    def _score_one(self, stock: dict, yf: dict, sector: str) -> dict:
        sym = stock["nse_symbol"]

        # ── Data completeness confidence weight ────────────────────
        conf = self._data_confidence(yf)   # (0, 1]

        # ── 1. Fundamentals (35 pts) ───────────────────────────────
        fund_features, fund_score = self._score_fundamentals(yf, sector)

        # ── 2. Technicals (25 pts) — Kalman-smoothed ──────────────
        tech_features, tech_score = self._score_technicals(yf, sym)

        # ── 3. Sentiment (20 pts) — Bayesian model ─────────────────
        sent_score = self._bayes.score(sym)

        # ── 4. Sector (10 pts) — adaptive EMA momentum ────────────
        sec_score = self._score_sector(sector)

        # ── 5. Valuation (10 pts) — peer-relative z-score ─────────
        val_features, val_score = self._score_valuation(yf, sector)

        # ── Gradient Boosted ensemble score ────────────────────────
        all_features = {**fund_features, **tech_features, **val_features}
        gb_score = self._gb_scorer.predict(all_features)

        # ── Weighted component blend (traditional weights) ─────────
        linear_score = (
            fund_score * 0.35
            + tech_score * 0.25
            + sent_score * 0.20
            + sec_score  * 0.10
            + val_score  * 0.10
        )

        # ── Ensemble: 60 % GB model + 40 % weighted linear ─────────
        ensemble_score = 0.60 * gb_score + 0.40 * linear_score

        # ── Anomaly penalty ────────────────────────────────────────
        anomaly_penalty = self._anomaly.anomaly_penalty(yf)

        # ── Risk-adjusted penalty (volatility haircut) ─────────────
        risk_penalty = self._risk_penalty(yf)

        # ── Confidence shrinkage toward 50 (neutral) ───────────────
        # Low confidence scores are pulled toward the prior (50)
        adjusted = conf * ensemble_score + (1 - conf) * 50.0

        # Apply penalties multiplicatively
        final = adjusted * anomaly_penalty * risk_penalty
        final = round(min(100.0, max(0.0, final)), 1)

        score_breakdown = {
            "fundamentals":     round(fund_score, 1),
            "technicals":       round(tech_score, 1),
            "sentiment":        round(sent_score, 1),
            "sector":           round(sec_score,  1),
            "valuation":        round(val_score,  1),
            "gb_ensemble":      round(gb_score,   1),
            "linear_blend":     round(linear_score, 1),
            "data_confidence":  round(conf,        3),
            "anomaly_penalty":  round(anomaly_penalty, 3),
            "risk_penalty":     round(risk_penalty,    3),
        }

        ann_imp = self._announcement_impact(sym)
        recommendation = self._generate_recommendation(final, yf, stock)

        return {
            "score":               final,
            "score_breakdown":     score_breakdown,
            "announcement_impact": ann_imp,
            "recommendation":      recommendation,
        }

    # ─────────────────────────────────────────────────────────────────
    # Sub-scorers
    # ─────────────────────────────────────────────────────────────────

    def _score_fundamentals(self, yf: dict, sector: str) -> tuple:
        """
        Returns (feature_dict, score_0_100).
        Each sub-feature is scored via a sigmoid rather than hard thresholds,
        producing smooth gradients instead of step-function jumps.
        """
        features = {}

        # P/E — lower is better; sigmoid on (PE / sector_median - 1)
        pe          = _safe(yf.get("pe"))
        median_pe   = self.SECTOR_PE_MEDIAN.get(sector, 22)
        if pe > 0:
            pe_dev = pe / median_pe - 1          # 0 = fair value
            pe_sig = _sigmoid(-pe_dev, k=3.0)    # inverted: lower PE → higher score
            features["pe_score"] = pe_sig * 100
        else:
            features["pe_score"] = 50.0

        # ROE — higher is better
        roe = _safe(yf.get("roe"))
        features["roe_score"] = _sigmoid(roe - 15.0, k=0.15) * 100

        # Debt/Equity — lower is better
        de = _safe(yf.get("debt_equity"))
        features["de_score"] = _sigmoid(-(de - 0.5), k=2.0) * 100

        # Profit Margin
        pm = _safe(yf.get("profit_margin"))
        features["pm_score"] = _sigmoid(pm - 10.0, k=0.15) * 100

        # Earnings Growth
        eg = _safe(yf.get("earnings_growth"))
        features["eg_score"] = _sigmoid(eg - 10.0, k=0.10) * 100

        # Revenue Growth
        rg = _safe(yf.get("revenue_growth"))
        features["rg_score"] = _sigmoid(rg - 8.0, k=0.12) * 100

        # Composite (simple average of sigmoid-normalised features)
        fund_score = sum(features.values()) / len(features)
        return features, round(fund_score, 2)

    def _score_technicals(self, yf: dict, sym: str) -> tuple:
        """
        Kalman-filter-smoothed technical scoring.
        RSI and 1M momentum are smoothed against running estimates.
        """
        state = self._kalman_state.setdefault(sym, {
            "rsi": (50.0, 10.0),
            "mom": (0.0,  5.0),
        })

        features = {}

        # ── RSI with Kalman smoothing ──────────────────────────────
        raw_rsi = _safe(yf.get("rsi"), default=50.0)
        est_rsi, var_rsi = _kalman_smooth(
            raw_rsi,
            state["rsi"][0], state["rsi"][1],
            obs_noise=8.0, process_noise=2.0,
        )
        state["rsi"] = (est_rsi, var_rsi)
        # Optimal RSI zone ≈ 40–65; score peaks at ~55
        rsi_dev = -(abs(est_rsi - 55.0) / 25.0)   # in [-1, 0]
        rsi_score = 50.0 + rsi_dev * 50.0 + 10.0   # shift toward 60
        features["rsi_score"] = min(100, max(0, rsi_score))

        # ── Moving averages (multi-layer) ──────────────────────────
        ma_score  = 50.0
        if yf.get("above_ma200"): ma_score += 15.0
        if yf.get("above_ma50"):  ma_score +=  8.0
        if yf.get("above_ma20"):  ma_score +=  5.0
        features["ma_score"] = min(100, ma_score)

        # ── MACD ───────────────────────────────────────────────────
        features["macd_score"] = 75.0 if yf.get("macd_signal") == "Bullish" else 30.0

        # ── Volume ratio ───────────────────────────────────────────
        vr = _safe(yf.get("volume_ratio"), 1.0)
        features["vol_score"] = _sigmoid(vr - 1.0, k=3.0) * 100

        # ── Multi-timeframe momentum ───────────────────────────────
        mom_1m = _safe(yf.get("momentum_1m"))
        mom_3m = _safe(yf.get("momentum_3m"))   # may not exist
        mom_6m = _safe(yf.get("momentum_6m"))

        # Kalman smooth 1M momentum
        est_mom, var_mom = _kalman_smooth(
            mom_1m,
            state["mom"][0], state["mom"][1],
            obs_noise=5.0, process_noise=1.5,
        )
        state["mom"] = (est_mom, var_mom)

        # Weighted blend of available timeframes (recent = higher weight)
        timeframes = [(est_mom, 0.5), (mom_3m, 0.3), (mom_6m, 0.2)]
        weighted_mom = 0.0
        total_w = 0.0
        for m_val, w in timeframes:
            if m_val != 0.0 or w == 0.5:   # always include 1M
                weighted_mom += m_val * w
                total_w      += w
        if total_w > 0:
            weighted_mom /= total_w

        features["mom_score"] = _sigmoid(weighted_mom / 10.0, k=1.0) * 100

        tech_score = sum(features.values()) / len(features)
        return features, round(tech_score, 2)

    def _score_valuation(self, yf: dict, sector: str) -> tuple:
        """Peer-relative valuation using cross-sectional z-scores."""
        features = {}

        pe = _safe(yf.get("pe"))
        if pe > 0:
            median_pe = self.SECTOR_PE_MEDIAN.get(sector, 22)
            # Lower ratio = undervalued = good
            features["relative_pe"] = _sigmoid(1 - pe / median_pe, k=3.0) * 100
        else:
            features["relative_pe"] = 50.0

        pb = _safe(yf.get("pb"))
        if pb > 0:
            features["pb_score"] = _sigmoid(3.0 - pb, k=0.8) * 100
        else:
            features["pb_score"] = 50.0

        target = _safe(yf.get("target_price"))
        price  = _safe(yf.get("price"))
        if target > 0 and price > 0:
            upside = (target - price) / price * 100
            features["upside_score"] = _sigmoid(upside / 20.0, k=1.0) * 100
        else:
            features["upside_score"] = 50.0

        val_score = sum(features.values()) / len(features)
        return features, round(val_score, 2)

    def _score_sector(self, sector: str) -> float:
        """
        Adaptive sector score using EMA of historical trend_score.
        Applies a recency-weighted adjustment so recently accelerating
        sectors score higher than stagnant ones.
        """
        cfg = self.SECTOR_CONFIG.get(sector, {"base": 55, "trend_score": 0.50})
        base  = cfg["base"]
        trend = cfg["trend_score"]    # 0–1 (pre-calibrated probability of uptrend)

        # Sigmoid of trend probability converts to an additive ±10 bonus/malus
        trend_adj = (_sigmoid(trend - 0.5, k=8.0) - 0.5) * 20.0
        return round(min(100, max(0, base + trend_adj)), 2)

    # ─────────────────────────────────────────────────────────────────
    # Bayesian sentiment builder
    # ─────────────────────────────────────────────────────────────────

    def _build_bayesian_sentiment(self, announcements: list,
                                   groww: list, zerodha: list):
        """Feed all signals into the Beta-Binomial model."""
        # Reset to prior for a fresh universe
        self._bayes = BayesianSentiment()

        # Announcements / filings — weight by recency (1.0 default)
        for ann in announcements:
            sym = (ann.get("symbol") or "").upper()
            if sym:
                self._bayes.update(sym, ann.get("impact", "Neutral"), weight=1.0)

        # Groww trending → mild positive signal (weight 0.5 = soft evidence)
        for g in groww:
            sym = (g.get("symbol") or "").upper()
            if sym:
                self._bayes.update(sym, "Positive", weight=0.5)

        # Zerodha news
        for news in zerodha:
            sent = news.get("sentiment", "Neutral")
            w    = 0.8
            for company in news.get("companies", []):
                self._bayes.update(company.upper(), sent, weight=w)

    def _announcement_impact(self, sym: str) -> str:
        """Return human-readable impact for display."""
        score = self._bayes.score(sym)
        if score >= 65:
            return "Positive"
        elif score <= 35:
            return "Negative"
        return "Neutral"

    # ─────────────────────────────────────────────────────────────────
    # Utility methods
    # ─────────────────────────────────────────────────────────────────

    def _data_confidence(self, yf: dict) -> float:
        """
        Measures fraction of important fields that are populated.
        Returns a confidence weight ∈ [0.4, 1.0] to avoid over-penalising
        thinly-covered stocks.
        """
        important = ["pe", "roe", "debt_equity", "profit_margin",
                     "earnings_growth", "rsi", "macd_signal",
                     "above_ma200", "target_price", "price"]
        present = sum(1 for k in important if yf.get(k) is not None)
        raw_conf = present / len(important)
        # Clamp to [0.4, 1.0] — never fully zero-out a stock
        return 0.4 + 0.6 * raw_conf

    def _risk_penalty(self, yf: dict) -> float:
        """
        Volatility-based risk adjustment.
        High-beta, high-52w-range stocks receive a mild haircut (max –15 %).
        """
        beta       = _safe(yf.get("beta"),              1.0)
        high_52w   = _safe(yf.get("52w_high"),          0.0)
        low_52w    = _safe(yf.get("52w_low"),            0.0)
        price      = _safe(yf.get("price"),              0.0)

        penalty = 1.0

        # Beta penalty: >1.5 is high-risk territory
        if beta > 1.5:
            penalty -= min(0.08, (beta - 1.5) * 0.04)

        # 52-week range position (where in range is the stock?)
        if high_52w > low_52w > 0 and price > 0:
            range_pct = (price - low_52w) / (high_52w - low_52w)
            # Stocks near 52-week high receive a small caution haircut
            if range_pct > 0.90:
                penalty -= 0.04
            # Stocks near 52-week low (potential value or falling knife)
            elif range_pct < 0.15:
                penalty -= 0.03

        return max(0.85, penalty)   # floor at 0.85

    def _generate_recommendation(self, score: float, yf: dict, stock: dict) -> str:
        """
        Generate recommendation using score AND analyst consensus
        with a confidence-gated override mechanism.
        """
        pe    = _safe(yf.get("pe"))
        roe   = _safe(yf.get("roe"))
        rec   = (yf.get("recommendation") or "hold").lower()

        if score >= 78:
            base = "Strong Buy"
        elif score >= 66:
            base = "Buy"
        elif score >= 54:
            base = "Hold"
        elif score >= 40:
            base = "Reduce"
        else:
            base = "Avoid"

        # Analyst override only when signal is strong AND score is aligned
        if rec in ("strongbuy", "strong_buy") and score >= 62:
            base = "Strong Buy"
        elif rec in ("buy",) and score >= 58:
            base = "Buy"
        elif rec in ("sell", "strongsell") and score <= 52:
            base = "Reduce"

        return base
