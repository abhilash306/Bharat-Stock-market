/* eslint-disable no-unused-vars */
import { useState, useEffect, useCallback } from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
} from "recharts";
import "./App.css";

// utility components remain unchanged
function ScoreRing({ score, size = 90 }) {
  const r = size * 0.38,
    cx = size / 2,
    cy = size / 2,
    circ = 2 * Math.PI * r,
    fill = (score / 100) * circ;
  const c =
    score >= 75
      ? "#00e676"
      : score >= 65
      ? "#69f0ae"
      : score >= 55
      ? "#ffab00"
      : score >= 40
      ? "#ff9800"
      : "#ff5252";
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="#1a2f4a"
        strokeWidth={size * 0.07}
      />
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={c}
        strokeWidth={size * 0.07}
        strokeDasharray={`${fill} ${circ - fill}`}
        strokeLinecap="round"
        style={{
          filter: `drop-shadow(0 0 6px ${c})`,
          transition: "stroke-dasharray 1s ease",
        }}
      />
      <text
        x={cx}
        y={cy + 1}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={c}
        fontSize={size * 0.22}
        fontWeight="bold"
        fontFamily="'Rajdhani', 'Segoe UI', sans-serif"
        style={{ transform: "rotate(90deg)", transformOrigin: `${cx}px ${cy}px` }}
      >
        {score}
      </text>
    </svg>
  );
}

function RSIGauge({ rsi }) {
  const n = parseFloat(rsi) || 50,
    angle = -135 + (n / 100) * 270;
  const c =
    n < 30
      ? "#ff5252"
      : n < 50
      ? "#00e676"
      : n < 70
      ? "#ffab00"
      : "#ff5252";
  return (
    <svg width={120} height={80} viewBox="0 0 120 80">
      {[
        { f: 0, t: 30, c: "#ff525233" },
        { f: 30, t: 70, c: "#00e67622" },
        { f: 70, t: 100, c: "#ff520033" },
      ].map((z) => {
        const s = (-135 + z.f * 2.7) * Math.PI / 180,
          e = (-135 + z.t * 2.7) * Math.PI / 180,
          R = 44,
          cx = 60,
          cy = 60;
        return (
          <path
            key={z.f}
            d={`M${cx} ${cy} L${cx + R * Math.cos(s)} ${cy + R * Math.sin(s)} A${R} ${R} 0 ${z.t - z.f > 50 ? 1 : 0} 1 ${cx + R * Math.cos(e)} ${cy + R * Math.sin(e)}`}
            fill={z.c}
          />
        );
      })}
      <path
        d={`M60 60 L${60 + 38 * Math.cos((angle * Math.PI) / 180)} ${60 + 38 * Math.sin((angle * Math.PI) / 180)}`}
        stroke={c}
        strokeWidth={2.5}
        strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 4px ${c})` }}
      />
      <circle cx={60} cy={60} r={4} fill={c} />
      <text
        x={60}
        y={75}
        textAnchor="middle"
        fill={c}
        fontSize={11}
        fontWeight="bold"
        fontFamily="'Rajdhani', 'Segoe UI', sans-serif"
      >
        {n.toFixed(0)}
      </text>
      <text x={14} y={72} fill="#ff5252" fontSize={8} fontFamily="'Rajdhani', 'Segoe UI', sans-serif">
        30
      </text>
      <text x={96} y={72} fill="#ff5252" fontSize={8} fontFamily="'Rajdhani', 'Segoe UI', sans-serif">
        70
      </text>
    </svg>
  );
}

function Sparkline({ data, color, w = 72, h = 28 }) {
  const vals = data.map((d) => d.v),
    mn = Math.min(...vals),
    mx = Math.max(...vals),
    rng = mx - mn || 1;
  const pts = vals
    .map((v, i) => `${(i / (vals.length - 1)) * w},${h - ((v - mn) / rng) * h}`)
    .join(" ");
  const id = `sg${color.replace("#", "")}`;
  return (
    <svg width={w} height={h}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${id})`} />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
      />
    </svg>
  );
}

