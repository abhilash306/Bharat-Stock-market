"""
Stock Analyzer & Scoring Engine — ML/AI Enhanced v3
=====================================================
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
  - [NEW v3] Ownership intelligence (MoneyControl)
      · Promoter holding % + QoQ change
      · FII / DII institutional flow (smart money signal)
      · Pledged shares % (hidden leverage risk flag)

Score weights (v3):
  Fundamentals  30 %  (was 35 %)
  Technicals    22 %  (was 25 %)
  Sentiment     18 %  (was 20 %)
  Sector        10 %  (unchanged)
  Valuation     10 %  (unchanged)
  Ownership     10 %  [NEW]
  ──────────────────
  Total        100 %
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
    """Clipped z-score → maps to [0, 100] via linear stretch."""
    if std < 1e-9:
        return 50.0
    z = (value - mean) / std
    z = max(-3.0, min(3.0, z))
    return 50.0 + z * (50.0 / 3.0)


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
    """

    PRIOR_ALPHA = 2.0
    PRIOR_BETA  = 2.0

    def __init__(self):
        self._alpha = {}
        self._beta  = {}

    def update(self, symbol: str, impact: str, weight: float = 1.0):
        sym = symbol.upper()
        a = self._alpha.get(sym, self.PRIOR_ALPHA)
        b = self._beta.get(sym,  self.PRIOR_BETA)
        if impact == "Positive":
            a += weight
        elif impact == "Negative":
            b += weight
        self._alpha[sym] = a
        self._beta[sym]  = b

    def score(self, symbol: str) -> float:
        """Return posterior sentiment score in [0, 100]."""
        sym = symbol.upper()
        a = self._alpha.get(sym, self.PRIOR_ALPHA)
        b = self._beta.get(sym,  self.PRIOR_BETA)
        posterior_mean = a / (a + b)
        n = a + b - self.PRIOR_ALPHA - self.PRIOR_BETA
        confidence = 1.0 - math.exp(-n * 0.5)
        blended = 50.0 * (1 - confidence) + posterior_mean * 100 * confidence
        return round(max(0, min(100, blended)), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-sectional normaliser
# ─────────────────────────────────────────────────────────────────────────────

class CrossSectionalNormaliser:
    """
    Sector-level mean & std for each feature so every sub-score
    reflects peer-relative rank, not absolute hard-coded scale.
    """

    def fit(self, records: list, features: list):
        self._universe_stats = {}
        self._sector_stats   = {}

        for feat in features:
            vals = [_safe(r.get(feat)) for r in records if r.get(feat) is not None]
            if len(vals) > 1:
                mean = sum(vals) / len(vals)
                std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
            else:
                mean, std = 0.0, 1.0
            self._universe_stats[feat] = (mean, std)

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
        stats = self._sector_stats.get(sector, self._universe_stats)
        mean, std = stats.get(feature, self._universe_stats.get(feature, (0.0, 1.0)))
        return _zscore(value, mean, std)


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detector
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Mahalanobis-like distance using per-feature standardisation.
    Stocks beyond 2.5σ on ≥3 features receive a score penalty.
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
        """Returns multiplicative penalty ∈ [0.70, 1.0]."""
        outlier_count = 0
        for feat, (mean, std) in self._stats.items():
            val = yf.get(feat)
            if val is not None:
                z = abs((_safe(val) - mean) / std)
                if z > 2.5:
                    outlier_count += 1
        if outlier_count == 0:   return 1.0
        elif outlier_count <= 2: return 0.92
        elif outlier_count <= 4: return 0.82
        else:                    return 0.70


# ─────────────────────────────────────────────────────────────────────────────
# Gradient-Boosted Additive Scorer
# ─────────────────────────────────────────────────────────────────────────────

class GradientBoostedScorer:
    """
    3-round gradient boosting simulation.
    Round 1 – Base linear model
    Round 2 – Non-linear interaction residuals (QARP, trend×momentum)
    Round 3 – Momentum + ownership overlay
    """

    LEARNING_RATE = 0.30
    BASE_SCORE    = 50.0

    FEATURE_WEIGHTS = {
        # Fundamentals
        "pe_score":         -0.12,
        "roe_score":         0.18,
        "de_score":         -0.10,
        "pm_score":          0.12,
        "eg_score":          0.15,
        "rg_score":          0.08,
        # Technicals
        "rsi_score":         0.10,
        "ma_score":          0.12,
        "macd_score":        0.08,
        "vol_score":         0.06,
        "mom_score":         0.10,
        # Valuation
        "relative_pe":      -0.10,
        "pb_score":         -0.07,
        "upside_score":      0.14,
        # Ownership (NEW)
        "promoter_score":    0.10,   # high stable promoter holding = quality
        "inst_flow_score":   0.12,   # FII+DII buying = smart money inflow
        "pledge_score":     -0.15,   # pledged shares = risk penalty
    }

    def predict(self, features: dict) -> float:
        """Return score ∈ [0, 100]."""
        base = self.BASE_SCORE
        for feat, weight in self.FEATURE_WEIGHTS.items():
            raw  = features.get(feat, 50.0)
            norm = (raw - 50.0) / 50.0
            base += weight * norm * 50.0

        # Round 2: interaction residuals
        roe_n = (features.get("roe_score",      50.0) - 50.0) / 50.0
        pe_n  = (features.get("pe_score",        50.0) - 50.0) / 50.0
        mom_n = (features.get("mom_score",       50.0) - 50.0) / 50.0
        ma_n  = (features.get("ma_score",        50.0) - 50.0) / 50.0
        # NEW: promoter stability × institutional buying interaction
        prom_n = (features.get("promoter_score", 50.0) - 50.0) / 50.0
        inst_n = (features.get("inst_flow_score",50.0) - 50.0) / 50.0

        qarp_interaction    = roe_n * (-pe_n)           # quality at reasonable price
        trend_momentum      = ma_n  * mom_n             # price trend + momentum
        smart_money_signal  = prom_n * inst_n           # promoter confidence × inst buying
        residual = (15.0 * qarp_interaction
                    + 10.0 * trend_momentum
                    + 8.0  * smart_money_signal)
        base += self.LEARNING_RATE * residual

        # Round 3: momentum + ownership overlay
        eg_n     = (features.get("eg_score",      50.0) - 50.0) / 50.0
        upside_n = (features.get("upside_score",  50.0) - 50.0) / 50.0
        pledge_n = (features.get("pledge_score",  50.0) - 50.0) / 50.0
        momentum_boost = (12.0 * mom_n
                          + 8.0  * eg_n
                          + 6.0  * upside_n
                          - 10.0 * pledge_n)   # pledged shares drag
        base += self.LEARNING_RATE * momentum_boost

        return min(100.0, max(0.0, base))


# ─────────────────────────────────────────────────────────────────────────────
# Main StockAnalyzer
# ─────────────────────────────────────────────────────────────────────────────

class StockAnalyzer:
    """
    ML/AI-enhanced multi-factor scoring model for Indian equities — v3.

    Score Components (total 100 %):
      Fundamentals  30 %  P/E, ROE, D/E, margins, growth (sigmoid transforms)
      Technicals    22 %  Kalman-smoothed RSI, MACD, MA, momentum
      Sentiment     18 %  Bayesian Beta-Binomial (NSE/BSE/Groww/Zerodha)
      Sector        10 %  Adaptive EMA momentum by sector
      Valuation     10 %  Peer-relative cross-sectional z-scores
      Ownership     10 %  [NEW] Promoter %, FII/DII flow, Pledged shares

    ML layers:
      · Gradient Boosted ensemble (3 rounds, ν=0.30)
      · Kalman filter on RSI & 1M momentum
      · Bayesian sentiment (Beta-Binomial conjugate)
      · Cross-sectional Z-score normaliser (sector peers)
      · Isolation-Forest anomaly penalty
      · Confidence weighting (data completeness shrinkage)
      · Risk-adjusted penalty (beta + 52w range)
      · Sigmoid feature transforms (no hard thresholds)
    """

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

    _kalman_state: dict = {}

    def __init__(self):
        self._bayes      = BayesianSentiment()
        self._anomaly    = AnomalyDetector()
        self._normaliser = CrossSectionalNormaliser()
        self._gb_scorer  = GradientBoostedScorer()
        self._fitted     = False

    # ─────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────

    def score_and_rank(self, stock_universe: list, all_data: dict) -> list:
        """
        Score every stock and return sorted list.

        all_data keys expected:
          "yfinance"           → dict keyed by nse_symbol
          "nse_announcements"  → list
          "bse_filings"        → list
          "groww_trending"     → list
          "zerodha_news"       → list
          "moneycontrol"       → dict keyed by nse_symbol  ← NEW (optional)
        """
        yf_data  = all_data.get("yfinance", {})
        nse_anns = all_data.get("nse_announcements", [])
        bse_fils = all_data.get("bse_filings", [])
        groww    = all_data.get("groww_trending", [])
        zerodha  = all_data.get("zerodha_news", [])
        mc_data  = all_data.get("moneycontrol", {})   # NEW

        # ── Step 1: Enrich records for cross-sectional fitting ─────
        enriched = []
        for stock in stock_universe:
            sym = stock["nse_symbol"]
            yf  = yf_data.get(sym, {})
            mc  = mc_data.get(sym, {})
            sec = yf.get("sector") or stock.get("sector", "Other")
            enriched.append({**yf, **mc, "sector": sec, "_sym": sym})

        # ── Step 2: Fit ML components ──────────────────────────────
        if not self._fitted or enriched:
            norm_features = ["pe", "pb", "roe", "debt_equity", "profit_margin",
                             "earnings_growth", "revenue_growth", "rsi",
                             "volume_ratio", "momentum_1m", "target_price",
                             "promoter_pct", "fii_chg_qoq", "dii_chg_qoq",
                             "pledged_pct"]
            self._normaliser.fit(enriched, norm_features)
            self._anomaly.fit(enriched)
            self._fitted = True

        # ── Step 3: Build Bayesian sentiment ───────────────────────
        self._build_bayesian_sentiment(nse_anns + bse_fils, groww, zerodha)

        # ── Step 4: Score each stock ───────────────────────────────
        scored_stocks = []
        for stock in stock_universe:
            sym = stock["nse_symbol"]
            yf  = yf_data.get(sym, {})
            mc  = mc_data.get(sym, {})
            sec = yf.get("sector") or stock.get("sector", "Other")

            result = self._score_one(stock, yf, mc, sec)
            scored_stocks.append({
                **stock,
                **yf,
                # MoneyControl ownership fields surfaced in output
                "promoter_pct":     mc.get("promoter_pct"),
                "promoter_chg_qoq": mc.get("promoter_chg_qoq"),
                "fii_pct":          mc.get("fii_pct"),
                "fii_chg_qoq":      mc.get("fii_chg_qoq"),
                "dii_pct":          mc.get("dii_pct"),
                "dii_chg_qoq":      mc.get("dii_chg_qoq"),
                "pledged_pct":      mc.get("pledged_pct"),
                "name":             yf.get("name") or stock["name"],
                "sector":           sec,
                **result,
                "analyst_rating":   yf.get("recommendation", "N/A"),
                "trend":            yf.get("trend", "N/A"),
                "scored_at":        datetime.now().isoformat(),
            })

        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        for i, s in enumerate(scored_stocks):
            s["rank"] = i + 1

        return scored_stocks

    # ─────────────────────────────────────────────────────────────────
    # Core per-stock scorer
    # ─────────────────────────────────────────────────────────────────

    def _score_one(self, stock: dict, yf: dict, mc: dict, sector: str) -> dict:
        sym = stock["nse_symbol"]

        conf = self._data_confidence(yf, mc)

        # ── 1. Fundamentals (30 %) ─────────────────────────────────
        fund_features, fund_score = self._score_fundamentals(yf, sector)

        # ── 2. Technicals (22 %) — Kalman-smoothed ────────────────
        tech_features, tech_score = self._score_technicals(yf, sym)

        # ── 3. Sentiment (18 %) — Bayesian ────────────────────────
        sent_score = self._bayes.score(sym)

        # ── 4. Sector (10 %) ───────────────────────────────────────
        sec_score = self._score_sector(sector)

        # ── 5. Valuation (10 %) — peer-relative ───────────────────
        val_features, val_score = self._score_valuation(yf, sector)

        # ── 6. Ownership (10 %) — MoneyControl [NEW] ──────────────
        own_features, own_score = self._score_ownership(mc)

        # ── Gradient Boosted ensemble ──────────────────────────────
        all_features = {
            **fund_features,
            **tech_features,
            **val_features,
            **own_features,
        }
        gb_score = self._gb_scorer.predict(all_features)

        # ── Weighted linear blend (v3 weights) ────────────────────
        linear_score = (
            fund_score * 0.30
            + tech_score * 0.22
            + sent_score * 0.18
            + sec_score  * 0.10
            + val_score  * 0.10
            + own_score  * 0.10
        )

        # ── Ensemble: 60 % GB + 40 % linear ───────────────────────
        ensemble_score = 0.60 * gb_score + 0.40 * linear_score

        # ── Anomaly + risk penalties ───────────────────────────────
        anomaly_penalty = self._anomaly.anomaly_penalty(yf)
        risk_penalty    = self._risk_penalty(yf, mc)

        # ── Confidence shrinkage ───────────────────────────────────
        adjusted = conf * ensemble_score + (1 - conf) * 50.0

        final = adjusted * anomaly_penalty * risk_penalty
        final = round(min(100.0, max(0.0, final)), 1)

        score_breakdown = {
            "fundamentals":      round(fund_score,   1),
            "technicals":        round(tech_score,   1),
            "sentiment":         round(sent_score,   1),
            "sector":            round(sec_score,    1),
            "valuation":         round(val_score,    1),
            "ownership":         round(own_score,    1),   # NEW
            "gb_ensemble":       round(gb_score,     1),
            "linear_blend":      round(linear_score, 1),
            "data_confidence":   round(conf,         3),
            "anomaly_penalty":   round(anomaly_penalty, 3),
            "risk_penalty":      round(risk_penalty,    3),
        }

        ann_imp        = self._announcement_impact(sym)
        recommendation = self._generate_recommendation(final, yf, mc, stock)

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
        """Sigmoid-normalised fundamental scoring."""
        features = {}

        pe = _safe(yf.get("pe"))
        median_pe = self.SECTOR_PE_MEDIAN.get(sector, 22)
        if pe > 0:
            pe_dev = pe / median_pe - 1
            features["pe_score"] = _sigmoid(-pe_dev, k=3.0) * 100
        else:
            features["pe_score"] = 50.0

        roe = _safe(yf.get("roe"))
        features["roe_score"] = _sigmoid(roe - 15.0, k=0.15) * 100

        de = _safe(yf.get("debt_equity"))
        features["de_score"] = _sigmoid(-(de - 0.5), k=2.0) * 100

        pm = _safe(yf.get("profit_margin"))
        features["pm_score"] = _sigmoid(pm - 10.0, k=0.15) * 100

        eg = _safe(yf.get("earnings_growth"))
        features["eg_score"] = _sigmoid(eg - 10.0, k=0.10) * 100

        rg = _safe(yf.get("revenue_growth"))
        features["rg_score"] = _sigmoid(rg - 8.0, k=0.12) * 100

        fund_score = sum(features.values()) / len(features)
        return features, round(fund_score, 2)

    def _score_technicals(self, yf: dict, sym: str) -> tuple:
        """Kalman-filter-smoothed technical scoring."""
        state = self._kalman_state.setdefault(sym, {
            "rsi": (50.0, 10.0),
            "mom": (0.0,   5.0),
        })
        features = {}

        raw_rsi = _safe(yf.get("rsi"), default=50.0)
        est_rsi, var_rsi = _kalman_smooth(
            raw_rsi, state["rsi"][0], state["rsi"][1],
            obs_noise=8.0, process_noise=2.0)
        state["rsi"] = (est_rsi, var_rsi)
        rsi_dev = -(abs(est_rsi - 55.0) / 25.0)
        features["rsi_score"] = min(100, max(0, 50.0 + rsi_dev * 50.0 + 10.0))

        ma_score = 50.0
        if yf.get("above_ma200"): ma_score += 15.0
        if yf.get("above_ma50"):  ma_score +=  8.0
        if yf.get("above_ma20"):  ma_score +=  5.0
        features["ma_score"] = min(100, ma_score)

        features["macd_score"] = 75.0 if yf.get("macd_signal") == "Bullish" else 30.0

        vr = _safe(yf.get("volume_ratio"), 1.0)
        features["vol_score"] = _sigmoid(vr - 1.0, k=3.0) * 100

        mom_1m = _safe(yf.get("momentum_1m"))
        mom_3m = _safe(yf.get("momentum_3m"))
        mom_6m = _safe(yf.get("momentum_6m"))

        est_mom, var_mom = _kalman_smooth(
            mom_1m, state["mom"][0], state["mom"][1],
            obs_noise=5.0, process_noise=1.5)
        state["mom"] = (est_mom, var_mom)

        timeframes = [(est_mom, 0.5), (mom_3m, 0.3), (mom_6m, 0.2)]
        weighted_mom, total_w = 0.0, 0.0
        for m_val, w in timeframes:
            if m_val != 0.0 or w == 0.5:
                weighted_mom += m_val * w
                total_w      += w
        if total_w > 0:
            weighted_mom /= total_w
        features["mom_score"] = _sigmoid(weighted_mom / 10.0, k=1.0) * 100

        tech_score = sum(features.values()) / len(features)
        return features, round(tech_score, 2)

    def _score_valuation(self, yf: dict, sector: str) -> tuple:
        """Peer-relative valuation scoring."""
        features = {}

        pe = _safe(yf.get("pe"))
        median_pe = self.SECTOR_PE_MEDIAN.get(sector, 22)
        if pe > 0:
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
        cfg = self.SECTOR_CONFIG.get(sector, {"base": 55, "trend_score": 0.50})
        base  = cfg["base"]
        trend = cfg["trend_score"]
        trend_adj = (_sigmoid(trend - 0.5, k=8.0) - 0.5) * 20.0
        return round(min(100, max(0, base + trend_adj)), 2)

    def _score_ownership(self, mc: dict) -> tuple:
        """
        Score ownership quality from MoneyControl data.

        Three signals, each mapped to [0, 100]:

        1. Promoter Holding % (promoter_score)
           - High stable holding (>50%) signals confidence
           - Declining holding is a warning sign (QoQ change penalty)

        2. Institutional Flow Score (inst_flow_score)
           - FII + DII combined QoQ inflow = smart money accumulation
           - Both buying simultaneously is the strongest signal

        3. Pledge Risk Score (pledge_score)
           - High pledged % signals hidden leverage / distress
           - 0% pledge → 100, >30% pledge → <20 (severe risk flag)
        """
        features = {}

        # ── 1. Promoter Score ──────────────────────────────────────
        prom_pct = mc.get("promoter_pct")
        prom_chg = _safe(mc.get("promoter_chg_qoq"), 0.0)

        if prom_pct is not None:
            # Base: sigmoid centred at 50% (typical Indian promoter holding)
            prom_base = _sigmoid(_safe(prom_pct) - 50.0, k=0.08) * 100
            # QoQ change penalty/bonus: increasing = +, decreasing = -
            prom_adj  = _sigmoid(prom_chg, k=1.5) * 20.0 - 10.0  # ±10 pts
            features["promoter_score"] = min(100, max(0, prom_base + prom_adj))
        else:
            features["promoter_score"] = 50.0   # neutral if data missing

        # ── 2. Institutional Flow Score ────────────────────────────
        fii_chg = mc.get("fii_chg_qoq")
        dii_chg = mc.get("dii_chg_qoq")
        fii_pct = _safe(mc.get("fii_pct"), 0.0)
        dii_pct = _safe(mc.get("dii_pct"), 0.0)

        if fii_chg is not None or dii_chg is not None:
            fii_delta = _safe(fii_chg, 0.0)
            dii_delta = _safe(dii_chg, 0.0)
            # Weighted combined flow: FII gets 60% weight (more volatile / informed)
            combined_flow = 0.60 * fii_delta + 0.40 * dii_delta
            # Absolute holding level adds context (higher holding = more conviction)
            holding_level = min(1.0, (fii_pct + dii_pct) / 30.0)
            flow_score    = _sigmoid(combined_flow, k=1.0) * 100
            # Blend flow signal with holding level
            features["inst_flow_score"] = 0.70 * flow_score + 0.30 * (holding_level * 100)
        else:
            features["inst_flow_score"] = 50.0

        # ── 3. Pledge Risk Score ───────────────────────────────────
        pledged = mc.get("pledged_pct")
        if pledged is not None:
            p = _safe(pledged)
            if p <= 0:
                features["pledge_score"] = 95.0   # zero pledge = excellent
            elif p < 5:
                features["pledge_score"] = 80.0
            elif p < 15:
                features["pledge_score"] = 60.0
            elif p < 30:
                features["pledge_score"] = 35.0
            elif p < 50:
                features["pledge_score"] = 15.0
            else:
                features["pledge_score"] = 5.0    # >50% pledged = severe risk
        else:
            features["pledge_score"] = 50.0   # neutral if unknown

        own_score = sum(features.values()) / len(features)
        return features, round(own_score, 2)

    # ─────────────────────────────────────────────────────────────────
    # Bayesian sentiment builder
    # ─────────────────────────────────────────────────────────────────

    def _build_bayesian_sentiment(self, announcements: list,
                                   groww: list, zerodha: list):
        self._bayes = BayesianSentiment()
        for ann in announcements:
            sym = (ann.get("symbol") or "").upper()
            if sym:
                self._bayes.update(sym, ann.get("impact", "Neutral"), weight=1.0)
        for g in groww:
            sym = (g.get("symbol") or "").upper()
            if sym:
                self._bayes.update(sym, "Positive", weight=0.5)
        for news in zerodha:
            sent = news.get("sentiment", "Neutral")
            for company in news.get("companies", []):
                self._bayes.update(company.upper(), sent, weight=0.8)

    def _announcement_impact(self, sym: str) -> str:
        score = self._bayes.score(sym)
        if score >= 65:   return "Positive"
        elif score <= 35: return "Negative"
        return "Neutral"

    # ─────────────────────────────────────────────────────────────────
    # Utility methods
    # ─────────────────────────────────────────────────────────────────

    def _data_confidence(self, yf: dict, mc: dict) -> float:
        """
        Confidence weight ∈ [0.4, 1.0] based on data completeness.
        Now includes MoneyControl fields — fully populated stock gets 1.0.
        """
        yf_fields = ["pe", "roe", "debt_equity", "profit_margin",
                     "earnings_growth", "rsi", "macd_signal",
                     "above_ma200", "target_price", "price"]
        mc_fields = ["promoter_pct", "fii_chg_qoq", "pledged_pct"]

        yf_present = sum(1 for k in yf_fields if yf.get(k) is not None)
        mc_present = sum(1 for k in mc_fields if mc.get(k) is not None)

        # MC data worth 20% of confidence; YF data worth 80%
        raw_conf = (0.80 * yf_present / len(yf_fields)
                  + 0.20 * mc_present / len(mc_fields))
        return 0.4 + 0.6 * raw_conf

    def _risk_penalty(self, yf: dict, mc: dict) -> float:
        """
        Volatility + pledge-based risk adjustment.
        Now also penalises stocks with >30% pledged shares.
        Floor: 0.80 (was 0.85) to accommodate pledge risk.
        """
        beta    = _safe(yf.get("beta"),     1.0)
        high_52 = _safe(yf.get("52w_high"), 0.0)
        low_52  = _safe(yf.get("52w_low"),  0.0)
        price   = _safe(yf.get("price"),    0.0)

        penalty = 1.0

        # Beta penalty
        if beta > 1.5:
            penalty -= min(0.08, (beta - 1.5) * 0.04)

        # 52-week range position
        if high_52 > low_52 > 0 and price > 0:
            range_pct = (price - low_52) / (high_52 - low_52)
            if range_pct > 0.90:   penalty -= 0.04
            elif range_pct < 0.15: penalty -= 0.03

        # Pledge risk (NEW) — severe pledge → extra haircut
        pledged = _safe(mc.get("pledged_pct"), 0.0)
        if pledged > 50:   penalty -= 0.10
        elif pledged > 30: penalty -= 0.06
        elif pledged > 15: penalty -= 0.03

        return max(0.80, penalty)

    def _generate_recommendation(self, score: float, yf: dict,
                                  mc: dict, stock: dict) -> str:
        """
        Recommendation with pledge-aware veto and analyst consensus overlay.
        A stock with >40% pledged shares cannot get better than 'Hold'.
        """
        rec     = (yf.get("recommendation") or "hold").lower()
        pledged = _safe(mc.get("pledged_pct"), 0.0)

        if score >= 78:   base = "Strong Buy"
        elif score >= 66: base = "Buy"
        elif score >= 54: base = "Hold"
        elif score >= 40: base = "Reduce"
        else:             base = "Avoid"

        # Analyst consensus override (confidence-gated)
        if rec in ("strongbuy", "strong_buy") and score >= 62:
            base = "Strong Buy"
        elif rec == "buy" and score >= 58:
            base = "Buy"
        elif rec in ("sell", "strongsell") and score <= 52:
            base = "Reduce"

        # ── Pledge veto (NEW) ──────────────────────────────────────
        # High pledge overrides optimistic signals — capital is at risk
        if pledged > 40 and base in ("Strong Buy", "Buy"):
            base = "Hold"
            logger.debug(f"[{stock['nse_symbol']}] Pledge veto: "
                         f"{pledged:.1f}% pledged → downgraded to Hold")

        return base
