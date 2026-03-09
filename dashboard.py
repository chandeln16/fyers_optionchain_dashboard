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
# GitHub original state
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

# ─────────────────────── SIDEBAR (Original UI) ───────────────────────────
st.sidebar.title("⚙️ Fyers Login")
st.sidebar.markdown("---")
client_id    = st.sidebar.text_input("Client ID (App ID)", value="OIROK73TDQ-100")
access_token = st.sidebar.text_input("Access Token", type="password")

if st.sidebar.button("🔗 Connect to Fyers", use_container_width=True):
    if client_id and access_token:
        try:
            obj = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")
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

# Index & Expiry Selection (Original GitHub Code)
index_options = {"NIFTY 50": "NSE:NIFTY50-INDEX", "BANK NIFTY": "NSE:NIFTYBANK-INDEX", "SENSEX": "BSE:SENSEX-INDEX"}
selected_index_name = st.sidebar.selectbox("Choose Index", list(index_options.keys()))
selected_symbol = index_options[selected_index_name]

if st.session_state.current_index != selected_index_name:
    st.session_state.current_index = selected_index_name
    st.session_state.current_expiry = None
    st.session_state.expiry_options = []
    st.session_state.expiry_timestamps = {}
    st.session_state.pcr_history = []
    st.session_state.last_pcr_time = None
    st.rerun()

if st.session_state.fyers and not st.session_state.expiry_options:
    try:
        base_resp = st.session_state.fyers.optionchain(data={"symbol": selected_symbol, "strikecount": 1, "timestamp": ""})
        if base_resp.get("code") == 200:
            exp_data = base_resp["data"].get("expiryData", [])
            st.session_state.expiry_options = [ex["date"] for ex in exp_data]
            st.session_state.expiry_timestamps = {ex["date"]: ex["timestamp"] for ex in exp_data}
    except: pass

selected_timestamp = ""
if st.session_state.expiry_options:
    selected_expiry = st.sidebar.selectbox("📅 Select Expiry", st.session_state.expiry_options)
    selected_timestamp = st.session_state.expiry_timestamps.get(selected_expiry, "")
    if st.session_state.current_expiry != selected_expiry:
        st.session_state.current_expiry = selected_expiry
        st.session_state.pcr_history = []
        st.session_state.last_pcr_time = None
        st.rerun()

st.sidebar.markdown("---")
refresh_sec = st.sidebar.slider("Interval (seconds)", 1, 10, 5)
auto_on = st.sidebar.toggle("Enable Auto-Refresh", value=st.session_state.auto_refresh)
st.session_state.auto_refresh = auto_on

# 👨‍💻 Author Info (Original)
st.sidebar.markdown("---")
st.sidebar.subheader("👨‍💻 Developer")
st.sidebar.markdown("**Narendra** [📸 Instagram (@chandeln16)](https://instagram.com/chandeln16)")

# ─────────────────────── FIXED HELPERS (Keeping Original Logic) ──────────────────

def fetch_chain(fyers_obj, symbol, timestamp):
    return fyers_obj.optionchain(data={"symbol": symbol, "strikecount": 7, "timestamp": str(timestamp)})

def parse_chain(resp):
    """FIXED: Uses your working keys but keeps GitHub's structure."""
    if resp.get('s') != 'ok':
        raise ValueError(resp.get("message", "API error"))
    
    data_dict = resp.get("data", {})
    raw = data_dict.get("optionsChain", [])
    if not raw: raise ValueError("No data available.")
    
    atm = data_dict.get("atm", 0)
    df = pd.DataFrame(raw)
    
    # Working keys from your source
    df_c = df[df['option_type'] == 'CE'].copy().rename(columns={"oi":"OI", "oich":"Chng OI", "volume":"Volume", "ltp":"LTP", "strike_price":"Strike"})
    df_p = df[df['option_type'] == 'PE'].copy().rename(columns={"oi":"OI", "oich":"Chng OI", "volume":"Volume", "ltp":"LTP", "strike_price":"Strike"})
    
    # Adding missing IV and Chng Vol for UI consistency
    for d in [df_c, df_p]:
        if 'IV' not in d: d['IV'] = 0.0
        if 'Chng Volume' not in d: d['Chng Volume'] = 0
            
    return df_c.sort_values("Strike"), df_p.sort_values("Strike"), atm

