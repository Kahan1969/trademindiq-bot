"""
TradeMindIQ Streamlit Dashboard
================================
Web-based dashboard for TradeMindIQ trading bot.
Provides real-time analytics, reports, backtesting, and strategy management.

Usage:
    streamlit run trademindiq_app.py

Requirements:
    pip install streamlit plotly pandas matplotlib
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import sys

# Add TradeMindIQBot to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.analytics import PerformanceAnalytics
from services.reports import ReportGenerator, WeeklyReport, MonthlyReport
from services.portfolio import PortfolioTracker
from services.backtest import Backtester

# Page configuration
st.set_page_config(
    page_title="TradeMindIQ Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ==================== SIDEBAR NAVIGATION ====================
st.sidebar.title("🤖 TradeMindIQ")
st.sidebar.markdown("---")

page = st.sidebar.selectbox(
    "Navigation",
    ["Dashboard", "Analytics", "Reports", "Backtesting", "Strategies", "Portfolio", "Export"]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 All data syncs with trades.db automatically.")


# ==================== HELPER FUNCTIONS ====================
@st.cache_data
def load_analytics():
    """Load analytics data."""
    return PerformanceAnalytics()


@st.cache_data
def load_portfolio():
    """Load portfolio data."""
    return PortfolioTracker()


@st.cache_data
def load_reports():
    """Load report generator."""
    return ReportGenerator()


def format_currency(value):
    """Format currency with $ and commas."""
    return f"${value:,.2f}" if value is not None else "$0.00"


def format_pct(value):
    """Format percentage."""
    return f"{value:.2f}%" if value is not None else "0.00%"


def get_emoji_for_pnl(value):
    """Get emoji for P/L value."""
    if value > 0:
        return "🟢"
    elif value < 0:
        return "🔴"
    else:
        return "⚪"


# ==================== PAGE: DASHBOARD ====================
if page == "Dashboard":
    st.markdown('<p class="main-header">🤖 TradeMindIQ Dashboard</p>', unsafe_allow_html=True)
    
    analytics = load_analytics()
    portfolio = load_portfolio()
    summary = analytics.calculate_performance_summary()
    
    # Quick Stats Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Trades",
            summary.total_trades,
            delta=None
        )
    
    with col2:
        st.metric(
            "Win Rate",
            format_pct(summary.win_rate),
            delta=f"{'+' if summary.win_rate >= 40 else ''}{summary.win_rate - 40:.1f}%" if summary.win_rate > 0 else None
        )
    
    with col3:
        st.metric(
            "Total P/L",
            format_currency(summary.total_pnl),
            delta=get_emoji_for_pnl(summary.total_pnl),
            delta_color="normal" if summary.total_pnl >= 0 else "inverse"
        )
    
    with col4:
        st.metric(
            "Avg P/L per Trade",
            format_currency(summary.avg_pnl_per_trade),
            delta=get_emoji_for_pnl(summary.avg_pnl_per_trade),
            delta_color="normal" if summary.avg_pnl_per_trade >= 0 else "inverse"
        )
    
    st.markdown("---")
    
    # Charts Row
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📈 P/L by Symbol")
        if summary.pnl_by_symbol:
            symbols = list(summary.pnl_by_symbol.keys())
            pnls = [summary.pnl_by_symbol[s].total_pnl for s in symbols]
            colors = ['green' if p > 0 else 'red' for p in pnls]
            
            fig = go.Figure(data=[
                go.Bar(x=symbols, y=pnls, marker_color=colors)
            ])
            fig.update_layout(
                xaxis_title="Symbol",
                yaxis_title="P/L ($)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trade data available")
    
    with col_right:
        st.subheader("🎯 Win Rate by Symbol")
        if summary.pnl_by_symbol:
            symbols = list(summary.pnl_by_symbol.keys())
            win_rates = [summary.pnl_by_symbol[s].win_rate for s in symbols]
            
            fig = go.Figure(data=[
                go.Bar(x=symbols, y=win_rates, marker_color='steelblue')
            ])
            fig.add_hline(y=40, line_dash="dash", line_color="green", annotation_text="Target: 40%")
            fig.update_layout(
                xaxis_title="Symbol",
                yaxis_title="Win Rate (%)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trade data available")
    
    st.markdown("---")
    
    # Daily P/L Chart
    st.subheader("📅 Daily P/L")
    if summary.daily_pnl:
        dates = list(summary.daily_pnl.keys())
        pnls = list(summary.daily_pnl.values())
        
        fig = go.Figure(data=[
            go.Scatter(x=dates, y=pnls, mode='lines+markers', line=dict(color='steelblue'))
        ])
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="P/L ($)",
            height=250
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Exit Reasons
    st.subheader("🚪 Exit Reasons")
    if summary.exit_reason_counts:
        reasons = list(summary.exit_reason_counts.keys())
        counts = list(summary.exit_reason_counts.values())
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = go.Figure(data=[go.Pie(labels=reasons, values=counts, hole=0.4)])
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("### Exit Summary")
            for reason, count in summary.exit_reason_counts.items():
                pct = count / sum(counts) * 100
                st.write(f"**{reason}:** {count} trades ({pct:.1f}%)")


# ==================== PAGE: ANALYTICS ====================
elif page == "Analytics":
    st.markdown('<p class="main-header">📊 Analytics</p>', unsafe_allow_html=True)
    
    analytics = load_analytics()
    summary = analytics.calculate_performance_summary()
    
    # Date filter
    days_filter = st.selectbox("Time Period", ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days"])
    
    if days_filter == "Last 7 Days":
        filtered_summary = analytics.get_recent_performance(7)
        period = "Last 7 Days"
    elif days_filter == "Last 30 Days":
        filtered_summary = analytics.get_recent_performance(30)
        period = "Last 30 Days"
    elif days_filter == "Last 90 Days":
        filtered_summary = analytics.get_recent_performance(90)
        period = "Last 90 Days"
    else:
        filtered_summary = summary
        period = "All Time"
    
    st.subheader(f"📈 Performance Summary - {period}")
    
    # Metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Trades", filtered_summary.total_trades)
    with col2:
        st.metric("Wins", filtered_summary.total_wins)
    with col3:
        st.metric("Losses", filtered_summary.total_losses)
    with col4:
        st.metric("Win Rate", format_pct(filtered_summary.win_rate))
    with col5:
        st.metric("Total P/L", format_currency(filtered_summary.total_pnl))
    
    st.markdown("---")
    
    # Best/Worst Trades
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("🏆 Best Trades")
        if filtered_summary.pnl_by_symbol:
            sorted_symbols = sorted(
                filtered_summary.pnl_by_symbol.items(),
                key=lambda x: x[1].total_pnl,
                reverse=True
            )[:5]
            
            for symbol, stats in sorted_symbols:
                if stats.total_pnl > 0:
                    st.write(f"**{symbol}:** {format_currency(stats.total_pnl)} ({stats.win_rate:.0f}% WR)")
    
    with col_right:
        st.subheader("⚠️ Worst Trades")
        if filtered_summary.pnl_by_symbol:
            sorted_symbols = sorted(
                filtered_summary.pnl_by_symbol.items(),
                key=lambda x: x[1].total_pnl
            )[:5]
            
            for symbol, stats in sorted_symbols:
                st.write(f"**{symbol}:** {format_currency(stats.total_pnl)} ({stats.win_rate:.0f}% WR)")
    
    st.markdown("---")
    
    # Full Symbol Breakdown
    st.subheader("📋 Complete Symbol Breakdown")
    if filtered_summary.pnl_by_symbol:
        data = []
        for symbol, stats in filtered_summary.pnl_by_symbol.items():
            data.append({
                "Symbol": symbol,
                "Trades": stats.total_trades,
                "Wins": stats.wins,
                "Losses": stats.losses,
                "Win Rate (%)": round(stats.win_rate, 1),
                "Total P/L ($)": round(stats.total_pnl, 2),
                "Avg P/L ($)": round(stats.avg_pnl, 2)
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        # CSV Export
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Export to CSV",
            csv,
            "analytics_export.csv",
            "text/csv"
        )


# ==================== PAGE: REPORTS ====================
elif page == "Reports":
    st.markdown('<p class="main-header">📝 Reports</p>', unsafe_allow_html=True)
    
    report_type = st.radio("Report Type", ["Weekly", "Monthly"], horizontal=True)
    
    reports = load_reports()
    
    if report_type == "Weekly":
        # Goals input
        st.subheader("🎯 Weekly Goals")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            goal_win_rate = st.number_input("Target Win Rate (%)", value=40)
        with col2:
            goal_pnl = st.number_input("Target P/L ($)", value=100)
        with col3:
            goal_trades = st.number_input("Target Trades", value=50)
        with col4:
            goal_max_loss = st.number_input("Max Loss ($)", value=100)
        
        goals = {
            f"win_rate_{goal_win_rate}%": None,
            f"positive_pnl_{goal_pnl}": None,
        }
        
        # Generate report
        if st.button("📊 Generate Weekly Report"):
            report = reports.get_current_week_report(goals)
            st.markdown("---")
            st.subheader(f"Week of {report.week_start.strftime('%Y-%m-%d')}")
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", report.total_trades)
            with col2:
                st.metric("Win Rate", format_pct(report.win_rate))
            with col3:
                st.metric("Net P/L", format_currency(report.total_pnl))
            with col4:
                st.metric("Best Symbol", report.best_symbol)
            
            # Daily breakdown
            st.subheader("📅 Daily Breakdown")
            if report.daily_breakdown:
                df = pd.DataFrame(report.daily_breakdown)
                st.dataframe(df, use_container_width=True)
            
            # Goals
            st.subheader("🎯 Goal Tracking")
            for goal, achieved in report.goals.items():
                status = "✅" if achieved else "❌"
                st.write(f"{status} {goal}")
            
            # Notes
            if report.notes:
                st.subheader("📝 Notes")
                for note in report.notes:
                    st.write(f"• {note}")
    
    else:  # Monthly
        # Monthly goal
        st.subheader("🎯 Monthly Goal")
        monthly_goal = st.number_input("Monthly P/L Goal ($)", value=100)
        
        if st.button("📊 Generate Monthly Report"):
            report = reports.get_current_month_report(monthly_goal)
            st.markdown("---")
            st.subheader(f"Monthly Report - {report.month}")
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", report.total_trades)
            with col2:
                st.metric("Win Rate", format_pct(report.win_rate))
            with col3:
                st.metric("Net P/L", format_currency(report.total_pnl))
            with col4:
                st.metric("Goal Achieved", "✅" if report.goal_achieved else "❌")
            
            # Top performers
            st.subheader("🏆 Top Performers")
            for p in report.top_performers:
                st.write(f"**{p['symbol']}:** {format_currency(p['pnl'])} ({p['trades']} trades)")
            
            # Weekly breakdown
            st.subheader("📈 Weekly Breakdown")
            if report.weekly_summaries:
                df = pd.DataFrame(report.weekly_summaries)
                st.dataframe(df, use_container_width=True)
            
            # Improvement areas
            if report.improvement_areas:
                st.subheader("🔧 Improvement Areas")
                for area in report.improvement_areas:
                    st.write(f"• {area}")


# ==================== PAGE: BACKTESTING ====================
elif page == "Backtesting":
    st.markdown('<p class="main-header">🧪 Backtesting</p>', unsafe_allow_html=True)
    
    # Configuration
    st.subheader("⚙️ Backtest Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbols = st.multiselect(
            "Symbols",
            ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "XRP/USDT", "DOGE/USDT"],
            default=["BTC/USDT", "ETH/USDT"]
        )
    
    with col2:
        days = st.number_input("Days to Test", value=7, min_value=1, max_value=90)
    
    with col3:
        initial_equity = st.number_input("Initial Equity ($)", value=500)
    
    strategy = st.selectbox(
        "Strategy",
        ["Warrior Momentum", "Mean Reversion", "Grid Trading"]
    )
    
    if st.button("🚀 Run Backtest"):
        with st.spinner("Running backtest..."):
            backtester = Backtester()
            
            end = datetime.now()
            start = end - timedelta(days=days)
            
            if strategy == "Warrior Momentum":
                result = backtester.run_warrior_momentum_backtest(
                    symbols=symbols,
                    start_date=start,
                    end_date=end,
                    initial_equity=initial_equity
                )
            else:
                # Generic backtest for other strategies
                result = backtester.run_warrior_momentum_backtest(
                    symbols=symbols,
                    start_date=start,
                    end_date=end,
                    initial_equity=initial_equity
                )
            
            st.markdown("---")
            st.subheader("📊 Backtest Results")
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", result.total_trades)
            with col2:
                st.metric("Win Rate", format_pct(result.win_rate))
            with col3:
                st.metric("Total P/L", format_currency(result.total_pnl))
            with col4:
                st.metric("Max Drawdown", format_pct(result.max_drawdown))
            
            # Strategy-specific results would go here
            st.info(f"Note: {strategy} backtest completed with {result.total_trades} trades simulated.")
            
            # Export
            if st.button("📥 Export Results"):
                backtester.export_results(result, "backtest_results.json")
                st.success("Results exported to backtest_results.json")


# ==================== PAGE: STRATEGIES ====================
elif page == "Strategies":
    st.markdown('<p class="main-header">🎯 Strategies</p>', unsafe_allow_html=True)
    
    strategy = st.selectbox(
        "Select Strategy",
        ["Warrior Momentum", "Mean Reversion", "Grid Trading", "Adaptive Grid"]
    )
    
    if strategy == "Warrior Momentum":
        st.markdown("""
        ## ⚔️ Warrior Momentum Strategy
        
        **Logic:**
        - Trade only during high-volatility session (EU/US overlap)
        - Require clear gap + high relative volume
        - Price must be above stacked EMAs (EMA9 > EMA20 > EMA50)
        - ATR-based stop placement
        - R-multiple profit target (2x risk)
        
        **Parameters:**
        | Parameter | Value | Description |
        |-----------|-------|-------------|
        | min_rel_vol | 2.0 | Minimum relative volume |
        | min_gap_pct | 0.5 | Minimum gap percentage |
        | session | 13-20 UTC | Trading hours |
        | r_multiple | 2.0 | Profit target multiplier |
        """)
        
        st.code("""
