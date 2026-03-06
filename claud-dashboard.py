"""
Live Option Chain Dashboard — Fyers API v3
Pure Python Streamlit App | No HTML/CSS/JS
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from fyers_apiv3 import fyersModel

# ─────────────────────── PAGE CONFIG ───────────────────────
st.set_page_config(
    page_title="Live Option Chain | Fyers",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────── SESSION STATE ─────────────────────
for k, v in {
    "pcr_history":       [],
    "last_pcr_time":     None,
    "fyers":             None,
    "auto_refresh":      False,
    "current_index":     "NIFTY 50",
    "current_expiry":    None,
    "expiry_options":    [],
    "expiry_timestamps": {},
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────── SIDEBAR ───────────────────────────
st.sidebar.title("⚙️ Fyers Login")
st.sidebar.markdown("---")
client_id    = st.sidebar.text_input("Client ID (App ID)", placeholder="XXXXXXXX-100")
access_token = st.sidebar.text_input("Access Token", type="password")

if st.sidebar.button("🔗 Connect to Fyers", use_container_width=True):
    if client_id and access_token:
        try:
            obj = fyersModel.FyersModel(
                client_id=client_id, is_async=False,
                token=access_token, log_path=""
            )
            r = obj.get_profile()
            if r.get("code") == 200:
                st.session_state.fyers = obj
                st.sidebar.success(f"✅ Connected: {r['data']['name']}")
            else:
                st.sidebar.error(f"❌ {r.get('message', 'Auth failed')}")
        except Exception as e:
            st.sidebar.error(f"❌ {e}")
    else:
        st.sidebar.warning("⚠️ Enter both Client ID & Access Token")

st.sidebar.info("🟢 Connected" if st.session_state.fyers else "🔴 Not connected")
st.sidebar.markdown("---")

# ── Index Selection ──
st.sidebar.subheader("📈 Select Index")
index_options = {
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX"
}
selected_index_name = st.sidebar.selectbox("Choose Index", list(index_options.keys()))
selected_symbol = index_options[selected_index_name]

# Agar Index change ho
if st.session_state.current_index != selected_index_name:
    st.session_state.current_index = selected_index_name
    st.session_state.current_expiry = None
    st.session_state.expiry_options = []
    st.session_state.expiry_timestamps = {}
    st.session_state.pcr_history = []
    st.session_state.last_pcr_time = None
    st.rerun()

# ── Expiry Selection ──
selected_timestamp = ""

if st.session_state.fyers:
    # 1. Pehle Expiry list fetch karein agar empty hai
    if not st.session_state.expiry_options:
        try:
            base_resp = st.session_state.fyers.optionchain(
                data={"symbol": selected_symbol, "strikecount": 1, "timestamp": ""}
            )
            if base_resp.get("code") == 200 and "data" in base_resp:
                exp_data = base_resp["data"].get("expiryData", [])
                st.session_state.expiry_options = [ex["date"] for ex in exp_data]
                st.session_state.expiry_timestamps = {ex["date"]: ex["timestamp"] for ex in exp_data}
        except Exception as e:
            st.sidebar.error("Could not load expiries.")

    # 2. Expiry Dropdown Show karein
    if st.session_state.expiry_options:
        selected_expiry = st.sidebar.selectbox("📅 Select Expiry", st.session_state.expiry_options)
        selected_timestamp = st.session_state.expiry_timestamps.get(selected_expiry, "")

        # Agar Expiry change ho toh history reset karein
        if st.session_state.current_expiry != selected_expiry:
            st.session_state.current_expiry = selected_expiry
            st.session_state.pcr_history = []
            st.session_state.last_pcr_time = None
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔄 Refresh Settings")
refresh_sec = st.sidebar.slider("Interval (seconds)", 1, 10, 5)
auto_on = st.sidebar.toggle("Enable Auto-Refresh", value=st.session_state.auto_refresh)
st.session_state.auto_refresh = auto_on
st.sidebar.markdown("---")
st.sidebar.caption("📌 Change OI PCR snapshot is saved **every 5 minutes** automatically.")

# ── AUTHOR INFO ──
st.sidebar.markdown("---")
st.sidebar.subheader("👨‍💻 Developer")
st.sidebar.markdown(
    """
    **Narendra** [📸 Instagram (@chandeln16)](https://instagram.com/chandeln16)  
    [🐦 X (@chandeln16)](https://x.com/chandeln16)
    """
)

# ─────────────────────── HELPER FUNCTIONS ──────────────────

def fetch_chain(fyers_obj, symbol, timestamp):
    """Fetch option chain (ATM ± 7 strikes) based on selected timestamp."""
    return fyers_obj.optionchain(
        data={"symbol": symbol, "strikecount": 7, "timestamp": str(timestamp)}
    )

def parse_chain(resp):
    """Parse API response into call/put DataFrames with error handling."""
    if resp.get("code") != 200:
        raise ValueError(resp.get("message", "API error"))

    # Safely get data dict to prevent KeyError
    data_dict = resp.get("data", {})
    raw = data_dict.get("optionsChain", [])
    
    if not raw:
        raise ValueError("No option chain data available for this expiry/index.")

    atm = data_dict.get("atm", 0)
    
    calls, puts = [], []
    for item in raw:
        s  = item.get("strikePrice", 0)
        ce = item.get("CE", {})
        pe = item.get("PE", {})
        
        calls.append({
            "Strike": s,
            "OI":           ce.get("openInterest", 0),
            "Chng OI":      ce.get("oiChange", 0),
            "Volume":       ce.get("volume", 0),
            "Chng Volume":  ce.get("volumeChange", 0),
            "LTP":          ce.get("ltp", 0),
            "IV":           ce.get("impliedVolatility", 0),
        })
        
        puts.append({
            "Strike": s,
            "OI":           pe.get("openInterest", 0),
            "Chng OI":      pe.get("oiChange", 0),
            "Volume":       pe.get("volume", 0),
            "Chng Volume":  pe.get("volumeChange", 0),
            "LTP":          pe.get("ltp", 0),
            "IV":           pe.get("impliedVolatility", 0),
        })

    df_c = pd.DataFrame(calls).sort_values("Strike").reset_index(drop=True)
    df_p = pd.DataFrame(puts).sort_values("Strike").reset_index(drop=True)
    return df_c, df_p, atm

def compute_summary(df_c, df_p):
    def sdiv(a, b):
        return round(a / b, 4) if b else 0.0

    tc_oi  = df_c["OI"].sum()
    tp_oi  = df_p["OI"].sum()
    tc_co  = df_c["Chng OI"].sum()
    tp_co  = df_p["Chng OI"].sum()
    tc_vol = df_c["Volume"].sum()
    tp_vol = df_p["Volume"].sum()
    tc_cv  = df_c["Chng Volume"].sum()
    tp_cv  = df_p["Chng Volume"].sum()

    return {
        "Total Call OI":      tc_oi,
        "Total Put OI":       tp_oi,
        "Call Chng OI":       tc_co,
        "Put Chng OI":        tp_co,
        "OI PCR":             sdiv(tp_oi, tc_oi),
        "Change OI PCR":      sdiv(tp_co, tc_co),
        "Total Call Volume":  tc_vol,
        "Total Put Volume":   tp_vol,
        "Call Chng Volume":   tc_cv,
        "Put Chng Volume":    tp_cv,
        "Volume PCR":         sdiv(tp_vol, tc_vol),
        "Change Volume PCR":  sdiv(tp_cv,  tc_cv),
    }

def maybe_record_pcr(pcr_val):
    now  = datetime.now()
    last = st.session_state.last_pcr_time
    if last is None or (now - last).total_seconds() >= 300:
        st.session_state.pcr_history.append({
            "Time":          now.strftime("%Y-%m-%d %H:%M:%S"),
            "Change OI PCR": round(pcr_val, 4),
        })
        st.session_state.last_pcr_time = now

def sentiment(v):
    if v > 1.2:  return "🟢 Bullish"
    if v < 0.8:  return "🔴 Bearish"
    return "🟡 Neutral"

def crore_fmt(n):
    an = abs(n)
    if an >= 1e7:  return f"{n/1e7:.2f} Cr"
    if an >= 1e5:  return f"{n/1e5:.2f} L"
    return f"{int(n):,}"

def hl_atm(row, atm):
    s = "background-color:#fff9c4;color:black;font-weight:bold;" if row["Strike"] == atm else ""
    return [s] * len(row)

def col_chng(v):
    if isinstance(v, (int, float)):
        if v > 0: return "color:#00a651;font-weight:600"
        if v < 0: return "color:#cc0000;font-weight:600"
    return ""

# ─────────────────────── MAIN DASHBOARD ────────────────────

st.title(f"📊 {selected_index_name} Live Option Chain")
st.caption("Fyers API v3  •  ATM ± 7 Strikes")

if not st.session_state.fyers:
    st.warning("👈 Connect your Fyers account from the **sidebar** to begin.")
    st.stop()

# Agar expiry select nahi hui hai
if not st.session_state.current_expiry:
    st.info("⏳ Loading expiries from Fyers...")
    st.stop()

r1, r2 = st.columns([1, 5])
r1.button("🔄 Refresh Now", use_container_width=True)
status_slot = r2.empty()

# ── Fetch data ──
try:
    raw_resp = fetch_chain(st.session_state.fyers, selected_symbol, selected_timestamp)
    df_c, df_p, atm = parse_chain(raw_resp)
    s = compute_summary(df_c, df_p)
    maybe_record_pcr(s["Change OI PCR"])
    
    display_expiry = st.session_state.current_expiry
    status_slot.success(
        f"🕐 Updated: **{datetime.now().strftime('%H:%M:%S')}** |  "
        f"Expiry: **{display_expiry}** |  ATM: **{atm:,.0f}**"
    )
except Exception as ex:
    st.error(f"❌ Could not fetch data: {ex}")
    st.stop()

# ═══════════════════════════════════════════
# SECTION 1 — MARKET SUMMARY METRICS
# ═══════════════════════════════════════════
st.markdown("---")
st.subheader("📋 Market Summary")

a1, a2, a3, a4 = st.columns(4)
a1.metric("📞 Total Call OI",   crore_fmt(s["Total Call OI"]))
a2.metric("🤙 Total Put OI",    crore_fmt(s["Total Put OI"]))
a3.metric("📞 Call Chng OI",    crore_fmt(s["Call Chng OI"]))
a4.metric("🤙 Put Chng OI",     crore_fmt(s["Put Chng OI"]))

b1, b2, b3, b4 = st.columns(4)
b1.metric("⚖️ OI PCR",             s["OI PCR"], delta=sentiment(s["OI PCR"]), delta_color="off")
b2.metric("⚖️ Change OI PCR",      s["Change OI PCR"], delta=sentiment(s["Change OI PCR"]), delta_color="off")
b3.metric("📊 Volume PCR",          s["Volume PCR"], delta=sentiment(s["Volume PCR"]), delta_color="off")
b4.metric("📊 Change Volume PCR",   s["Change Volume PCR"], delta=sentiment(s["Change Volume PCR"]), delta_color="off")

c1, c2, c3, c4 = st.columns(4)
c1.metric("📞 Total Call Volume",   crore_fmt(s["Total Call Volume"]))
c2.metric("🤙 Total Put Volume",    crore_fmt(s["Total Put Volume"]))
c3.metric("📞 Call Chng Volume",    crore_fmt(s["Call Chng Volume"]))
c4.metric("🤙 Put Chng Volume",     crore_fmt(s["Put Chng Volume"]))

# ═══════════════════════════════════════════
# SECTION 2 — COMBINED OPTION CHAIN TABLE
# ═══════════════════════════════════════════
st.markdown("---")
st.subheader(f"🗂️ Option Chain  —  ATM: {atm:,.0f}  (Yellow row = ATM)")

df_chain = pd.merge(
    df_c.rename(columns={
        "OI": "Call OI", "Chng OI": "Call Chng OI", "Volume": "Call Vol", 
        "Chng Volume": "Call Chng Vol", "LTP": "Call LTP", "IV": "Call IV",
    }),
    df_p.rename(columns={
        "OI": "Put OI", "Chng OI": "Put Chng OI", "Volume": "Put Vol", 
        "Chng Volume": "Put Chng Vol", "LTP": "Put LTP", "IV": "Put IV",
    }),
    on="Strike",
)

chain_cols = [
    "Call IV", "Call LTP", "Call Chng Vol", "Call Vol", "Call Chng OI", "Call OI",
    "Strike",
    "Put OI", "Put Chng OI", "Put Vol", "Put Chng Vol", "Put LTP", "Put IV",
]

chain_fmt = {
    "Strike":       "{:,.0f}",
    "Call OI":      "{:,}", "Put OI":       "{:,}",
    "Call Chng OI": "{:,}", "Put Chng OI":  "{:,}",
    "Call Vol":     "{:,}", "Put Vol":      "{:,}",
    "Call Chng Vol":"{:,}", "Put Chng Vol": "{:,}",
    "Call LTP":     "{:.2f}", "Put LTP":    "{:.2f}",
    "Call IV":      "{:.1f}%","Put IV":     "{:.1f}%",
}

st.dataframe(
    df_chain[chain_cols].style
        .apply(hl_atm, atm=atm, axis=1)
        .map(col_chng, subset=["Call Chng OI","Put Chng OI","Call Chng Vol","Put Chng Vol"])
        .format(chain_fmt),
    use_container_width=True,
    height=430,
)

# ═══════════════════════════════════════════
# SECTION 3 — 5-MIN CHANGE OI PCR HISTORY
# ═══════════════════════════════════════════
st.markdown("---")
st.subheader("🕐 Change OI PCR — 5-Minute Snapshot Log")

if st.session_state.pcr_history:
    df_h = pd.DataFrame(st.session_state.pcr_history)
    df_h.index = range(1, len(df_h) + 1)
    df_h.index.name = "#"

    tbl_col, chart_col = st.columns([1, 2])

    with tbl_col:
        st.dataframe(df_h.style.format({"Change OI PCR": "{:.4f}"}), use_container_width=True, height=340)

    with chart_col:
        if len(df_h) > 1:
            st.line_chart(df_h.set_index("Time")[["Change OI PCR"]], use_container_width=True)
        else:
            st.info("📈 Chart will appear once 2+ snapshots are recorded.")

    if st.button("🗑️ Clear PCR History"):
        st.session_state.pcr_history = []
        st.session_state.last_pcr_time = None
        st.rerun()
else:
    st.info("⏳ First snapshot will be recorded within 5 minutes of the app running.")

# ═══════════════════════════════════════════
# SECTION 4 — INDIVIDUAL TABS
# ═══════════════════════════════════════════
st.markdown("---")
tab_calls, tab_puts = st.tabs(["📞 Call Options Detail", "🤙 Put Options Detail"])

detail_cols = ["Strike", "LTP", "IV", "OI", "Chng OI", "Volume", "Chng Volume"]
detail_fmt  = {
    "Strike": "{:,.0f}", "OI": "{:,}", "Chng OI": "{:,}", 
    "Volume": "{:,}", "Chng Volume": "{:,}", "LTP": "{:.2f}", "IV": "{:.1f}%",
}

with tab_calls:
    st.dataframe(
        df_c[detail_cols].style.apply(hl_atm, atm=atm, axis=1)
        .map(col_chng, subset=["Chng OI", "Chng Volume"]).format(detail_fmt),
        use_container_width=True,
    )

with tab_puts:
    st.dataframe(
        df_p[detail_cols].style.apply(hl_atm, atm=atm, axis=1)
        .map(col_chng, subset=["Chng OI", "Chng Volume"]).format(detail_fmt),
        use_container_width=True,
    )

# ═══════════════════════════════════════════
# AUTO-REFRESH LOOP
# ═══════════════════════════════════════════
if st.session_state.auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()