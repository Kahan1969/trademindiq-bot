#!/bin/bash
# TradeMindIQ Dashboard Launcher
# Usage: ./run_dashboard.sh

echo "🤖 Starting TradeMindIQ Dashboard..."
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✅ Using virtual environment"
    source venv/bin/activate
else
    echo "⚠️ No virtual environment found"
    echo "Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements_dashboard.txt
fi

echo ""
echo "🚀 Launching Streamlit dashboard..."
echo "📍 URL: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Launch Streamlit
streamlit run trademindiq_app.py --server.port 8501 --server.address localhost
