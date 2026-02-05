#!/bin/bash
# TrendLab deployment script

set -e

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Checking Python dependencies..."
uv sync

echo ""
echo "Build complete! To deploy as a service:"
echo ""
echo "1. Create the systemd service file:"
echo "   sudo nano /etc/systemd/system/trendlab.service"
echo ""
echo "2. Paste this content:"
cat << 'EOF'
[Unit]
Description=TrendLab API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$HOME/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "3. Enable and start:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable trendlab"
echo "   sudo systemctl start trendlab"
echo ""
echo "Then access at http://localhost:8000"