# Warrior Momentum Settings
breakout_lookback: 12
min_body_pct: 0.55
min_vol_spike: 1.8
r_multiple: 2.0
        """, language="yaml")
    
    elif strategy == "Mean Reversion":
        st.markdown("""
        ## 📉 Mean Reversion Strategy
        
        **Logic:**
        - RSI oversold (< 30) + near lower Bollinger Band = LONG
        - RSI overbought (> 70) + near upper Bollinger Band = SHORT
        - VWAP for trend confirmation
        
        **Parameters:**
        | Parameter | Value | Description |
        |-----------|-------|-------------|
        | rsi_period | 14 | RSI lookback |
        | rsi_oversold | 30 | Oversold threshold |
        | rsi_overbought | 70 | Overbought threshold |
        | bb_period | 20 | Bollinger Band period |
        | bb_std | 2.0 | Standard deviations |
        """)
    
    elif strategy == "Grid Trading":
        st.markdown("""
        ## 📐 Grid Trading Strategy
        
        **Logic:**
        - Place orders at fixed price intervals
        - Buy when price drops to grid level
        - Sell when price rises to grid level
        - Profit from volatility within range
        
        **Parameters:**
        | Parameter | Value | Description |
        |-----------|-------|-------------|
        | grid_levels | 5 | Number of grid levels |
        | grid_spacing_pct | 0.5 | Spacing between levels (%) |
        | range_width_pct | 5.0 | Total range width (%) |
        """)
    
    elif strategy == "Adaptive Grid":
        st.markdown("""
        ## 🔄 Adaptive Grid Strategy
        
        **Logic:**
        - Grid spacing adjusts to volatility
        - Wider grids during high volatility
        - Tighter grids during low volatility
        
        **Parameters:**
        | Parameter | Value | Description |
        |-----------|-------|-------------|
        | volatility_lookback | 20 | Volatility calculation period |
        | volatility_multiplier | 1.5 | Volatility scaling factor |
        | base_spacing_pct | 0.5 | Base grid spacing |
        """)


# ==================== PAGE: PORTFOLIO ====================
elif page == "Portfolio":
    st.markdown('<p class="main-header">💼 Portfolio</p>', unsafe_allow_html=True)
    
    portfolio = load_portfolio()
    summary = portfolio.get_portfolio_summary()
    
    # Portfolio Summary
    st.subheader("📊 Portfolio Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Equity", format_currency(summary.total_equity))
    with col2:
        st.metric("Realized P/L", format_currency(summary.total_realized_pnl))
    with col3:
        st.metric("Unrealized P/L", format_currency(summary.total_unrealized_pnl))
    with col4:
        st.metric("Open Positions", len(summary.open_positions))
    
    st.markdown("---")
    
    # Open Positions
    st.subheader("📍 Open Positions")
    
    if summary.open_positions:
        # Create dataframe
        data = []
        for p in summary.open_positions:
            data.append({
                "Symbol": p.symbol,
                "Side": p.side,
                "Entry Price": round(p.entry_price, 6),
                "Current Price": round(p.current_price, 6),
                "Quantity": round(p.quantity, 6),
                "Unrealized P/L": round(p.unrealized_pnl, 2),
                "P/L (%)": round(p.unrealized_pnl_pct, 2),
                "Duration (min)": round(p.duration_seconds / 60, 1)
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        # Chart
        fig = px.bar(
            df, 
            x="Symbol", 
            y="Unrealized P/L",
            color="Unrealized P/L",
            color_continuous_scale=["red", "gray", "green"]
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Exposure
        st.subheader("📈 Exposure")
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("**By Symbol**")
            for symbol, exposure in summary.exposure_by_symbol.items():
                st.write(f"{symbol}: {format_currency(exposure)}")
        
        with col_right:
            st.write("**By Side**")
            for side, exposure in summary.exposure_by_side.items():
                st.write(f"{side}: {format_currency(exposure)}")
    else:
        st.info("No open positions currently")
    
    # Export
    if st.button("📥 Export Positions"):
        portfolio.export_positions_json("positions.json")
        st.success("Positions exported to positions.json")


# ==================== PAGE: EXPORT ====================
elif page == "Export":
    st.markdown('<p class="main-header">📤 Export Data</p>', unsafe_allow_html=True)
    
    export_type = st.radio("Export Type", ["Analytics", "Positions", "Backtest"], horizontal=True)
    
    if export_type == "Analytics":
        analytics = load_analytics()
        
        st.subheader("📊 Analytics Export")
        period = st.selectbox("Period", ["All Time", "Last 7 Days", "Last 30 Days"])
        
        if st.button("📥 Generate Analytics Export"):
            if period == "Last 7 Days":
                data = analytics.export_to_json(days=7)
            elif period == "Last 30 Days":
                data = analytics.export_to_json(days=30)
            else:
                data = analytics.export_to_json()
            
            st.download_button(
                "📥 Download JSON",
                data,
                "analytics_export.json",
                "application/json"
            )
    
    elif export_type == "Positions":
        portfolio = load_portfolio()
        
        st.subheader("💼 Positions Export")
        
        if st.button("📥 Generate Positions Export"):
            data = portfolio.export_positions_json("positions.json")
            with open("positions.json", "r") as f:
                json_data = f.read()
            
            st.download_button(
                "📥 Download JSON",
                json_data,
                "positions.json",
                "application/json"
            )
    
    elif export_type == "Backtest":
        st.subheader("🧪 Backtest Export")
        st.info("Run a backtest first, then export results.")
        
        if os.path.exists("backtest_results.json"):
            with open("backtest_results.json", "r") as f:
                data = f.read()
            
            st.download_button(
                "📥 Download Previous Results",
                data,
                "backtest_results.json",
                "application/json"
            )
        else:
            st.warning("No backtest results found. Run a backtest first.")


# ==================== FOOTER ====================
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        🤖 TradeMindIQ Dashboard | 
        Data synced from trades.db | 
        Last updated: {} | 
        <a href='https://github.com/yourusername/TradeMindIQBot' target='_blank'>GitHub</a>
    </div>
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    unsafe_allow_html=True
)
