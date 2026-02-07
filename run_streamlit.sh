#!/bin/bash
# Launch Virtue Foundation Agent Streamlit Interface

echo "🏥 Starting Virtue Foundation Agent..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Set Python path
export PYTHONPATH=/home/ali-jafar/hack-nationn:$PYTHONPATH

# Navigate to project directory
cd /home/ali-jafar/hack-nationn

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "📦 Streamlit not found. Installing..."
    pip install streamlit streamlit-folium --break-system-packages
fi

echo ""
echo "🚀 Launching Streamlit interface..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 The app will open in your browser at:"
echo "   http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run streamlit
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address localhost \
    --browser.gatherUsageStats false \
    --theme.primaryColor="#1f77b4" \
    --theme.backgroundColor="#ffffff" \
    --theme.secondaryBackgroundColor="#f0f2f6"
