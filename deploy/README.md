# TrendLab Deployment Guide

Choose the method that works best for you:

| Method | Best For |
|--------|----------|
| **Systemd** | Direct install on Linux (recommended for mini PC) |
| **Docker** | Isolated container, easy updates |

---

## Option 1: Systemd Service (Recommended)

### 1. Build the frontend
```bash
cd frontend && npm run build
```

### 2. Create a systemd service file
```bash
sudo nano /etc/systemd/system/trendlab.service
```

Paste this content:
```ini
[Unit]
Description=TrendLab API Server
After=network.target

[Service]
Type=simple
User=hexi
WorkingDirectory=/home/hexi/local/src/trendlab
Environment="PATH=/home/hexi/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/hexi/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable trendlab
sudo systemctl start trendlab
```

### 4. Check status
```bash
sudo systemctl status trendlab
journalctl -u trendlab -f  # view logs
```

## Access

- **Local**: http://localhost:8000
- **LAN**: http://YOUR_IP:8000

## Reverse Proxy with Nginx (Optional)

If you want to serve on port 80/443 with SSL:

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/trendlab
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # or your local IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/trendlab /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

## Commands

- `sudo systemctl start trendlab` - Start
- `sudo systemctl stop trendlab` - Stop
- `sudo systemctl restart trendlab` - Restart
- `journalctl -u trendlab -f` - View logs

---

## Option 2: Docker

### Build and run
```bash
docker build -t trendlab .
docker run -d --name trendlab \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=your-key-here \
  -v trendlab-data:/app/data \
  --restart unless-stopped \
  trendlab
```

### Commands
- `docker logs -f trendlab` - View logs
- `docker restart trendlab` - Restart
- `docker stop trendlab` - Stop

---

## Environment Variables

Create a `.env` file or set these:

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Required for AI features
GITHUB_TOKEN=ghp_...            # Optional: GitHub stars adapter
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
RATE_LIMIT_ENABLED=true         # Protect from abuse
TRENDLAB_SECRET_PHRASE=your-secret-here   # Secret phrase to unlock the app
```

## Authentication

If `TRENDLAB_SECRET_PHRASE` is set, the app shows a lock screen. Users must type the exact phrase to unlock.

- Session is stored in a cookie (30 days)
- API endpoints are also protected
- Wrong phrase shows "No results found" (looks like a search error)
