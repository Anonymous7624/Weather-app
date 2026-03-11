# Clearcast

An intelligent, lightweight weather dashboard for Raspberry Pi. Uses the official [National Weather Service API](https://api.weather.gov) with a clean Flask + Jinja + vanilla JS stack. No React, no heavy frontend — just fast, readable weather.

## Features

- **Smart location** – Autocomplete search (ZIP, city/state, lat/lon), keyboard navigation, "Use My Location" via geolocation
- **Persistent location** – Selected location persists across sessions; favorites and recent searches
- **Built-in radar** – Map-based radar view inside the app, centered on your location (Leaflet + OpenStreetMap + NWS radar overlay)
- **Progressive detail** – Clean default view; expand days, hours, and alerts for deeper data
- **Advanced data on demand** – Humidity, dew point, pressure, visibility, wind gusts, sunrise/sunset, precipitation trends
- **Lightweight charts** – Temperature, precipitation, wind, and humidity trends when you drill down (Chart.js)
- **Alerts** – Clear severity, timing, expandable full detail; calm "No active alerts" state
- **Dark/light mode** – Theme toggle with system preference detection
- **Mobile & desktop** – Responsive layout; radar usable on mobile
- **Raspberry Pi ready** – Minimal dependencies, 10-minute cache, runs on Pi 4 (4GB)
- **Static homepage** – Polished product landing page suitable for GitHub Pages

## Quick Start (Raspberry Pi)

### 1. Clone and prepare

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/clearcast.git
cd clearcast
```

### 2. Virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure (optional)

```bash
cp .env.example .env
# Edit .env: DEFAULT_LOCATION=Boston, MA
```

### 5. Run

**Development:**
```bash
python3 app.py
```

**Production (bind 0.0.0.0:5050):**
```bash
gunicorn -w 1 -b 0.0.0.0:5050 app:app
```

Or with Flask directly:
```bash
PORT=5050 python3 app.py
```

Access at `http://<pi-ip>:5050`

## Built-in Radar

The radar view loads inside the app:

- **Leaflet** and **Chart.js** are loaded from CDNs (unpkg, jsDelivr)
- **OpenStreetMap** provides the base map
- **NWS radar** overlay (via IEM NEXRAD WMS) shows precipitation
- No extra setup; the radar works as long as the Pi has internet

On first opening the Radar section, the map centers on your selected location. Changing location updates the radar automatically.

## Static Homepage

The `docs/` folder contains a static product landing page designed for GitHub Pages (or any static hosting). It shares the same design language, color palette, and typography as the weather app.

**Structure:**
```
docs/
├── index.html          # Landing page
├── css/
│   └── homepage.css    # Homepage styles (same theme variables)
└── js/
    └── homepage.js     # Scroll animations, theme toggle
```

**Deployment:** Configure GitHub Pages to serve from the `docs/` folder on your main branch. The homepage lives on the root domain; the Flask weather app runs on the `weather` subdomain.

## Systemd Service

1. Copy the service file:

```bash
sudo cp clearer-weather.service /etc/systemd/system/clearcast.service
```

2. Edit if needed (paths, user, default location):

```bash
sudo nano /etc/systemd/system/clearcast.service
```

3. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clearcast
sudo systemctl start clearcast
sudo systemctl status clearcast
```

4. Logs:

```bash
journalctl -u clearcast -f
```

## Project Structure

```
clearcast/
├── app.py                    # Flask app, routes
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── clearer-weather.service    # Systemd unit
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
│   ├── config.py             # Last location, favorites, recent
│   ├── geocode.py            # Census + Nominatim
│   ├── nws.py                # NWS API client
│   ├── normalize.py          # Data normalization
│   ├── cache.py              # In-memory cache
│   └── sun.py                # Sunrise/sunset
├── docs/                     # Static homepage (GitHub Pages)
│   ├── index.html
│   ├── css/
│   │   └── homepage.css
│   └── js/
│       └── homepage.js
└── instance/                 # Runtime: config.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_LOCATION` | (empty) | Default location on first visit |
| `PORT` | 5050 | Port to bind |
| `CACHE_TTL_SECONDS` | 600 | Cache TTL (10 min) |
| `FLASK_DEBUG` | 0 | Set to 1 for debug |
| `SECRET_KEY` | (dev default) | Session secret |

## Tech Stack

- Python 3.9+
- Flask, Jinja2
- Vanilla HTML/CSS/JS (no React)
- NWS API (api.weather.gov)
- Leaflet + OpenStreetMap (CDN)
- Chart.js (CDN)
- Census + Nominatim geocoding

## Raspberry Pi Run Commands (Summary)

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/clearcast.git
cd clearcast

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Optional: DEFAULT_LOCATION=Boston, MA

# Development
python3 app.py

# Production (0.0.0.0:5050)
gunicorn -w 1 -b 0.0.0.0:5050 app:app
```

Access at `http://<your-pi-ip>:5050`

## License

MIT
