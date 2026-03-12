/**
 * Clearcast — Unified JS
 * Theme, autocomplete, geolocation, radar animation, charts, favorites/recents
 * (localStorage), progressive disclosure, scroll reveal, tabs
 */

var Clearcast = (function () {
    'use strict';

    var loadingId = 'loading-overlay';
    var DEBOUNCE_MS = 300;

    /* ─── Constants for localStorage ─── */
    var FAVORITES_KEY = 'clearcast-favorites';
    var RECENTS_KEY = 'clearcast-recents';
    var MAX_FAVORITES = 10;
    var MAX_RECENTS = 5;

    /* ─── Loading overlay ─── */
    function showLoading() {
        var el = document.getElementById(loadingId);
        if (el) el.classList.remove('hidden');
    }

    function hideLoading() {
        var el = document.getElementById(loadingId);
        if (el) el.classList.add('hidden');
    }

    /* ─── Theme toggle ─── */
    function initThemeToggle() {
        var btn = document.querySelector('.theme-toggle');
        if (!btn) return;

        var stored = localStorage.getItem('clearcast-theme') || localStorage.getItem('clearer-weather-theme');
        if (stored === 'light' || (stored === null && window.matchMedia('(prefers-color-scheme: light)').matches)) {
            document.body.classList.remove('theme-dark');
            document.body.classList.add('theme-light');
        } else {
            document.body.classList.remove('theme-light');
            document.body.classList.add('theme-dark');
        }

        btn.addEventListener('click', function () {
            var isLight = document.body.classList.contains('theme-light');
            if (isLight) {
                document.body.classList.remove('theme-light');
                document.body.classList.add('theme-dark');
                localStorage.setItem('clearcast-theme', 'dark');
            } else {
                document.body.classList.remove('theme-dark');
                document.body.classList.add('theme-light');
                localStorage.setItem('clearcast-theme', 'light');
            }
        });
    }

    /* ─── Nav scroll effect ─── */
    function initNavScroll() {
        var nav = document.querySelector('.nav');
        if (!nav) return;

        function check() {
            if (window.scrollY > 20) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        }

        check();
        window.addEventListener('scroll', check, { passive: true });
    }

    /* ─── Scroll reveal ─── */
    function initScrollReveal() {
        var elements = document.querySelectorAll('.reveal');
        if (!elements.length) return;

        if (!('IntersectionObserver' in window)) {
            elements.forEach(function (el) { el.classList.add('visible'); });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.08,
            rootMargin: '0px 0px -30px 0px'
        });

        elements.forEach(function (el) {
            observer.observe(el);
        });
    }

    /* ─── Search forms loading indicator ─── */
    function initSearchForms() {
        var forms = document.querySelectorAll('form[action*="/weather"]');
        forms.forEach(function (form) {
            form.addEventListener('submit', function () {
                var input = form.querySelector('input[name="location"]');
                if (input && input.value.trim()) {
                    showLoading();
                }
            });
        });
    }

    /* ─── Autocomplete ─── */
    function initAutocomplete(inputId, dropdownId) {
        var input = document.getElementById(inputId);
        var dropdown = document.getElementById(dropdownId);
        if (!input || !dropdown) return;

        var debounceTimer;
        var selectedIndex = -1;
        var suggestions = [];

        function hideSuggestions() {
            dropdown.classList.add('hidden');
            dropdown.innerHTML = '';
            selectedIndex = -1;
            input.setAttribute('aria-expanded', 'false');
        }

        function showSuggestions() {
            if (suggestions.length > 0) {
                dropdown.classList.remove('hidden');
                input.setAttribute('aria-expanded', 'true');
            }
        }

        function selectSuggestion(idx) {
            if (idx >= 0 && idx < suggestions.length) {
                var s = suggestions[idx];
                input.value = s.display_name;
                hideSuggestions();
                var form = input.closest('form');
                if (form) {
                    showLoading();
                    form.submit();
                }
            }
        }

        function fetchSuggestions(q) {
            if (q.length < 2) {
                hideSuggestions();
                return;
            }
            fetch('/api/geocode-suggest?q=' + encodeURIComponent(q) + '&limit=8')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    suggestions = data || [];
                    dropdown.innerHTML = '';
                    selectedIndex = -1;
                    if (suggestions.length === 0) {
                        hideSuggestions();
                        return;
                    }
                    suggestions.forEach(function (s, i) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'suggestion-item';
                        btn.role = 'option';
                        btn.id = dropdownId + '-opt-' + i;
                        btn.textContent = s.display_name;
                        btn.setAttribute('aria-selected', 'false');
                        btn.addEventListener('click', function () {
                            selectSuggestion(i);
                        });
                        dropdown.appendChild(btn);
                    });
                    showSuggestions();
                })
                .catch(function () {
                    hideSuggestions();
                });
        }

        input.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            var q = input.value.trim();
            debounceTimer = setTimeout(function () {
                fetchSuggestions(q);
            }, DEBOUNCE_MS);
        });

        input.addEventListener('keydown', function (e) {
            if (dropdown.classList.contains('hidden')) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
                updateHighlight();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, -1);
                updateHighlight();
            } else if (e.key === 'Enter' && selectedIndex >= 0 && suggestions.length > 0) {
                e.preventDefault();
                selectSuggestion(selectedIndex);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                hideSuggestions();
            }
        });

        function updateHighlight() {
            var items = dropdown.querySelectorAll('.suggestion-item');
            items.forEach(function (item, i) {
                item.setAttribute('aria-selected', i === selectedIndex ? 'true' : 'false');
                if (i === selectedIndex) {
                    item.scrollIntoView({ block: 'nearest' });
                }
            });
        }

        input.addEventListener('blur', function () {
            setTimeout(hideSuggestions, 200);
        });

        document.addEventListener('click', function (e) {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                hideSuggestions();
            }
        });
    }

    /* ─── Geolocation ─── */
    function initUseLocation(selector) {
        document.querySelectorAll(selector).forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!navigator.geolocation) {
                    alert('Geolocation is not supported by your browser.');
                    return;
                }
                btn.disabled = true;
                var origHTML = btn.innerHTML;
                btn.textContent = 'Locating\u2026';
                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        var lat = pos.coords.latitude.toFixed(4);
                        var lon = pos.coords.longitude.toFixed(4);
                        showLoading();
                        window.location.href = '/weather?location=' + encodeURIComponent(lat + ',' + lon);
                    },
                    function () {
                        btn.disabled = false;
                        btn.innerHTML = origHTML;
                        alert('Could not get your location. Please check permissions or try again.');
                    }
                );
            });
        });
    }

    /* ────────────────────────────────────────────
     * Favorites & Recents (localStorage per-user)
     * ──────────────────────────────────────────── */
    function getFavorites() {
        try {
            return JSON.parse(localStorage.getItem(FAVORITES_KEY)) || [];
        } catch (e) { return []; }
    }

    function saveFavorites(favs) {
        try {
            localStorage.setItem(FAVORITES_KEY, JSON.stringify(favs.slice(0, MAX_FAVORITES)));
        } catch (e) { /* storage full or blocked */ }
    }

    function isFavorite(location) {
        if (!location) return false;
        var lower = location.trim().toLowerCase();
        return getFavorites().some(function (f) {
            return f.trim().toLowerCase() === lower;
        });
    }

    function addFavorite(location) {
        if (!location) return;
        var favs = getFavorites();
        var loc = location.trim();
        var lower = loc.toLowerCase();
        favs = favs.filter(function (f) { return f.trim().toLowerCase() !== lower; });
        favs.push(loc);
        saveFavorites(favs);
    }

    function removeFavorite(location) {
        if (!location) return;
        var lower = location.trim().toLowerCase();
        var favs = getFavorites().filter(function (f) { return f.trim().toLowerCase() !== lower; });
        saveFavorites(favs);
    }

    function getRecents() {
        try {
            return JSON.parse(localStorage.getItem(RECENTS_KEY)) || [];
        } catch (e) { return []; }
    }

    function addRecent(location) {
        if (!location) return;
        try {
            var recents = getRecents();
            var loc = location.trim();
            var lower = loc.toLowerCase();
            recents = recents.filter(function (r) { return r.trim().toLowerCase() !== lower; });
            recents.unshift(loc);
            localStorage.setItem(RECENTS_KEY, JSON.stringify(recents.slice(0, MAX_RECENTS)));
        } catch (e) { /* storage full or blocked */ }
    }

    function _createFavButton(location, isFav, onToggle) {
        var wrap = document.createElement('span');
        wrap.className = 'fav-btn-group';

        if (isFav) {
            var inBtn = document.createElement('button');
            inBtn.type = 'button';
            inBtn.className = 'btn btn-secondary fav-toggle-btn';
            inBtn.disabled = true;
            inBtn.innerHTML = '&#9733; In Favorites';
            wrap.appendChild(inBtn);

            var rmBtn = document.createElement('button');
            rmBtn.type = 'button';
            rmBtn.className = 'btn btn-outline fav-toggle-btn';
            rmBtn.style.marginLeft = '0.5rem';
            rmBtn.textContent = 'Remove';
            rmBtn.addEventListener('click', function () {
                removeFavorite(location);
                if (onToggle) onToggle();
            });
            wrap.appendChild(rmBtn);
        } else {
            var addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.className = 'btn btn-secondary fav-toggle-btn add-favorite-btn';
            addBtn.innerHTML = '&#9733; Add to Favorites';
            addBtn.addEventListener('click', function () {
                addFavorite(location);
                if (onToggle) onToggle();
            });
            wrap.appendChild(addBtn);
        }
        return wrap;
    }

    function initFavorites(currentLocation) {
        if (!currentLocation) return;

        function render() {
            var isFav = isFavorite(currentLocation);

            // Hero area
            var heroWrap = document.getElementById('fav-toggle-hero');
            if (heroWrap) {
                heroWrap.innerHTML = '';
                heroWrap.appendChild(_createFavButton(currentLocation, isFav, render));
            }

            // Actions area
            var actionsWrap = document.getElementById('fav-toggle-actions');
            if (actionsWrap) {
                actionsWrap.innerHTML = '';
                actionsWrap.appendChild(_createFavButton(currentLocation, isFav, render));
            }

            // Quick-switch bar
            var switchBar = document.getElementById('fav-switch-bar');
            var switchPills = document.getElementById('fav-switch-pills');
            if (switchBar && switchPills) {
                var favs = getFavorites();
                var others = favs.filter(function (f) {
                    return f.trim().toLowerCase() !== currentLocation.trim().toLowerCase();
                });
                if (others.length > 0) {
                    switchPills.innerHTML = '';
                    others.forEach(function (fav) {
                        var a = document.createElement('a');
                        a.href = '/weather?location=' + encodeURIComponent(fav);
                        a.className = 'fav-pill';
                        a.textContent = fav;
                        switchPills.appendChild(a);
                    });
                    switchBar.style.display = '';
                } else {
                    switchBar.style.display = 'none';
                }
            }
        }

        render();
    }

    function renderLandingLists() {
        var container = document.getElementById('landing-lists');
        if (!container) return;

        var favsSection = document.getElementById('landing-favorites');
        var favsList = document.getElementById('favorites-list');
        var recentsSection = document.getElementById('landing-recents');
        var recentsList = document.getElementById('recents-list');

        var favs = getFavorites();
        var recents = getRecents();
        var hasContent = false;

        if (favsSection && favsList && favs.length > 0) {
            favsList.innerHTML = '';
            favs.forEach(function (fav) {
                var li = document.createElement('li');
                var a = document.createElement('a');
                a.href = '/weather?location=' + encodeURIComponent(fav);
                a.textContent = fav;
                li.appendChild(a);
                favsList.appendChild(li);
            });
            favsSection.style.display = '';
            hasContent = true;
        }

        if (recentsSection && recentsList && recents.length > 0) {
            recentsList.innerHTML = '';
            recents.forEach(function (loc) {
                var li = document.createElement('li');
                var a = document.createElement('a');
                a.href = '/weather?location=' + encodeURIComponent(loc);
                a.textContent = loc;
                li.appendChild(a);
                recentsList.appendChild(li);
            });
            recentsSection.style.display = '';
            hasContent = true;
        }

        if (hasContent) {
            container.style.display = '';
        }
    }

    /* ─── Radar (Leaflet + RainViewer animated timeline) ─── */
    var radarState = {
        map: null,
        frames: [],
        layers: [],
        currentFrame: 0,
        playing: false,
        playInterval: null,
        pastCount: 0,
    };

    function initRadar(lat, lon) {
        var mapEl = document.getElementById('radar-map');
        if (!mapEl || typeof L === 'undefined') return;

        lat = parseFloat(lat) || 39;
        lon = parseFloat(lon) || -98;

        var map = L.map('radar-map', {
            center: [lat, lon],
            zoom: 8,
            zoomControl: false,
        });

        L.control.zoom({ position: 'topright' }).addTo(map);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '\u00a9 OpenStreetMap',
            maxZoom: 19,
        }).addTo(map);

        L.marker([lat, lon]).addTo(map)
            .bindPopup('Your location')
            .openPopup();

        mapEl._leaflet_map = map;
        radarState.map = map;

        fetch('https://api.rainviewer.com/public/weather-maps.json')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                _initRadarAnimation(map, data);
            })
            .catch(function () {
                _addStaticRadar(map);
            });
    }

    function _addStaticRadar(map) {
        try {
            L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi', {
                layers: 'nexrad-n0q-900913',
                format: 'image/png',
                transparent: true,
                opacity: 0.6,
                attribution: 'Radar: NOAA/IEM',
            }).addTo(map);
        } catch (err) {
            // Radar unavailable
        }
    }

    function _initRadarAnimation(map, apiData) {
        var host = apiData.host || '';
        var past = (apiData.radar && apiData.radar.past) || [];
        var nowcast = (apiData.radar && apiData.radar.nowcast) || [];

        if (past.length === 0 && nowcast.length === 0) {
            _addStaticRadar(map);
            return;
        }

        var frames = [];
        past.forEach(function (f) {
            frames.push({ time: f.time, path: f.path, type: 'past' });
        });
        nowcast.forEach(function (f) {
            frames.push({ time: f.time, path: f.path, type: 'forecast' });
        });

        radarState.frames = frames;
        radarState.pastCount = past.length;

        var layers = [];
        frames.forEach(function (frame) {
            var layer = L.tileLayer(host + frame.path, {
                tileSize: 256,
                opacity: 0,
                zIndex: 5,
            });
            layer.addTo(map);
            layers.push(layer);
        });
        radarState.layers = layers;

        // Show last past frame by default (= "Now")
        var startIdx = Math.max(0, past.length - 1);
        radarState.currentFrame = startIdx;
        _showRadarFrame(startIdx);

        // Show controls
        var controls = document.getElementById('radar-controls');
        if (controls) controls.style.display = '';

        // Set up slider
        var slider = document.getElementById('radar-slider');
        if (slider) {
            slider.max = frames.length - 1;
            slider.value = startIdx;
            slider.addEventListener('input', function () {
                _stopRadarPlay();
                _showRadarFrame(parseInt(this.value, 10));
            });
        }

        // Play button
        var playBtn = document.getElementById('radar-play');
        if (playBtn) {
            playBtn.addEventListener('click', function () {
                if (radarState.playing) {
                    _stopRadarPlay();
                } else {
                    _startRadarPlay();
                }
            });
        }

        // Quick buttons
        var quickBtns = document.querySelectorAll('.radar-quick-btn');
        quickBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var range = btn.getAttribute('data-range');
                _stopRadarPlay();
                quickBtns.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                if (range === 'past') {
                    _showRadarFrame(0);
                    _startRadarPlay();
                } else if (range === 'now') {
                    _showRadarFrame(Math.max(0, radarState.pastCount - 1));
                } else if (range === 'forecast') {
                    if (nowcast.length > 0) {
                        _showRadarFrame(radarState.pastCount);
                        _startRadarPlay();
                    }
                }
            });
        });

        _updateRadarDisclaimer();
    }

    function _showRadarFrame(idx) {
        if (idx < 0 || idx >= radarState.layers.length) return;
        radarState.layers.forEach(function (l, i) {
            l.setOpacity(i === idx ? 0.65 : 0);
        });
        radarState.currentFrame = idx;
        _updateRadarUI();
    }

    function _updateRadarUI() {
        var frame = radarState.frames[radarState.currentFrame];
        if (!frame) return;

        var time = new Date(frame.time * 1000);
        var timeStr = time.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

        var timeLabel = document.getElementById('radar-time');
        if (timeLabel) timeLabel.textContent = timeStr;

        var typeLabel = document.getElementById('radar-type');
        if (typeLabel) {
            if (frame.type === 'forecast') {
                typeLabel.textContent = 'Forecast';
                typeLabel.className = 'radar-type-badge radar-forecast';
            } else {
                typeLabel.textContent = 'Observed';
                typeLabel.className = 'radar-type-badge radar-observed';
            }
        }

        var slider = document.getElementById('radar-slider');
        if (slider) slider.value = radarState.currentFrame;
    }

    function _updateRadarDisclaimer() {
        var disclaimer = document.getElementById('radar-disclaimer');
        if (!disclaimer) return;
        var hasForecast = radarState.frames.some(function (f) { return f.type === 'forecast'; });
        if (hasForecast) {
            disclaimer.textContent = 'Forecast frames are short-term nowcast predictions based on current radar motion, not model-based forecasts.';
        } else {
            disclaimer.textContent = '';
        }
    }

    function _startRadarPlay() {
        radarState.playing = true;
        var playBtn = document.getElementById('radar-play');
        if (playBtn) playBtn.innerHTML = '&#9646;&#9646;';
        radarState.playInterval = setInterval(function () {
            var next = (radarState.currentFrame + 1) % radarState.frames.length;
            _showRadarFrame(next);
        }, 600);
    }

    function _stopRadarPlay() {
        radarState.playing = false;
        var playBtn = document.getElementById('radar-play');
        if (playBtn) playBtn.innerHTML = '&#9654;';
        if (radarState.playInterval) {
            clearInterval(radarState.playInterval);
            radarState.playInterval = null;
        }
    }

    /* ─── Section nav ─── */
    function initSectionNav() {
        var pills = document.querySelectorAll('.nav-pill');
        var sections = document.querySelectorAll('.dashboard-section[data-section]');
        if (!pills.length || !sections.length) return;

        function setActive(sectionId) {
            pills.forEach(function (p) {
                if (p.getAttribute('data-section') === sectionId) {
                    p.classList.add('active');
                } else {
                    p.classList.remove('active');
                }
            });
        }

        pills.forEach(function (pill) {
            pill.addEventListener('click', function (e) {
                e.preventDefault();
                var sectionId = pill.getAttribute('data-section');
                var target = document.getElementById(sectionId) || document.querySelector('[data-section="' + sectionId + '"]');
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setActive(sectionId);
                    if (sectionId === 'radar') {
                        setTimeout(function () {
                            var mapEl = document.getElementById('radar-map');
                            if (mapEl && mapEl._leaflet_map) {
                                mapEl._leaflet_map.invalidateSize();
                            }
                        }, 400);
                    }
                }
            });
        });

        if ('IntersectionObserver' in window) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        var id = entry.target.getAttribute('data-section') || entry.target.id;
                        if (id) setActive(id);
                    }
                });
            }, { rootMargin: '-120px 0px -50% 0px', threshold: 0 });

            sections.forEach(function (s) {
                observer.observe(s);
            });
        }
    }

    /* ─── Expandable cards ─── */
    function initExpandableCards() {
        function toggleExpand(trigger, content, shouldExpand) {
            if (shouldExpand) {
                content.hidden = false;
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'true');
                    if (trigger.classList.contains('current-expand-btn')) {
                        trigger.textContent = 'Hide details';
                    }
                }
                var card = trigger ? trigger.closest('.alert-card') : null;
                if (card) card.setAttribute('data-expanded', 'true');
            } else {
                content.hidden = true;
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'false');
                    if (trigger.classList.contains('current-expand-btn')) {
                        trigger.textContent = 'More info';
                    }
                }
                var card2 = trigger ? trigger.closest('.alert-card') : null;
                if (card2) card2.setAttribute('data-expanded', 'false');
            }
        }

        document.querySelectorAll('.current-expand-btn').forEach(function (btn) {
            var targetId = btn.getAttribute('data-expand-target');
            var content = document.getElementById(targetId);
            if (!content) return;
            btn.addEventListener('click', function () {
                toggleExpand(btn, content, content.hidden);
            });
        });

        document.querySelectorAll('.alert-card-trigger').forEach(function (btn) {
            var content = btn.nextElementSibling;
            if (!content) return;
            btn.addEventListener('click', function () {
                toggleExpand(btn, content, content.hidden);
            });
        });

        document.querySelectorAll('.hourly-card-trigger').forEach(function (btn) {
            var card = btn.closest('.hourly-card');
            var content = card ? card.querySelector('.hourly-expandable') : null;
            if (!content) return;
            btn.addEventListener('click', function () {
                var shouldExpand = content.hidden;
                toggleExpand(btn, content, shouldExpand);
                if (shouldExpand) {
                    var placeholder = content.querySelector('.hourly-chart-placeholder');
                    if (placeholder && placeholder.dataset.index !== undefined) {
                        Clearcast.renderHourlyChart(placeholder, parseInt(placeholder.dataset.index, 10));
                    }
                }
            });
        });
    }

    /* ─── Charts ─── */
    var chartHourlyData = [];

    function initCharts(data) {
        chartHourlyData = data || [];
    }

    function getChartColors() {
        var isDark = document.body.classList.contains('theme-dark');
        return {
            text: isDark ? '#8b9cad' : '#656d76',
            grid: isDark ? 'rgba(48, 54, 61, 0.5)' : 'rgba(208, 215, 222, 0.5)',
            accent: '#58a6ff',
            accentBg: 'rgba(88, 166, 255, 0.1)',
            success: '#3fb950',
            successBg: 'rgba(63, 185, 80, 0.1)',
            warning: '#d29922',
            warningBg: 'rgba(210, 153, 34, 0.1)',
            danger: '#f85149',
            dangerBg: 'rgba(248, 81, 73, 0.1)',
        };
    }

    function chartDefaults() {
        var c = getChartColors();
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleFont: { size: 12 },
                    bodyFont: { size: 12 },
                    padding: 10,
                    cornerRadius: 8,
                    displayColors: false,
                },
            },
            scales: {
                x: {
                    ticks: { color: c.text, maxRotation: 45, font: { size: 11 } },
                    grid: { color: c.grid },
                },
                y: {
                    ticks: { color: c.text, font: { size: 11 } },
                    grid: { color: c.grid },
                },
            },
        };
    }

    function renderHourlyChart(placeholder, startIndex) {
        if (typeof Chart === 'undefined' || !chartHourlyData.length) return;
        if (placeholder.chartInstance) {
            placeholder.chartInstance.destroy();
        }
        var ctx = document.createElement('canvas');
        ctx.width = placeholder.offsetWidth || 250;
        ctx.height = 100;
        placeholder.innerHTML = '';
        placeholder.appendChild(ctx);

        var slice = chartHourlyData.slice(startIndex, startIndex + 12);
        var labels = slice.map(function (d) { return d.time; });
        var temps = slice.map(function (d) { return d.temp; });
        var c = getChartColors();

        placeholder.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Temp \u00b0F',
                    data: temps,
                    borderColor: c.accent,
                    backgroundColor: c.accentBg,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2,
                    borderWidth: 2,
                }],
            },
            options: chartDefaults(),
        });
    }

    /* ─── Day detail charts ─── */
    function renderDayCharts(chartData) {
        if (typeof Chart === 'undefined' || !chartData || !chartData.length) return;
        var c = getChartColors();
        var labels = chartData.map(function (d) { return d.time; });
        var baseOpts = chartDefaults();

        // Temperature
        var tempEl = document.getElementById('day-temp-chart');
        if (tempEl) {
            var tempData = chartData.map(function (d) { return d.temp; });
            var tempCanvas = document.createElement('canvas');
            tempEl.appendChild(tempCanvas);
            new Chart(tempCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Temperature (\u00b0F)',
                        data: tempData,
                        borderColor: c.accent,
                        backgroundColor: c.accentBg,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        borderWidth: 2,
                    }],
                },
                options: Object.assign({}, baseOpts, {
                    plugins: Object.assign({}, baseOpts.plugins, {
                        tooltip: Object.assign({}, baseOpts.plugins.tooltip, {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.y + '\u00b0F'; },
                            },
                        }),
                    }),
                }),
            });
        }

        // Precipitation
        var precipEl = document.getElementById('day-precip-chart');
        if (precipEl) {
            var precipCanvas = document.createElement('canvas');
            precipEl.appendChild(precipCanvas);
            new Chart(precipCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Precip %',
                        data: chartData.map(function (d) { return d.precip; }),
                        backgroundColor: c.accent,
                        borderRadius: 4,
                    }],
                },
                options: Object.assign({}, baseOpts, {
                    scales: Object.assign({}, baseOpts.scales, {
                        y: Object.assign({}, baseOpts.scales.y, { min: 0, max: 100 }),
                    }),
                    plugins: Object.assign({}, baseOpts.plugins, {
                        tooltip: Object.assign({}, baseOpts.plugins.tooltip, {
                            callbacks: {
                                label: function (ctx) { return (ctx.parsed.y || 0) + '%'; },
                            },
                        }),
                    }),
                }),
            });
        }

        // Wind
        var windEl = document.getElementById('day-wind-chart');
        if (windEl) {
            var windCanvas = document.createElement('canvas');
            windEl.appendChild(windCanvas);
            new Chart(windCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Wind (mph)',
                        data: chartData.map(function (d) { return d.wind; }),
                        borderColor: c.warning,
                        backgroundColor: c.warningBg,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        borderWidth: 2,
                    }],
                },
                options: Object.assign({}, baseOpts, {
                    plugins: Object.assign({}, baseOpts.plugins, {
                        tooltip: Object.assign({}, baseOpts.plugins.tooltip, {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.y + ' mph'; },
                            },
                        }),
                    }),
                }),
            });
        }

        // Humidity
        var humidityEl = document.getElementById('day-humidity-chart');
        if (humidityEl) {
            var humidCanvas = document.createElement('canvas');
            humidityEl.appendChild(humidCanvas);
            new Chart(humidCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Humidity %',
                        data: chartData.map(function (d) { return d.humidity; }),
                        borderColor: c.success,
                        backgroundColor: c.successBg,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        borderWidth: 2,
                    }],
                },
                options: Object.assign({}, baseOpts, {
                    scales: Object.assign({}, baseOpts.scales, {
                        y: Object.assign({}, baseOpts.scales.y, { min: 0, max: 100 }),
                    }),
                    plugins: Object.assign({}, baseOpts.plugins, {
                        tooltip: Object.assign({}, baseOpts.plugins.tooltip, {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.y + '%'; },
                            },
                        }),
                    }),
                }),
            });
        }
    }

    /* ─── Day detail tabs ─── */
    function initDayDetailTabs() {
        var tabs = document.querySelectorAll('.detail-tab');
        var panels = document.querySelectorAll('.detail-tab-panel');
        if (!tabs.length) return;

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                var target = tab.getAttribute('data-tab');
                tabs.forEach(function (t) {
                    t.classList.remove('active');
                    t.setAttribute('aria-selected', 'false');
                });
                panels.forEach(function (p) {
                    p.classList.remove('active');
                });
                tab.classList.add('active');
                tab.setAttribute('aria-selected', 'true');
                var panel = document.querySelector('[data-tab-panel="' + target + '"]');
                if (panel) panel.classList.add('active');
            });
        });
    }

    /* ─── Auto refresh ─── */
    function initAutoRefresh(intervalMs) {
        if (!intervalMs || intervalMs < 60000) return;
        var dash = document.querySelector('.dashboard[data-location]');
        if (!dash) return;
        var location = dash.getAttribute('data-location');
        if (!location) return;

        setInterval(function () {
            window.location.href = '/weather?location=' + encodeURIComponent(location);
        }, intervalMs);
    }

    /* ─── Init ─── */
    function init() {
        initThemeToggle();
        initNavScroll();
        initScrollReveal();
        initSearchForms();
        hideLoading();
    }

    function initDashboard(opts) {
        init();
        if (opts && opts.refreshInterval) {
            initAutoRefresh(opts.refreshInterval);
        }
    }

    return {
        init: init,
        initDashboard: initDashboard,
        initDayDetail: function () {
            init();
            initDayDetailTabs();
        },
        initAutocomplete: initAutocomplete,
        initUseLocation: initUseLocation,
        initRadar: initRadar,
        initSectionNav: initSectionNav,
        initExpandableCards: initExpandableCards,
        initCharts: initCharts,
        initFavorites: initFavorites,
        addRecent: addRecent,
        renderLandingLists: renderLandingLists,
        renderHourlyChart: renderHourlyChart,
        renderDayCharts: renderDayCharts,
        showLoading: showLoading,
        hideLoading: hideLoading,
    };
})();

document.addEventListener('DOMContentLoaded', Clearcast.init);
