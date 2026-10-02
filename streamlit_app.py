import time
from datetime import datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import yfinance as yf

# Configuration
REFRESH_INTERVAL_MINUTES = 10

st.set_page_config(page_title="Multi-Asset Options Matrix", layout="wide", page_icon="⚡")

# Custom CSS to strictly compress padding, margins, and text sizes for a single-screen view
st.markdown("""
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
""", unsafe_allow_html=True)

# Display refresh engine status banner
current_time = datetime.now().strftime("%H:%M:%S")
st.markdown(
    f"<div class='timer-banner'>🔄 <b>Automation:</b> Active | "
    f"<b>Interval:</b> Every {REFRESH_INTERVAL_MINUTES} Mins | "
    f"<b>Last Sync:</b> {current_time}</div>", 
    unsafe_allow_html=True
)

# Secure browser session mock to bypass public web throttling blocks
custom_session = requests.Session()
custom_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

@st.cache_data(ttl=900)
def fetch_ticker_data_row(ticker):
    stock = yf.Ticker(ticker, session=custom_session)
    try:
        fast_info = stock.fast_info
        spot = fast_info.get('lastPrice', 0.0)
        if spot == 0.0:
            spot = stock.history(period="1d")['Close'].iloc[-1]
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
        
        calls['Type'], calls['Expiration'] = 'Call', nearest_date
        puts['Type'], puts['Expiration'] = 'Put', nearest_date
        
        df = pd.concat([calls, puts], ignore_index=True)
        df['impliedVolatility'] = df['impliedVolatility'] * 100
        df['Ticker'] = ticker
        return df, spot, nearest_date
    except Exception:
        return pd.DataFrame(), spot, ""

# ==========================================
# 🎛️ SIDEBAR WATCHLIST INTERFACE
# ==========================================
st.sidebar.markdown("### ⚙️ Terminal Controls")
user_watchlist_input = st.sidebar.text_input(
    "Type 5 Tickers (comma separated):", 
    value="AAPL, MSFT, NVDA, TSLA,META"
)

stocks_to_plot = [t.strip().upper() for t in user_watchlist_input.split(",") if t.strip()][:5]

# Shared compact plot dimensions to lock all 12 charts inside one screen height window
chart_layout_config = dict(
    hovermode='x unified',
    plot_bgcolor='rgba(0,0,0,0)',
    height=120,  # Scaled down to fit 4 rows perfectly on one screen
    margin=dict(l=5, r=5, t=5, b=5),
    showlegend=False,  # Turned off to save vertical screen real estate
    xaxis=dict(tickfont=dict(size=10), title=dict(text="", font=dict(size=10))), # Dropped axis label to save space
    yaxis=dict(tickfont=dict(size=10), title=dict(font=dict(size=10)))
)

# ==========================================
# 📈 ROW-BY-STOCK VISUALIZATION GRID ENGINE
# ==========================================
with st.spinner("Synchronizing market snapshots..."):
    for index, t in enumerate(stocks_to_plot):
        if not t:
            continue
            
        df_opt, price_spot, expiry_closest = fetch_ticker_data_row(t)
        
        if not df_opt.empty:
            # Focus on At-The-Money (ATM) +/- 15% to keep view compact
            lower_bound = price_spot * 0.85
            upper_bound = price_spot * 1.15
            filtered_df = df_opt[(df_opt['strike'] >= lower_bound) & (df_opt['strike'] <= upper_bound)]
            chart_df = filtered_df.sort_values(by='strike')
            
            # --- MIN/MAX ANALYTICS ---
            min_iv = chart_df['impliedVolatility'].min()
            max_iv = chart_df['impliedVolatility'].max()
            
            max_oi_row = chart_df.loc[chart_df['openInterest'].idxmax()] if not chart_df['openInterest'].empty else None
            max_oi = max_oi_row['openInterest'] if max_oi_row is not None else 0
            max_oi_strike = max_oi_row['strike'] if max_oi_row is not None else 0
            
            max_vol_row = chart_df.loc[chart_df['volume'].idxmax()] if not chart_df['volume'].empty else None
            max_vol = max_vol_row['volume'] if max_vol_row is not None else 0
            max_vol_strike = max_vol_row['strike'] if max_vol_row is not None else 0

            # --- HEADER STRIP ---
            header_html = (
                f"<h6>"
                f"📊 {t} — Spot: \${price_spot:,.2f} | Exp: {expiry_closest}"
                f"<span class='header-stat'>📉 IV: {min_iv:.0f}%-{max_iv:.0f}%</span>"
                f"<span class='header-stat'>🧱 Max OI: {max_oi:,.0f} @ \${max_oi_strike:.0f}</span>"
                f"<span class='header-stat'>🔥 Max Vol: {max_vol:,.0f} @ \${max_vol_strike:.0f}</span>"
                f"</h6>"
            )
            st.markdown(header_html, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            
            with c1:
                fig_iv = px.line(
                    chart_df, x='strike', y='impliedVolatility', color='Type',
                    color_discrete_map={'Call': '#10b981', 'Put': '#ef4444'},
                    template='plotly_dark'
                )
                fig_iv.update_layout(**chart_layout_config)
                st.plotly_chart(fig_iv, use_container_width=True, key=f"fig_iv_{t}_{index}", config={'displayModeBar': False})
                
            with c2:
                fig_oi = px.bar(
                    chart_df, x='strike', y='openInterest', color='Type', barmode='group',
                    color_discrete_map={'Call': '#10b981', 'Put': '#ef4444'},
                    template='plotly_dark'
                )
                fig_oi.update_layout(**chart_layout_config)
                st.plotly_chart(fig_oi, use_container_width=True, key=f"fig_oi_{t}_{index}", config={'displayModeBar': False})
                
            with c3:
                fig_vol = px.bar(
                    chart_df, x='strike', y='volume', color='Type', barmode='group',
                    color_discrete_map={'Call': '#10b981', 'Put': '#ef4444'},
                    template='plotly_dark'
                )
                fig_vol.update_layout(**chart_layout_config)
                st.plotly_chart(fig_vol, use_container_width=True, key=f"fig_vol_{t}_{index}", config={'displayModeBar': False})
                
        else:
            st.warning(f"Could not load data for symbol: {t}")

# ==========================================
# 🔄 AUTOMATED UPDATE INTERVAL ENGINE
# ==========================================
time.sleep(REFRESH_INTERVAL_MINUTES * 60)
st.rerun()
