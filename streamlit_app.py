from datetime import datetime
import time
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# Configuration & Page Setup
REFRESH_INTERVAL_MINUTES = 10

st.set_page_config(
    page_title="Unified Options Terminal & Strategy Visualizer",
    layout="wide",
    page_icon="⚡",
)

# Custom CSS
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"], .main .block-container { 
        font-size: 11px !important; 
        padding-top: 10px !important; 
        padding-bottom: 5px !important;
        padding-left: 20px !important;
        padding-right: 20px !important;
    }
    h1 { font-size: 16px !important; font-weight: bold !important; margin: 0px !important; padding: 0px !important;}
    h4 { font-size: 12px !important; font-weight: bold !important; margin-top: 4px !important; margin-bottom: 2px !important; border-bottom: 1px solid #475569; padding-bottom: 2px; color: #f8fafc;}
    div[data-testid="stSidebarUserContent"] { padding-top: 0.5rem !important; }
    .timer-banner { background-color: #0f172a; padding: 4px 10px; border-radius: 4px; border: 1px solid #475569; margin-top: 4px; margin-bottom: 4px; font-size: 11px; font-weight: 500; }
    .header-stat { font-size: 10px !important; font-weight: normal !important; color: #cbd5e1; background-color: #1e293b; padding: 1px 6px; border-radius: 3px; margin-left: 4px; border: 1px solid #334155; display: inline-block; vertical-align: middle; }
    .stTextInput input { font-size: 11px !important; padding: 4px !important; }
    div[data-testid="element-container"] { margin-bottom: 0px !important; }
    div.stGap { gap: 0px !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 🔒 SIMPLE AUTHENTICATION SYSTEM
# ==========================================
if "authenticated" not in st.session_state:
  st.session_state["authenticated"] = False


def check_login():
  """Callback to verify credentials and update state."""
  if (
      st.session_state.get("username", "") == "admin"
      and st.session_state.get("password", "") == "options123"
  ):
    st.session_state["authenticated"] = True
    st.success("Access Granted!")
  else:
    st.error("❌ Invalid Username or Password")


# Render Login Portal if not logged in
if not st.session_state["authenticated"]:
  st.title("🔐 Terminal Access Control")
  with st.form("login_form"):
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.form_submit_button("Access Dashboard", on_click=check_login)
  st.stop()

# ==========================================
# 🎛️ MAIN NAVIGATION SELECTION
# ==========================================
st.sidebar.markdown("### 🧭 Application Selector")
app_mode = st.sidebar.selectbox(
    "Choose Feature:",
    ["📊 Multi-Asset Options Matrix", "📈 SPX Strategy Payoff Visualizer"],
)

st.sidebar.markdown("---")

# Setup robust shared custom session with browser-like headers
custom_session = requests.Session()
custom_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com",
})

# ==========================================
# FEATURE 1: MULTI-ASSET OPTIONS MATRIX
# ==========================================
if app_mode == "📊 Multi-Asset Options Matrix":
  current_time = datetime.now().strftime("%H:%M:%S")
  st.markdown(
      f"<div class='timer-banner'>🔄 <b>Automation:</b> Active | "
      f"<b>Interval:</b> Every {REFRESH_INTERVAL_MINUTES} Mins | "
      f"<b>Last Sync:</b> {current_time}</div>",
      unsafe_allow_html=True,
  )


  @st.cache_data(ttl=900)
  def fetch_ticker_data_row(ticker):
    stock = yf.Ticker(ticker, session=custom_session)
    spot = 0.0
    try:
      fast_info = stock.fast_info
      spot = fast_info.get("lastPrice", 0.0)
      if spot == 0.0:
        hist = stock.history(period="1d")
        if not hist.empty:
          spot = hist["Close"].iloc[-1]
    except Exception:
      spot = 0.0

    try:
      options_dates = stock.options
      if not options_dates:
        return pd.DataFrame(), spot, ""

      options_list = list(options_dates)
      nearest_date = options_list[0]

      chain = stock.option_chain(nearest_date)
      calls, puts = chain.calls.copy(), chain.puts.copy()

      calls["Type"], calls["Expiration"] = "Call", nearest_date
      puts["Type"], puts["Expiration"] = "Put", nearest_date

      df = pd.concat([calls, puts], ignore_index=True)
      df["impliedVolatility"] = df["impliedVolatility"] * 100
      df["Ticker"] = ticker
      return df, spot, nearest_date
    except Exception:
      return pd.DataFrame(), spot, ""

  st.sidebar.markdown("### ⚙️ Matrix Controls")
  user_watchlist_input = st.sidebar.text_input(
      "Type 5 Tickers (comma separated):", value="AAPL, MSFT, NVDA, TSLA, META"
  )

  if st.sidebar.button("Logout Dashboard"):
    st.session_state["authenticated"] = False
    st.rerun()

  stocks_to_plot = [
      t.strip().upper() for t in user_watchlist_input.split(",") if t.strip()
  ][:5]

  chart_layout_config = dict(
      hovermode="x unified",
      plot_bgcolor="rgba(0,0,0,0)",
      height=120,
      margin=dict(l=5, r=5, t=5, b=5),
      showlegend=False,
      xaxis=dict(tickfont=dict(size=10), title=dict(text="", font=dict(size=10))),
      yaxis=dict(tickfont=dict(size=10), title=dict(font=dict(size=10))),
  )

  with st.spinner("Synchronizing market snapshots..."):
    for index, t in enumerate(stocks_to_plot):
      if not t:
        continue

      df_opt, price_spot, expiry_closest = fetch_ticker_data_row(t)
      time.sleep(1.0)  # Rate limit buffer

      if not df_opt.empty:
        lower_bound = price_spot * 0.85
        upper_bound = price_spot * 1.15
        filtered_df = df_opt[
            (df_opt["strike"] >= lower_bound)
            & (df_opt["strike"] <= upper_bound)
        ]
        chart_df = filtered_df.sort_values(by="strike")

        min_iv = (
            chart_df["impliedVolatility"].min()
            if not chart_df["impliedVolatility"].empty
            else 0
        )
        max_iv = (
            chart_df["impliedVolatility"].max()
            if not chart_df["impliedVolatility"].empty
            else 0
        )

        max_oi_row = (
            chart_df.loc[chart_df["openInterest"].idxmax()]
            if not chart_df["openInterest"].empty
            and chart_df["openInterest"].max() > 0
            else None
        )
        max_oi = max_oi_row["openInterest"] if max_oi_row is not None else 0
        max_oi_strike = max_oi_row["strike"] if max_oi_row is not None else 0

        max_vol_row = (
            chart_df.loc[chart_df["volume"].idxmax()]
            if not chart_df["volume"].empty and chart_df["volume"].max() > 0
            else None
        )
        max_vol = max_vol_row["volume"] if max_vol_row is not None else 0
        max_vol_strike = max_vol_row["strike"] if max_vol_row is not None else 0

        header_html = (
            f"<h6>"
            f"📊 {t} — Spot: ${price_spot:,.2f} | Exp: {expiry_closest}"
            f"<span class='header-stat'>📉 IV: {min_iv:.0f}%-{max_iv:.0f}%</span>"
            f"<span class='header-stat'>🧱 Max OI: {max_oi:,.0f} @"
            f" ${max_oi_strike:.0f}</span>"
            f"<span class='header-stat'>🔥 Max Vol: {max_vol:,.0f} @"
            f" ${max_vol_strike:.0f}</span>"
            f"</h6>"
        )
        st.markdown(header_html, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)

        with c1:
          fig_iv = px.line(
              chart_df,
              x="strike",
              y="impliedVolatility",
              color="Type",
              color_discrete_map={"Call": "#10b981", "Put": "#ef4444"},
              template="plotly_dark",
          )
          fig_iv.update_layout(**chart_layout_config)
          st.plotly_chart(
              fig_iv,
              width="stretch",
              key=f"fig_iv_{t}_{index}",
              config={"displayModeBar": False},
          )

        with c2:
          fig_oi = px.bar(
              chart_df,
              x="strike",
              y="openInterest",
              color="Type",
              barmode="group",
              color_discrete_map={"Call": "#10b981", "Put": "#ef4444"},
              template="plotly_dark",
          )
          fig_oi.update_layout(**chart_layout_config)
          st.plotly_chart(
              fig_oi,
              width="stretch",
              key=f"fig_oi_{t}_{index}",
              config={"displayModeBar": False},
          )

        with c3:
          fig_vol = px.bar(
              chart_df,
              x="strike",
              y="volume",
              color="Type",
              barmode="group",
              color_discrete_map={"Call": "#10b981", "Put": "#ef4444"},
              template="plotly_dark",
          )
          fig_vol.update_layout(**chart_layout_config)
          st.plotly_chart(
              fig_vol,
              width="stretch",
              key=f"fig_vol_{t}_{index}",
              config={"displayModeBar": False},
          )
      else:
        st.warning(
            f"Could not load data for symbol: {t} (Rate limited / Market closed)"
        )

  time.sleep(REFRESH_INTERVAL_MINUTES * 60)
  st.rerun()

# ==========================================
# FEATURE 2: SPX OPTIONS STRATEGY PAYOFF VISUALIZER
# ==========================================
elif app_mode == "📈 SPX Strategy Payoff Visualizer":
  st.title("📊 SPX Options Strategy Payoff Visualizer")
  st.write(
      "Fetches current S&P 500 SPOT data and live option chains from Yahoo"
      " Finance."
  )


  @st.cache_data(ttl=300)
  def get_spx_data():
    for attempt in range(3):
      try:
        ticker = yf.Ticker("^GSPC", session=custom_session)
        todays_data = ticker.history(period="1d")
        spot = (
            round(todays_data["Close"].iloc[-1], 2)
            if not todays_data.empty
            else 5000.0
        )
        expirations = ticker.options
        if expirations:
          return spot, expirations
        time.sleep(1)
      except Exception:
        time.sleep(2)
    return 5000.0, []


  spot_price, spx_expirations = get_spx_data()


  @st.cache_data(ttl=120)
  def fetch_option_market_price(expiry_date, option_type, target_strike):
    for attempt in range(3):
      try:
        stock = yf.Ticker("^GSPC", session=custom_session)
        chain = stock.option_chain(expiry_date)
        df = chain.calls if option_type.lower() == "call" else chain.puts
        if df.empty:
          return None, None
        df["diff"] = abs(df["strike"] - target_strike)
        closest_row = df.loc[df["diff"].idxmin()]
        bid = closest_row.get("bid", 0)
        ask = closest_row.get("ask", 0)
        last = closest_row.get("lastPrice", 0)
        if (
            pd.notnull(bid)
            and pd.notnull(ask)
            and float(bid) > 0
            and float(ask) > 0
        ):
          return float((float(bid) + float(ask)) / 2), float(
              closest_row["strike"]
          )
        if pd.notnull(last) and float(last) > 0:
          return float(last), float(closest_row["strike"])
        return None, None
      except Exception:
        time.sleep(1)
    return None, None


  st.sidebar.header("🔧 SPX Strategy Settings")
  st.sidebar.metric(label="Current SPX Spot Price", value=f"${spot_price:,.2f}")

  if spx_expirations:
    selected_expiry = st.sidebar.selectbox(
        "📅 Select Expiration Date", spx_expirations
    )
  else:
    selected_expiry = None
    st.sidebar.warning(
        "No expiration dates available (Rate-limited or market closed)."
    )

  if st.sidebar.button("🔄 Refresh Spot & Data"):
    st.cache_data.clear()
    st.rerun()

  if st.sidebar.button("Logout Dashboard", key="logout_spx"):
    st.session_state["authenticated"] = False
    st.rerun()

  range_pct = st.sidebar.slider(
      "X-Axis Graph Range (%)",
      1,
      20,
      5,
      help="Percentage movement away from current spot price.",
  )
  x_min = spot_price * (1 - range_pct / 100)
  x_max = spot_price * (1 + range_pct / 100)
  S = np.linspace(x_min, x_max, 1000)


  def call_payoff(S, strike, premium, position="long"):
    payoff = np.maximum(S - strike, 0) - premium
    return payoff if position == "long" else -payoff


  def put_payoff(S, strike, premium, position="long"):
    payoff = np.maximum(strike - S, 0) - premium
    return payoff if position == "long" else -payoff


  def plot_strategy(S, total_payoff, title, operational_legs):
    fig = go.Figure()
    fig.add_shape(
        type="line",
        x0=S[0],
        y0=0,
        x1=S[-1],
        y1=0,
        line=dict(color="gray", width=1.5, dash="dash"),
    )
    fig.add_trace(
        go.Scatter(
            x=S,
            y=total_payoff,
            mode="lines",
            name="Total Strategy Net PnL",
            line=dict(color="#1f77b4", width=3.5),
        )
    )

    profit_payoff = np.where(total_payoff >= 0, total_payoff, 0)
    loss_payoff = np.where(total_payoff < 0, total_payoff, 0)

    fig.add_trace(
        go.Scatter(
            x=S,
            y=profit_payoff,
            fill="tozeroy",
            fillcolor="rgba(44, 160, 44, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=S,
            y=loss_payoff,
            fill="tozeroy",
            fillcolor="rgba(214, 39, 40, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_vline(
        x=spot_price,
        line_width=1.5,
        line_dash="dot",
        line_color="orange",
        annotation_text="Current Spot",
    )
    fig.update_layout(
        title=title,
        xaxis_title="SPX Index Price at Expiration",
        yaxis_title="Net Profit / Loss ($)",
        template="plotly_dark",
        hovermode="x unified",
    )

    st.plotly_chart(fig, width="stretch")

    max_profit = np.max(total_payoff)
    max_loss = np.min(total_payoff)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Max Potential Profit",
        (
            f"${max_profit:,.2f}"
            if max_profit != total_payoff[-1] and max_profit != total_payoff[0]
            else "Unlimited"
        ),
    )
    c2.metric(
        "Max Potential Risk",
        (
            f"${abs(max_loss):,.2f}"
            if max_loss != total_payoff[-1] and max_loss != total_payoff[0]
            else "Unlimited"
        ),
    )

    with st.expander("🔍 View Operational Leg Breakdown"):
      st.write(operational_legs)

  tab1, tab2, tab3, tab4 = st.tabs(
      ["⚡ Long Strangle", "🛡️ Short Strangle", "🦅 Iron Condor", "🛠️ Custom Setup"]
  )

  with tab1:
    st.header("Long Strangle Payoff Graph")
    st.caption(
        "Expect volatility breakout. Buying an OTM Put and OTM Call for"
        f" expiration: {selected_expiry}"
    )

    col1, col2 = st.columns(2)
    with col1:
      put_strike = st.number_input(
          "Long Put Strike", value=int(spot_price * 0.98), step=5, key="ls_p_s"
      )
      default_p_prem = 25.0
      if selected_expiry and st.button(
          "🔗 Fetch Live Put Price", key="fetch_ls_p"
      ):
        live_p, matched_s = fetch_option_market_price(
            selected_expiry, "Put", put_strike
        )
        if live_p is not None:
          default_p_prem = live_p
          st.success(f"Fetched Put Price: ${live_p:.2f} (Strike: {matched_s})")
        else:
          st.warning("Could not fetch live price (Rate limited).")
      put_prem = st.number_input(
          "Put Premium Paid ($)",
          value=float(default_p_prem),
          step=0.5,
          key="ls_p_p",
      )

    with col2:
      call_strike = st.number_input(
          "Long Call Strike", value=int(spot_price * 1.02), step=5, key="ls_c_s"
      )
      default_c_prem = 25.0
      if selected_expiry and st.button(
          "🔗 Fetch Live Call Price", key="fetch_ls_c"
      ):
        live_c, matched_s = fetch_option_market_price(
            selected_expiry, "Call", call_strike
        )
        if live_c is not None:
          default_c_prem = live_c
          st.success(f"Fetched Call Price: ${live_c:.2f} (Strike: {matched_s})")
        else:
          st.warning("Could not fetch live price (Rate limited).")
      call_prem = st.number_input(
          "Call Premium Paid ($)",
          value=float(default_c_prem),
          step=0.5,
          key="ls_c_p",
      )

    p1 = put_payoff(S, put_strike, put_prem, "long")
    p2 = call_payoff(S, call_strike, call_prem, "long")
    legs_desc = f"1x Long Put Strike {put_strike} @ ${put_prem} | 1x Long Call Strike {call_strike} @ ${call_prem} (Exp: {selected_expiry})"
    plot_strategy(
        S,
        (p1 + p2) * 100,
        "Long Strangle Net Payoff Profile (1 Contract = x100)",
        legs_desc,
    )

  with tab2:
    st.header("Short Strangle Payoff Graph")
    st.caption(
        "Range-bound premium collection. Selling an OTM Put and OTM Call for"
        f" expiration: {selected_expiry}"
    )

    col1, col2 = st.columns(2)
    with col1:
      s_put_strike = st.number_input(
          "Short Put Strike", value=int(spot_price * 0.97), step=5, key="ss_p_s"
      )
      default_sp_prem = 20.0
      if selected_expiry and st.button(
          "🔗 Fetch Live Short Put Price", key="fetch_ss_p"
      ):
        live_p, matched_s = fetch_option_market_price(
            selected_expiry, "Put", s_put_strike
        )
        if live_p is not None:
          default_sp_prem = live_p
          st.success(
              f"Fetched Short Put Price: ${live_p:.2f} (Strike: {matched_s})"
          )
        else:
          st.warning("Could not fetch live price (Rate limited).")
      s_put_prem = st.number_input(
          "Put Premium Collected ($)",
          value=float(default_sp_prem),
          step=0.5,
          key="ss_p_p",
      )

    with col2:
      s_call_strike = st.number_input(
          "Short Call Strike", value=int(spot_price * 1.03), step=5, key="ss_c_s"
      )
      default_sc_prem = 20.0
      if selected_expiry and st.button(
          "🔗 Fetch Live Short Call Price", key="fetch_ss_c"
      ):
        live_c, matched_s = fetch_option_market_price(
            selected_expiry, "Call", s_call_strike
        )
        if live_c is not None:
          default_sc_prem = live_c
          st.success(
              f"Fetched Short Call Price: ${live_c:.2f} (Strike: {matched_s})"
          )
        else:
          st.warning("Could not fetch live price (Rate limited).")
      s_call_prem = st.number_input(
          "Call Premium Collected ($)",
          value=float(default_sc_prem),
          step=0.5,
          key="ss_c_p",
      )

    p1 = put_payoff(S, s_put_strike, s_put_prem, "short")
    p2 = call_payoff(S, s_call_strike, s_call_prem, "short")
    legs_desc = f"1x Short Put Strike {s_put_strike} @ ${s_put_prem} | 1x Short Call Strike {s_call_strike} @ ${s_call_prem} (Exp: {selected_expiry})"
    plot_strategy(
        S,
        (p1 + p2) * 100,
        "Short Strangle Net Payoff Profile (1 Contract = x100)",
        legs_desc,
    )

  with tab3:
    st.header("Iron Condor Payoff Graph")
    st.caption(
        "Defined risk premium collection strategy for expiration:"
        f" {selected_expiry}"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
      ic_lp_s = st.number_input(
          "Long Put (Wing)", value=int(spot_price * 0.95), step=5
      )
      ic_lp_p = st.number_input("LP Premium Paid", value=10.0, step=0.5)
    with col2:
      ic_sp_s = st.number_input(
          "Short Put (Inner)", value=int(spot_price * 0.97), step=5
      )
      ic_sp_p = st.number_input("SP Premium Credit", value=22.0, step=0.5)
    with col3:
      ic_sc_s = st.number_input(
          "Short Call (Inner)", value=int(spot_price * 1.03), step=5
      )
      ic_sc_p = st.number_input("SC Premium Credit", value=22.0, step=0.5)
    with col4:
      ic_lc_s = st.number_input(
          "Long Call (Wing)", value=int(spot_price * 1.05), step=5
      )
      ic_lc_p = st.number_input("LC Premium Paid", value=10.0, step=0.5)

    if selected_expiry and st.button(
        "🔗 Fetch All Iron Condor Prices from Market"
    ):
      lp, _ = fetch_option_market_price(selected_expiry, "Put", ic_lp_s)
      sp, _ = fetch_option_market_price(selected_expiry, "Put", ic_sp_s)
      sc, _ = fetch_option_market_price(selected_expiry, "Call", ic_sc_s)
      lc, _ = fetch_option_market_price(selected_expiry, "Call", ic_lc_s)
      if (
          lp is not None
          and sp is not None
          and sc is not None
          and lc is not None
      ):
        st.success(
            f"Fetched! LP: ${lp:.2f} | SP: ${sp:.2f} | SC: ${sc:.2f} | LC:"
            f" ${lc:.2f}"
        )
      else:
        st.warning(
            "Some leg prices could not be fetched due to rate-limiting."
        )

    p1 = put_payoff(S, ic_lp_s, ic_lp_p, "long")
    p2 = put_payoff(S, ic_sp_s, ic_sp_p, "short")
    p3 = call_payoff(S, ic_sc_s, ic_sc_p, "short")
    p4 = call_payoff(S, ic_lc_s, ic_lc_p, "long")

    legs_desc = f"LP {ic_lp_s} (-${ic_lp_p}) | SP {ic_sp_s} (+${ic_sp_p}) | SC {ic_sc_s} (+${ic_sc_p}) | LC {ic_lc_s} (-${ic_lc_p}) (Exp: {selected_expiry})"
    plot_strategy(
        S,
        (p1 + p2 + p3 + p4) * 100,
        "Iron Condor Net Payoff Profile (1 Contract = x100)",
        legs_desc,
    )

  with tab4:
    st.header("🛠️ Advanced Custom Option Builder")
    st.caption(
        "Mix and match up to 8 individual leg components with live market data"
        f" for expiration: {selected_expiry}"
    )

    num_legs = st.number_input(
        "Number of available legs to configure:",
        min_value=1,
        max_value=8,
        value=4,
        step=1,
    )
    total_custom_payoff = np.zeros_like(S)
    custom_desc = []

    st.write("---")

    for i in range(1, int(num_legs) + 1):
      with st.container(border=True):
        c_check, c_type, c_dir, c_strike, c_prem = st.columns(
            [1, 2, 2, 3, 3]
        )

        with c_check:
          st.write("")
          active = st.checkbox(
              f"Leg {i}", value=(i <= 2), key=f"active_{i}"
          )

        if active:
          with c_type:
            opt_type = st.selectbox("Type", ["Call", "Put"], key=f"type_{i}")
          with c_dir:
            direction = st.selectbox(
                "Direction", ["Long", "Short"], key=f"dir_{i}"
            )
          with c_strike:
            default_strike = (
                int(spot_price)
                if i % 2 == 0
                else (
                    int(spot_price * 0.98)
                    if opt_type == "Put"
                    else int(spot_price * 1.02)
                )
            )
            strike = st.number_input(
                "Strike Price", value=default_strike, step=5, key=f"strike_{i}"
            )
          with c_prem:
            default_prem = 15.0
            if selected_expiry and st.button(
                f"🔗 Fetch", key=f"fetch_custom_{i}"
            ):
              live_p, matched_s = fetch_option_market_price(
                  selected_expiry, opt_type, strike
              )
              if live_p is not None:
                default_prem = live_p
                st.success(f"Fetched: ${live_p:.2f} (@ Strike {matched_s})")
              else:
                st.warning("Fetch failed (Rate limited)")
            premium = st.number_input(
                "Premium ($)",
                value=float(default_prem),
                step=0.5,
                key=f"prem_{i}",
            )

          if opt_type == "Call":
            leg_pnl = call_payoff(S, strike, premium, direction.lower())
          else:
            leg_pnl = put_payoff(S, strike, premium, direction.lower())

          total_custom_payoff += leg_pnl
          custom_desc.append(
              f"**Leg {i}:** {direction} {opt_type} @ Strike {strike}"
              f" (Premium: ${premium})"
          )
        else:
          with c_type:
            st.text_input("Type", "—", disabled=True, key=f"dis_t_{i}")
          with c_dir:
            st.text_input("Direction", "—", disabled=True, key=f"dis_d_{i}")
          with c_strike:
            st.text_input("Strike Price", "—", disabled=True, key=f"dis_s_{i}")
          with c_prem:
            st.text_input("Premium ($)", "—", disabled=True, key=f"dis_p_{i}")

    st.write("---")

    if len(custom_desc) > 0:
      plot_strategy(
          S,
          total_custom_payoff * 100,
          f"Custom Multi-Leg Strategy Profile (Exp: {selected_expiry})",
          "\n".join(custom_desc),
      )
    else:
      st.info(
          "💡 Please check the box next to at least one leg above to start"
          " building your visual profile."
      )