def compute_summary(df_c, df_p):
    # GitHub's original summary logic
    def sdiv(a, b): return round(a / b, 4) if b else 0.0
    tc_oi, tp_oi = df_c["OI"].sum(), df_p["OI"].sum()
    tc_co, tp_co = df_c["Chng OI"].sum(), df_p["Chng OI"].sum()
    tc_vol, tp_vol = df_c["Volume"].sum(), df_p["Volume"].sum()
    
    return {
        "Total Call OI": tc_oi, "Total Put OI": tp_oi, "Call Chng OI": tc_co, "Put Chng OI": tp_co,
        "OI PCR": sdiv(tp_oi, tc_oi), "Change OI PCR": sdiv(tp_co, tc_co),
        "Total Call Volume": tc_vol, "Total Put Volume": tp_vol,
        "Volume PCR": sdiv(tp_vol, tc_vol), "Change Volume PCR": 0.0, "Call Chng Volume": 0, "Put Chng Volume": 0
    }

def maybe_record_pcr(pcr_val):
    now = datetime.now()
    if st.session_state.last_pcr_time is None or (now - st.session_state.last_pcr_time).total_seconds() >= 300:
        st.session_state.pcr_history.append({"Time": now.strftime("%H:%M:%S"), "Change OI PCR": pcr_val})
        st.session_state.last_pcr_time = now

def sentiment(v):
    if v > 1.2: return "🟢 Bullish"
    if v < 0.8: return "🔴 Bearish"
    return "🟡 Neutral"

def hl_atm(row, atm):
    s = "background-color:#fff9c4;color:black;font-weight:bold;" if row["Strike"] == atm else ""
    return [s] * len(row)

def col_chng(v):
    if v > 0: return "color:#00a651;font-weight:600"
    if v < 0: return "color:#cc0000;font-weight:600"
    return ""

# ─────────────────────── MAIN DASHBOARD (Full Original UI) ────────────────────
st.title(f"📊 {selected_index_name} Live Option Chain")
st.caption("Fyers API v3  •  ATM ± 7 Strikes")

if not st.session_state.fyers or not st.session_state.current_expiry:
    st.warning("👈 Connect Fyers and select Expiry from the sidebar.")
    st.stop()

try:
    raw_resp = fetch_chain(st.session_state.fyers, selected_symbol, selected_timestamp)
    df_c, df_p, atm = parse_chain(raw_resp)
    s = compute_summary(df_c, df_p)
    maybe_record_pcr(s["Change OI PCR"])

    # UI Row 1 - Metrics
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("📞 Total Call OI", f"{s['Total Call OI']:,}")
    a2.metric("🤙 Total Put OI", f"{s['Total Put OI']:,}")
    a3.metric("📞 Call Chng OI", f"{s['Call Chng OI']:,}")
    a4.metric("🤙 Put Chng OI", f"{s['Put Chng OI']:,}")

    # UI Row 2 - PCR Metrics
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("⚖️ OI PCR", s["OI PCR"], delta=sentiment(s["OI PCR"]), delta_color="off")
    b2.metric("⚖️ Change OI PCR", s["Change OI PCR"], delta=sentiment(s["Change OI PCR"]), delta_color="off")
    b3.metric("📊 Volume PCR", s["Volume PCR"], delta=sentiment(s["Volume PCR"]), delta_color="off")

    # SECTION 2 — Combined Table (Original Style)
    st.markdown("---")
    st.subheader(f"🗂️ Option Chain (ATM: {atm:,.0f})")
    df_chain = pd.merge(
        df_c.rename(columns={"OI":"Call OI", "Chng OI":"Call Chng OI", "Volume":"Call Vol", "LTP":"Call LTP", "IV":"Call IV"}),
        df_p.rename(columns={"OI":"Put OI", "Chng OI":"Put Chng OI", "Volume":"Put Vol", "LTP":"Put LTP", "IV":"Put IV"}),
        on="Strike"
    )
    cols = ["Call IV", "Call LTP", "Call Chng OI", "Call OI", "Strike", "Put OI", "Put Chng OI", "Put LTP", "Put IV"]
    st.dataframe(df_chain[cols].style.apply(hl_atm, atm=atm, axis=1).map(col_chng, subset=["Call Chng OI","Put Chng OI"]), use_container_width=True, height=400)

    # SECTION 3 — History & Chart (Original Style)
    if st.session_state.pcr_history:
        st.markdown("---")
        st.subheader("🕐 Change OI PCR — 5-Minute Snapshot")
        df_h = pd.DataFrame(st.session_state.pcr_history)
        st.line_chart(df_h.set_index("Time"), use_container_width=True)

except Exception as ex:
    st.error(f"❌ Error: {ex}")

if st.session_state.auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()