function MiniBar({ value, color }) {
  return (
    <div
      style={{
        background: "#0a1628",
        borderRadius: 3,
        height: 6,
        width: "100%",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${Math.min(100, Math.max(0, value))}%`,
          height: "100%",
          background: color,
          borderRadius: 3,
          transition: "width 0.8s ease",
          boxShadow: "0 0 6px " + color + "55",
        }}
      />
    </div>
  );
}

function Badge({ rec }) {
  const m = {
    "Strong Buy": "#00e676",
    Buy: "#69f0ae",
    Hold: "#ffab00",
    Reduce: "#ff9800",
    Avoid: "#ff5252",
  };
  const c = m[rec] || "#667";
  return (
    <span
      style={{
        background: c + "22",
        color: c,
        border: "1px solid " + c + "55",
        padding: "3px 8px",
        borderRadius: 3,
        fontSize: 12,
        letterSpacing: 1.5,
        fontWeight: "bold",
      }}
    >
      {(rec || "N/A").toUpperCase()}
    </span>
  );
}

const impC = (i) => (i === "Positive" ? "#00e676" : i === "Negative" ? "#ff5252" : "#ffab00");
const catC =
  (c) =>
    ({
      Results: "#00e676",
      Dividend: "#69f0ae",
      SEBI: "#ff5252",
      Order: "#00bfff",
      Rating: "#e040fb",
      "Bulk Deal": "#ffab00",
      Management: "#ff9800",
      Regulatory: "#f48fb1",
      Board: "#40c4ff",
      Shareholding: "#b388ff",
    }[c] || "#667");

// color constants used in tables
const SECTOR = {
  IT: { color: "#00e5ff", note: "AI boom, strong deal wins", trend: "UP" },
  Banking: { color: "#00e676", note: "Credit growth 14%, NPA falling", trend: "UP" },
  Energy: { color: "#ffab00", note: "Strong refining margins", trend: "UP" },
  FMCG: { color: "#ff6d00", note: "Rural demand recovering", trend: "FLAT" },
  Pharma: { color: "#e040fb", note: "USFDA approvals rising", trend: "UP" },
  Telecom: { color: "#40c4ff", note: "5G monetization, ARPU up", trend: "UP" },
  Auto: { color: "#ffca28", note: "Premium strong, EV transition", trend: "FLAT" },
  Finance: { color: "#69f0ae", note: "AUM growth, retail lending", trend: "UP" },
  Infrastructure: { color: "#f48fb1", note: "Govt capex cycle strong", trend: "UP" },
  Materials: { color: "#ff5252", note: "China slowdown pressure", trend: "DOWN" },
  Consumer: { color: "#b388ff", note: "Premiumization trend", trend: "UP" },
  Conglomerate: { color: "#ff8a65", note: "Regulatory overhang", trend: "DOWN" },
};

// 
// data fetching & state management
// 
export default function App() {
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState("top10");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("score");
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [lastFetch, setLastFetch] = useState(null);
  const [filterImpact, setFilterImpact] = useState("all");
  const [filterCat, setFilterCat] = useState("all");
  const [marketData, setMarketData] = useState(null);

  const loadMarket = useCallback(async () => {
    setFetching(true);
    try {
      const res = await fetch("/api/market-data");
      if (res.ok) {
        const data = await res.json();
        setMarketData(data);
        setAlerts([...(data.nse_announcements || []), ...(data.bse_filings || [])]);
        setLastFetch(new Date(data.last_updated).toLocaleTimeString("en-IN"));
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
    setFetching(false);
  }, []);

  useEffect(() => {
    loadMarket();
  }, [loadMarket]);

  const stocks = (marketData?.ranked_stocks || [])
    .map((s) => {
      const a = alerts.find((x) => x.symbol === s.nse_symbol);
      const sentBoost = a
        ? a.impact === "Positive"
          ? 3
          : a.impact === "Negative"
          ? -5
          : 0
        : 0;
      const sent = a
        ? a.impact === "Positive"
          ? 80
          : a.impact === "Negative"
          ? 18
          : 55
        : 55;
      return { ...s, sent, score: Math.min(100, Math.max(0, s.score + sentBoost)) };
    })
    .sort((a, b) => b.score - a.score)
    .map((s, i) => ({ ...s, rank: i + 1 }));

  const displayed = stocks
    .filter(
      (s) =>
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.nse_symbol.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) =>
      sortBy === "score"
        ? b.score - a.score
        : sortBy === "price"
        ? parseFloat(b.price) - parseFloat(a.price)
        : parseFloat(b.change_pct) - parseFloat(a.change_pct)
    );

  const showStocks = view === "top10" ? displayed.slice(0, 10) : displayed;

  const filteredAlerts = alerts.filter((a) => {
    if (filterImpact !== "all" && a.impact !== filterImpact) return false;
    if (filterCat !== "all" && a.category !== filterCat) return false;
    return true;
  });

  const categories = [...new Set(alerts.map((a) => a.category))];

  const globalStyles = `
    @keyframes fadeIn{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
    @keyframes slideIn{from{transform:translateX(100%)}to{transform:translateX(0)}}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.35}}
    @keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
    ::-webkit-scrollbar{width:3px;height:3px}::-webkit-scrollbar-track{background:#050a14}::-webkit-scrollbar-thumb{background:#1a2f4a;border-radius:2px}
    .srow{cursor:pointer;transition:background 0.12s;border-bottom:1px solid #0a1628}
    .srow:hover{background:#0d1f3566}
    .chip{display:inline-block;padding:2px 7px;border-radius:3px;font-size:12px;letter-spacing:1px}
    .tbtn{background:none;border:1px solid #1a2f4a;color:#556;padding:4px 10px;border-radius:4px;cursor:pointer;font-family:'Rajdhani','Segoe UI',sans-serif;font-size:12px;letter-spacing:1.2px;transition:all 0.15s}
    .tbtn:hover{border-color:#00bfff55;color:#c8d8e8}
    .tbtn.on{background:#0d1f35;border-color:#00bfff;color:#00bfff}
    .acard{cursor:pointer;padding:12px 14px;border-radius:6px;margin-bottom:7px;transition:background 0.12s}
    .acard:hover{background:#0d1f35!important}
  `;

  return (
    <div
      style={{
        background: "radial-gradient(circle at 10% 0%, #0f203f 0%, #060b17 45%, #040812 100%)",
        minHeight: "100vh",
        fontFamily: "'Sora', 'Segoe UI', sans-serif",
        lineHeight: 1.35,
        color: "#d8e7f9",
      }}
    >
      {/* global styles */}
      <style dangerouslySetInnerHTML={{ __html: globalStyles }} />

      {/*  HEADER  */}
      <div
        style={{
          background: "#070e1c",
          borderBottom: "1px solid #1a2f4a",
          padding: "13px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div
            style={{
              fontSize: 18,
              fontWeight: "bold",
              color: "#00bfff",
              letterSpacing: 3,
              fontFamily: "'Orbitron', 'Rajdhani', sans-serif",
            }}
          >
             BHARAT MARKET INTELLIGENCE
          </div>
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              marginTop: 3,
            }}
          >
            <span
              style={{ fontSize: 11, color: "#334", letterSpacing: 2 }}
            >
              NSE | BSE | SEBI | LIVE AI ALERTS
            </span>
            <div
              style={{ display: "flex", alignItems: "center", gap: 5 }}
            >
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: loading
                    ? "#ffab00"
                    : fetching
                    ? "#ffab00"
                    : "#00e676",
                  animation:
                    loading || fetching ? "pulse 1s infinite" : "none",
                  boxShadow: `0 0 5px ${
                    loading || fetching ? "#ffab00" : "#00e676"
                  }`,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  color: loading || fetching ? "#ffab00" : "#00e676",
                  letterSpacing: 1,
                }}
              >
                {loading ? "LOADING ALERTS..." : fetching ? "REFRESHING..." : "LIVE"}
              </span>
            </div>
            {lastFetch && (
              <span style={{ fontSize: 11, color: "#334" }}>
                Updated {lastFetch}
              </span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
          {[
            ["NIFTY 50", "21,853", "+0.82%", "#00e676"],
            ["SENSEX", "72,085", "+0.91%", "#00e676"],
          ].map(([n, v, c, col]) => (
            <div key={n} style={{ textAlign: "right" }}>
              <div
                style={{ fontSize: 11, color: "#445", letterSpacing: 1 }}
              >
                {n}
              </div>
              <div
                style={{ fontSize: 16, fontWeight: "bold", color: "#c8d8e8" }}
              >
                {v}
              </div>
              <div style={{ fontSize: 13, color: col }}>{c}</div>
            </div>
          ))}
          <button
            onClick={loadMarket}
            disabled={fetching}
            style={{
              background: "#0d1f35",
              border: "1px solid #00bfff55",
              color: fetching ? "#445" : "#00bfff",
              padding: "7px 14px",
              borderRadius: 4,
              cursor: fetching ? "not-allowed" : "pointer",
              fontFamily: "'Rajdhani', 'Segoe UI', sans-serif",
              fontSize: 12,
              letterSpacing: 2,
            }}
          >
            {fetching ? "..." : "REFRESH"}
          </button>
        </div>
      </div>

      {/*  STATS BAR  */}
      <div
        style={{
          background: "#070e1c",
          borderBottom: "1px solid #1a2f4a",
          padding: "6px 20px",
          display: "flex",
          gap: 24,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {[
          { l: "Stocks", v: stocks.length },
          {
            l: "Avg Score",
            v:
              Math.round(stocks.reduce((a, b) => a + b.score, 0) / stocks.length) +
              "/100",
          },
          {
            l: "Gainers",
            v: stocks.filter((s) => parseFloat(s.change_pct) > 0).length +
              "/" +
              stocks.length,
            c: "#00e676",
          },
          { l: "Strong Buys", v: stocks.filter((s) => s.recommendation === "Strong Buy").length, c: "#00e676" },
          { l: "Avoid", v: stocks.filter((s) => s.recommendation === "Avoid").length, c: "#ff5252" },
          { l: "Live Alerts", v: alerts.length, c: "#00bfff" },
          { l: "Positive", v: alerts.filter((a) => a.impact === "Positive").length, c: "#00e676" },
          { l: "Negative", v: alerts.filter((a) => a.impact === "Negative").length, c: "#ff5252" },
        ].map((m) => (
          <div key={m.l} style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "#334", letterSpacing: 1 }}>
              {m.l}:
            </span>
            <span style={{ fontSize: 13, fontWeight: "bold", color: m.c || "#c8d8e8" }}>
              {m.v}
            </span>
          </div>
        ))}
      </div>

      {/*  MAIN 2-COLUMN LAYOUT  */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 410px", gap: 0, minHeight: "calc(100vh - 110px)" }}>

        {/*  LEFT: STOCKS TABLE  */}
        <div style={{ padding: "14px 16px 20px", borderRight: "1px solid #1a2f4a", overflowX: "auto" }}>

          {/* Controls */}
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 3 }}>
              {["top10", "all"].map((v) => (
                <button
                  key={v}
                  className={`tbtn ${view === v ? "on" : ""}`}
                  onClick={() => setView(v)}
                  style={{ padding: "5px 12px", fontSize: 12 }}
                >
                  {v === "top10" ? "TOP 10" : "ALL 20"}
                </button>
              ))}
            </div>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              style={{
                background: "#0a1628",
                border: "1px solid #1a2f4a",
                color: "#c8d8e8",
                padding: "5px 10px",
                borderRadius: 4,
                fontFamily: "'Rajdhani', 'Segoe UI', sans-serif",
                fontSize: 13,
                outline: "none",
                width: 140,
              }}
            />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                background: "#0a1628",
                border: "1px solid #1a2f4a",
                color: "#c8d8e8",
                padding: "5px 8px",
                borderRadius: 4,
                fontFamily: "'Rajdhani', 'Segoe UI', sans-serif",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              <option value="score">Score DESC</option>
              <option value="price">Price DESC</option>
              <option value="change">Change DESC</option>
            </select>
            <span style={{ fontSize: 12, color: "#334", marginLeft: "auto" }}>
              click row for deep analysis
            </span>
          </div>

          {/* Table */}
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #1a2f4a" }}>
                {[
                  "#",
                  "COMPANY",
                  "SECTOR",
                  "PRICE",
                  "CHG%",
                  "P/E",
                  "ROE",
                  "RSI",
                  "TREND",
                  "30D",
                  "SCORE",
                  "ALERT",
                  "REC",
                ].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: "6px 7px",
                      textAlign: "left",
                      fontSize: 11,
                      color: "#334",
                      letterSpacing: 1.5,
                      fontWeight: "normal",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {showStocks.map((s, i) => {
                const up = parseFloat(s.change_pct || 0) >= 0;
                const sc =
                  s.score >= 75
                    ? "#00e676"
                    : s.score >= 65
                    ? "#69f0ae"
                    : s.score >= 55
                    ? "#ffab00"
                    : s.score >= 40
                    ? "#ff9800"
                    : "#ff5252";
                const alert = alerts.find((a) => a.symbol === s.nse_symbol);
                return (
                  <tr
                    key={s.nse_symbol}
                    className="srow"
                    onClick={() => setSelected(s)}
                    style={{
                      background: i < 3 && view === "top10" ? "#0a1a2e66" : "transparent",
                      animation: `fadeIn ${0.04 * i + 0.08}s ease`,
                    }}
                  >
                    <td style={{ padding: "10px 7px" }}>
                      <span
                        style={{
                          color:
                            i === 0
                              ? "#ffab00"
                              : i === 1
                              ? "#aaa"
                              : i === 2
                              ? "#cd7f32"
                              : "#334",
                          fontSize: i < 3 ? 13 : 10,
                          fontWeight: i < 3 ? "bold" : "normal",
                        }}
                      >
                        {i === 0 ? "#1" : i === 1 ? "#2" : i === 2 ? "#3" : `#${s.rank}`}
                      </span>
                    </td>
                    <td style={{ padding: "10px 7px", whiteSpace: "nowrap" }}>
                      <div
                        style={{ fontWeight: "bold", color: "#c8d8e8", fontSize: 14 }}
                      >
                        {s.name.split(" ").slice(0, 2).join(" ")}
                      </div>
                      <div style={{ fontSize: 11, color: "#445", marginTop: 1 }}>
                        {s.nse_symbol}
                      </div>
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      <span
                        className="chip"
                        style={{
                          background: `${s.sectorColor}15`,
                          color: s.sectorColor,
                          border: `1px solid ${s.sectorColor}33`,
                          whiteSpace: "nowrap",
                          fontSize: 11,
                        }}
                      >
                        {s.sector}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: "10px 7px",
                        fontWeight: "bold",
                        color: "#c8d8e8",
                        fontSize: 14,
                        whiteSpace: "nowrap",
                      }}
                    >
                      INR {parseFloat(s.price || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      <span
                        style={{
                          color: up ? "#00e676" : "#ff5252",
                          fontWeight: "bold",
                          fontSize: 13,
                        }}
                      >
                        {up ? "+" : "-"}{Math.abs(s.change_pct || 0)}%
                      </span>
                    </td>
                    <td
                      style={{
                        padding: "10px 7px",
                        color: parseFloat(s.pe) < 25 ? "#00e676" : parseFloat(s.pe) > 40 ? "#ff5252" : "#c8d8e8",
                        fontSize: 13,
                      }}
                    >
                      {s.pe}
                    </td>
                    <td
                      style={{
                        padding: "10px 7px",
                        color: parseFloat(s.roe) > 20 ? "#00e676" : "#c8d8e8",
                        fontSize: 13,
                      }}
                    >
                      {s.roe}%
                    </td>
                    <td style={{ padding: "10px 7px", textAlign: "center" }}>
                      <div
                        style={{
                          fontSize: 13,
                          color:
                            parseFloat(s.rsi) < 30
                              ? "#ff5252"
                              : parseFloat(s.rsi) < 50
                              ? "#00e676"
                              : parseFloat(s.rsi) < 70
                              ? "#ffab00"
                              : "#ff5252",
                          fontWeight: "bold",
                        }}
                      >
                        {s.rsi}
                      </div>
                      <div style={{ fontSize: 10, color: "#445" }}>
                        {parseFloat(s.rsi) < 30
                          ? "OVER"
                          : parseFloat(s.rsi) < 50
                          ? "RECOV"
                          : parseFloat(s.rsi) < 70
                          ? "OK"
                          : "HIGH"}
                      </div>
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      <span
                        style={{
                          color: s.trend === "Bullish" ? "#00e676" : "#ff5252",
                          fontSize: 13,
                          fontWeight: "bold",
                        }}
                      >
                        {s.trend === "Bullish" ? "UP" : "DOWN"}
                      </span>
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      <Sparkline data={s.sparkline || []} color={up ? "#00e676" : "#ff5252"} />
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <div
                          style={{
                            width: 36,
                            height: 4,
                            background: "#1a2f4a",
                            borderRadius: 3,
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              width: `${s.score}%`,
                              height: "100%",
                              background: sc,
                              borderRadius: 3,
                            }}
                          />
                        </div>
                        <span style={{ fontSize: 14, fontWeight: "bold", color: sc }}>
                          {s.score}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      {alert ? (
                        <span
                          className="chip"
                          style={{
                            background: `${impC(alert.impact)}22`,
                            color: impC(alert.impact),
                            border: `1px solid ${impC(alert.impact)}44`,
                            fontSize: 11,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {alert.category}
                        </span>
                      ) : (
                        <span style={{ color: "#334", fontSize: 13 }}>-</span>
                      )}
                    </td>
                    <td style={{ padding: "10px 7px" }}>
                      <Badge rec={s.recommendation} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Sector Heatmap */}
          <div style={{ marginTop: 22 }}>
            <div style={{ fontSize: 11, color: "#334", letterSpacing: 2, marginBottom: 10 }}>
              SECTOR HEATMAP
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(6,1fr)", gap: 7 }}>
              {Object.entries(SECTOR).map(([sec, meta]) => {
                const ss = stocks.filter((s) => s.sector === sec);
                const avg = ss.length
                  ? Math.round(
                      ss.reduce((a, b) => a + b.score, 0) / ss.length
                    )
                  : 55;
                return (
                  <div
                    key={sec}
                    style={{
                      background: `${meta.color}11`,
                      border: `1px solid ${meta.color}33`,
                      borderRadius: 6,
                      padding: "9px 10px",
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: "bold", color: meta.color }}>
                      {sec}
                    </div>
                    <div style={{ fontSize: 10, color: "#445", marginTop: 2, lineHeight: 1.3 }}>
                      {meta.note}
                    </div>
                    <div style={{ marginTop: 7 }}>
                      <div style={{ background: "#0a1628", borderRadius: 2, height: 3 }}>
                        <div
                          style={{
                            width: `${avg}%`,
                            height: "100%",
                            background: meta.color,
                            borderRadius: 2,
                          }}
                        />
                      </div>
                      <div style={{ fontSize: 11, color: meta.color, marginTop: 2 }}>
                        {avg}/100 {meta.trend}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/*  RIGHT: 10 LIVE NSE/BSE/SEBI ALERTS  */}
        <div style={{ background: "#070e1c", display: "flex", flexDirection: "column" }}>

          {/* Panel Header */}
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #1a2f4a", background: "#050a14" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: "bold", color: "#00bfff", letterSpacing: 2 }}>
                  NSE | BSE | SEBI ALERTS
                </div>
                <div style={{ fontSize: 11, color: "#445", marginTop: 2, letterSpacing: 1 }}>
                  10 LIVE CORPORATE FILINGS | AI POWERED
                </div>
              </div>
              <div style={{ fontSize: 12, color: alerts.length > 0 ? "#00e676" : "#ffab00", fontWeight: "bold" }}>
                {alerts.length > 0 ? `${alerts.length} LIVE` : "LOADING"}
              </div>
            </div>

            {/* Filter chips */}
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
              {["all", "Positive", "Negative", "Neutral"].map((f) => (
                <button
                  key={f}
                  className={`tbtn ${filterImpact === f ? "on" : ""}`}
                  onClick={() => setFilterImpact(f)}
                  style={{
                    fontSize: 11,
                    padding: "3px 8px",
                    color:
                      filterImpact === f
                        ? "#00bfff"
                        : f === "Positive"
                        ? "#00e67688"
                        : f === "Negative"
                        ? "#ff525288"
                        : "#556",
                  }}
                >
                  {f === "all" ? "ALL IMPACT" : f.toUpperCase()}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {["all", ...categories.slice(0, 5)].map((f) => (
                <button
                  key={f}
                  className={`tbtn ${filterCat === f ? "on" : ""}`}
                  onClick={() => setFilterCat(f)}
                  style={{
                    fontSize: 11,
                    padding: "3px 7px",
                    color: filterCat === f ? "#00bfff" : f !== "all" ? catC(f) + "99" : "#556",
                  }}
                >
                  {f === "all" ? "ALL TYPES" : f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Alerts List */}
          <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>
            {loading ? (
              <div style={{ padding: "50px 20px", textAlign: "center" }}>
                <div style={{ fontSize: 26, marginBottom: 12, animation: "spin 1s linear infinite", display: "inline-block" }}>
                  ...
                </div>
                <div style={{ fontSize: 14, color: "#ffab00", marginBottom: 6 }}>
                  Fetching live market data...
                </div>
                <div style={{ fontSize: 12, color: "#445" }}>
                  Python backend is pulling NSE/BSE/SEBI filings
                </div>
                <div style={{ fontSize: 12, color: "#334", marginTop: 8 }}>
                  10 corporate announcements loading
                </div>
              </div>
            ) : filteredAlerts.length === 0 ? (
              <div style={{ padding: "40px 20px", textAlign: "center", color: "#445", fontSize: 13 }}>
                No alerts match current filter
              </div>
            ) : (
              filteredAlerts.map((a, i) => {
                const borderC = impC(a.impact);
                return (
                  <div
                    key={a.id || i}
                    className="acard"
                    onClick={() => {
                      const s = stocks.find((st) => st.nse_symbol === a.symbol);
                      if (s) setSelected(s);
                    }}
                    style={{
                      background: "#0a1628",
                      border: `1px solid ${borderC}22`,
                      borderLeft: `3px solid ${borderC}`,
                      animation: `fadeIn ${0.06 * i}s ease`,
                    }}
                  >
                    {/* Alert number badge */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                      <div style={{ display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap" }}>
                        <span style={{ fontSize: 12, fontWeight: "bold", color: "#e8f4ff" }}>
                          {a.company || a.symbol}
                        </span>
                        <span
                          className="chip"
                          style={{
                            background: `${catC(a.category)}22`,
                            color: catC(a.category),
                            border: `1px solid ${catC(a.category)}44`,
                            fontSize: 11,
                          }}
                        >
                          {a.category}
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: 5, alignItems: "center", flexShrink: 0 }}>
                        <span style={{ fontSize: 11, color: "#445", background: "#1a2f4a", padding: "1px 5px", borderRadius: 2 }}>
                          {a.source}
                        </span>
                        <span style={{ fontSize: 11, color: "#445" }}>{a.date}</span>
                      </div>
                    </div>

                    {/* Type */}
                    <div style={{ fontSize: 12, color: "#667", marginBottom: 6, letterSpacing: 0.5 }}>
                      {a.ann_type || a.type}
                    </div>

                    {/* Detail */}
                    <div style={{ fontSize: 13, color: "#8a9ab0", lineHeight: 1.65 }}>
                      {a.detail}
                    </div>

                    {/* Footer */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, paddingTop: 8, borderTop: `1px solid ${borderC}22` }}>
                      <span style={{ fontSize: 12, fontWeight: "bold", color: borderC }}>
                        {a.impact === "Positive" ? "+ POSITIVE" : a.impact === "Negative" ? "- NEGATIVE" : "NEUTRAL"}
                        {a.impactPts && (
                          <span style={{ color: "#445", fontWeight: "normal", marginLeft: 6 }}>{a.impactPts}</span>
                        )}
                      </span>
                      <span style={{ fontSize: 11, color: "#334" }}>tap -> analysis</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Panel Footer */}
          {!loading && alerts.length > 0 && (
            <div style={{ padding: "8px 14px", borderTop: "1px solid #1a2f4a", background: "#050a14", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "#334" }}>
                {alerts.length} alerts | positive {alerts.filter((a) => a.impact === "Positive").length} | negative {alerts.filter((a) => a.impact === "Negative").length}
              </span>
              <span style={{ fontSize: 11, color: "#334" }}>
                Click any alert to open stock analysis
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Company Detail Slide-In */}
      {selected && <DetailPanel stock={selected} alerts={alerts} onClose={() => setSelected(null)} />}
    </div>
  );
}

function DetailPanel({ stock, alerts, onClose }) {
  const [tab, setTab] = useState("overview");
  if (!stock) return null;
  const sc = stock.sectorColor || "#00e676";
  const stockAlerts = alerts.filter((a) => a.symbol === stock.nse_symbol);

  const radarData = [
    { subject: "Fundamentals", value: stock.score_breakdown?.fundamentals || 50 },
    { subject: "Technicals", value: stock.score_breakdown?.technicals || 50 },
    { subject: "Sentiment", value: stock.sent || 55 },
    { subject: "Sector", value: stock.score_breakdown?.sector || 50 },
    { subject: "Valuation", value: stock.score_breakdown?.valuation || 50 },
  ];

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#000000cc",
        zIndex: 1000,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "flex-end",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "min(780px,95vw)",
          height: "100vh",
          background: "#070e1c",
          borderLeft: "1px solid #1a2f4a",
          overflowY: "auto",
          animation: "slideIn 0.3s ease",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: "18px 24px", borderBottom: "1px solid #1a2f4a", background: "#050a14", position: "sticky", top: 0, zIndex: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: sc, boxShadow: `0 0 8px ${sc}` }} />
                <span style={{ fontSize: 20, fontWeight: "bold", color: "#e8f4ff" }}>{stock.name}</span>
                <Badge rec={stock.recommendation} />
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 5 }}>
                <span style={{ fontSize: 13, color: "#556" }}>{stock.nse_symbol}</span>
                <span style={{ fontSize: 13, color: sc, background: sc + "22", padding: "1px 8px", borderRadius: 3 }}>
                  {stock.sector}
                </span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 24, fontWeight: "bold", color: "#e8f4ff" }}>INR {parseFloat(stock.price || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}</div>
              <div style={{ color: parseFloat(stock.change_pct) >= 0 ? "#00e676" : "#ff5252", fontSize: 14 }}>
                {parseFloat(stock.change_pct) >= 0 ? "+" : "-"} {Math.abs(stock.change_pct || 0)}% today
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 4, marginTop: 14, flexWrap: "wrap" }}>
            {["overview", "technicals", "fundamentals"].map((t) => (
              <button key={t} onClick={() => setTab(t)} style={{ background: tab === t ? "#0d1f35" : "none", border: `1px solid ${tab === t ? "#00bfff" : "#1a2f4a"}`, color: tab === t ? "#00bfff" : "#556", padding: "5px 14px", borderRadius: 4, cursor: "pointer", fontFamily: "'Rajdhani', 'Segoe UI', sans-serif", fontSize: 13, letterSpacing: 1.5, textTransform: "uppercase" }}>
                {t}
              </button>
            ))}
            <button onClick={onClose} style={{ marginLeft: "auto", background: "none", border: "1px solid #1a2f4a", color: "#556", padding: "5px 12px", borderRadius: 4, cursor: "pointer", fontSize: 18 }}>X</button>
          </div>
        </div>
        <div style={{ padding: 22 }}>
          {tab === "overview" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
                <div style={{ background: "#0a1628", border: "1px solid #1a2f4a", borderRadius: 8, padding: 18, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                  <div style={{ fontSize: 12, color: "#445", letterSpacing: 2 }}>COMPOSITE SCORE</div>
                  <ScoreRing score={stock.score} size={110} />
                  <Badge rec={stock.recommendation} />
                </div>
                <div style={{ background: "#0a1628", border: "1px solid #1a2f4a", borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 12, color: "#445", letterSpacing: 2, marginBottom: 4 }}>SCORE RADAR</div>
                  <ResponsiveContainer width="100%" height={185}>
                    <RadarChart data={radarData} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
                      <PolarGrid stroke="#1a2f4a" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: "#556", fontSize: 11, fontFamily: "'Rajdhani', 'Segoe UI', sans-serif" }} />
                      <Radar dataKey="value" stroke={sc} fill={sc} fillOpacity={0.2} strokeWidth={2} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div style={{ background: "#0a1628", border: "1px solid #1a2f4a", borderRadius: 8, padding: 18 }}>
                <div style={{ fontSize: 12, color: "#445", letterSpacing: 2, marginBottom: 12 }}>KEY METRICS</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
                  {[{ label: "P/E Ratio", value: stock.pe }, { label: "ROE", value: stock.roe + "%" }, { label: "Debt/Equity", value: stock.debt_equity }, { label: "Market Cap", value: stock.market_cap_cr + "Cr" }, { label: "52W High", value: "INR " + (stock.week52_high || "N/A") }, { label: "52W Low", value: "INR " + (stock.week52_low || "N/A") }].map((m) => (
                    <div key={m.label} style={{ background: "#070e1c", border: "1px solid #1a2f4a", borderRadius: 6, padding: "10px 12px" }}>
                      <div style={{ fontSize: 11, color: "#445", letterSpacing: 1.5, marginBottom: 3 }}>{m.label}</div>
                      <div style={{ fontSize: 16, fontWeight: "bold", color: "#c8d8e8" }}>{m.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          {tab === "technicals" && (
            <div style={{ background: "#0a1628", border: "1px solid #1a2f4a", borderRadius: 8, padding: 18 }}>
              <div style={{ fontSize: 12, color: "#445", letterSpacing: 2, marginBottom: 12 }}>TECHNICAL ANALYSIS</div>
              <div>RSI: {stock.rsi}</div>
              <div>Trend: {stock.trend}</div>
              <div>MACD: {stock.macd_signal}</div>
            </div>
          )}
          {tab === "fundamentals" && (
            <div style={{ background: "#0a1628", border: "1px solid #1a2f4a", borderRadius: 8, padding: 18 }}>
              <div style={{ fontSize: 12, color: "#445", letterSpacing: 2, marginBottom: 12 }}>FINANCIAL METRICS</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {[{ label: "Profit Margin", value: stock.profit_margin + "%" }, { label: "Revenue Growth", value: stock.revenue_growth + "%" }, { label: "Earnings Growth", value: stock.earnings_growth + "%" }, { label: "Dividend Yield", value: stock.div_yield + "%" }].map((m) => (
                  <div key={m.label} style={{ background: "#070e1c", border: "1px solid #1a2f4a", borderRadius: 6, padding: 14 }}>
                    <div style={{ fontSize: 11, color: "#445", letterSpacing: 1 }}>{m.label}</div>
                    <div style={{ fontSize: 20, fontWeight: "bold", color: "#00e676", margin: "7px 0" }}>{m.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

