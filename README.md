# Clearer Weather

A lightweight, production-ready weather dashboard for Raspberry Pi. Uses the official [National Weather Service API](https://api.weather.gov) to present forecast data in a clean, readable format.

## Features

- **Clean UI** – Card-based layout, modern typography, dark/light mode
- **NWS API** – Official api.weather.gov (no scraping)
- **Multiple input formats** – ZIP code, city/state, or latitude,longitude
- **Sections** – Current conditions, hourly forecast, extended forecast, active alerts
- **Lightweight** – Minimal dependencies, suitable for Raspberry Pi 4 (4GB)
- **Caching** – 10-minute cache to reduce API calls

## Quick Start (Raspberry Pi)

### 1. Clone from GitHub

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/clearer-weather.git
cd clearer-weather
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install requirements

```bash
pip install -r requirements.txt
```

### 4. Configure (optional)

```bash
cp .env.example .env
# Edit .env to set DEFAULT_LOCATION, etc.
```

### 5. Run locally

**Development (Flask built-in server):**

```bash
python app.py
```

**Production (bind to all interfaces on port 5050):**

```bash
gunicorn -w 1 -b 0.0.0.0:5050 app:app
```

Or with environment variable:

```bash
PORT=5050 python app.py
```

Access at `http://<pi-ip>:5050`

## Systemd Service (run continuously)

1. Copy the service file:

```bash
sudo cp clearer-weather.service /etc/systemd/system/
```

2. Edit the service file to match your paths (e.g. if installed elsewhere):

```bash
sudo nano /etc/systemd/system/clearer-weather.service
```

Adjust `WorkingDirectory`, `ExecStart`, and `Environment` as needed.

3. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clearer-weather
sudo systemctl start clearer-weather
sudo systemctl status clearer-weather
```

4. View logs:

```bash
journalctl -u clearer-weather -f
```

## Cloudflare Tunnel / Reverse Proxy

To expose the app through a tunnel or reverse proxy:

- **Cloudflare Tunnel**: Run `cloudflared tunnel` and point it to `http://localhost:5050`
- **Nginx**: Proxy `/` to `http://127.0.0.1:5050`
- **Caddy**: `reverse_proxy localhost:5050`

The app has no special headers requirements; standard reverse proxy config works.

## Project Structure

```
clearer-weather/
├── app.py                 # Flask application
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── clearer-weather.service
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── dashboard.html
│   └── error.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── utils/
│   ├── __init__.py
│   ├── config.py         # Default location, favorites, recent
│   ├── geocode.py        # Census + Nominatim geocoding
│   ├── nws.py            # NWS API client
│   ├── normalize.py      # Data normalization
│   └── cache.py          # In-memory cache
└── instance/             # Created at runtime (config.json)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_LOCATION` | (empty) | Default location on first visit |
| `PORT` | 5050 | Port to bind |
| `CACHE_TTL_SECONDS` | 600 | Cache duration (10 min) |
| `FLASK_DEBUG` | 0 | Set to 1 for debug mode |
| `SECRET_KEY` | (dev default) | Session secret |

## Tech Stack

- Python 3.9+
- Flask
- Jinja2
- Vanilla HTML/CSS/JS
- NWS API (api.weather.gov)
- Nominatim (OpenStreetMap) for geocoding

## Exact Raspberry Pi Run Commands

```bash
# Clone
cd ~
git clone https://github.com/YOUR_USERNAME/clearer-weather.git
cd clearer-weather

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt

# Optional: configure default location
cp .env.example .env
# Edit .env: DEFAULT_LOCATION=Boston, MA

# Run (development)
python3 app.py

# Run (production, bind to 0.0.0.0 on port 5050)
gunicorn -w 1 -b 0.0.0.0:5050 app:app

# Or with Flask directly on port 5050
PORT=5050 python3 app.py
```

Access at `http://<your-pi-ip>:5050`

## License

MIT
