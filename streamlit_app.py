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

# Custom CSS injection for tight, space-optimized text layout structures
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] { font-size: 11px !important; }
    h1 { font-size: 15px !important; margin-top: 1px !important; margin-bottom: 1px !important; padding-top: 1px !important;}
    h4 { font-size: 12px !important; font-weight: bold !important; margin-top: 4px !important; margin-bottom: 1px !important; border-bottom: 1px solid #475569; padding-bottom: 1px; color: #f1f5f9;}
    h5 { font-size: 11px !important; font-weight: bold !important; margin-bottom: 0px !important; color: #a855f7;}
    div[data-testid="stSidebarUserContent"] { padding-top: 0.5rem !important; }
    div[data-testid="element-container"] { margin-bottom: 1px !important; }
    .stTextInput input { font-size: 11px !important; padding: 4px !important; }
    .timer-banner { background-color: #0f172a; padding: 6px 12px; border-radius: 4px; border: 1px solid #334155; margin-bottom: 8px; font-size: 11px; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Multi-Asset Options Row Matrix")

# Display the Refresh Interval metadata prominently on the primary dashboard area
current_time = datetime.now().strftime("%H:%M:%S")
st.markdown(
    f"<div class='timer-banner'>🔄 <b>Automation Engine Status:</b> Active | "
    f"<b>Refresh Cycle Cadence:</b> Every {REFRESH_INTERVAL_MINUTES} Minutes | "
    f"<b>Last Terminal Pull:</b> {current_time}</div>", 
    unsafe_allow_html=True
)

# Secure browser session mock to bypass public web throttling blocks
custom_session = requests.Session()
custom_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

@st.cache_data(ttl=900)
def fetch_ticker_data_row(ticker):
    """Pulls and isolates the closest option expiration contract layer for a ticker."""
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
    "Type 4 Tickers (comma separated):", 
    value="AAPL, MSFT, NVDA, TSLA"
)

# Parse inputs into a clean array matching the 4-column requirements
stocks_to_plot = [t.strip().upper() for t in user_watchlist_input.split(",") if t.strip()][:4]

# Shared structural dimensions for parallel metrics row blocks
chart_layout_config = dict(
    hovermode='x unified',
    plot_bgcolor='rgba(0,0,0,0)',
    height=140,  # Compact vertical frame height to keep rows visible
    margin=dict(l=5, r=5, t=5, b=5),
    showlegend=False,
    xaxis=dict(tickfont=dict(size=7), title=dict(text="Strike", font=dict(size=8))),
    yaxis=dict(tickfont=dict(size=7), title=dict(font=dict(size=8)))
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
            # Context-bound crop filters out extreme illiquid wings (+/- 15% out of the money)
            lower_bound = price_spot * 0.85
            upper_bound = price_spot * 1.15
            filtered_df = df_opt[(df_opt['strike'] >= lower_bound) & (df_opt['strike'] <= upper_bound)]
            chart_df = filtered_df.sort_values(by='strike')
            
            # Create a localized heading block for the stock row
            st.markdown(f"<h4>📊 {t} Matrix — Spot: \${price_spot:,.2f} | Near Expiry: {expiry_closest}</h4>", unsafe_allow_html=True)
            
            # Generate 3 layout panels side-by-side horizontally for this specific stock
            c1, c2, c3 = st.columns(3)
            
            # Panel 1: Implied Volatility Smile
            with c1:
                fig_iv = px.line(
                    chart_df, x='strike', y='impliedVolatility', color='Type', markers=True,
                    labels={'impliedVolatility': 'IV %'},
                    color_discrete_map={'Call': '#10b981', 'Put': '#ef4444'},
                    template='plotly_dark'
                )
                fig_iv.update_layout(**chart_layout_config)
                st.plotly_chart(fig_iv, use_container_width=True, key=f"fig_iv_{t}_{index}", config={'displayModeBar': False})
                
            # Panel 2: Open Interest Structure Bars
            with c2:
                fig_oi = px.bar(
                    chart_df, x='strike', y='openInterest', color='Type', barmode='group',
                    labels={'openInterest': 'OI'},
                    color_discrete_map={'Call': '#10b981', 'Put': '#ef4444'},
                    template='plotly_dark'
                )
                fig_oi.update_layout(**chart_layout_config)
                st.plotly_chart(fig_oi, use_container_width=True, key=f"fig_oi_{t}_{index}", config={'displayModeBar': False})
                
            # Panel 3: Daily Volume Traded Bars
            with c3:
                fig_vol = px.bar(
                    chart_df, x='strike', y='volume', color='Type', barmode='group',
                    labels={'volume': 'Vol'},
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
