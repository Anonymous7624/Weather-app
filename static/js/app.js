/**
 * Clearcast — Unified JS
 * Theme, autocomplete, geolocation, radar, charts, progressive disclosure,
 * scroll reveal, nav scroll, tabs, day detail charts
 */

var Clearcast = (function () {
    'use strict';

    var loadingId = 'loading-overlay';
    var DEBOUNCE_MS = 300;

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

    /* ─── Nav scroll effect (matching homepage) ─── */
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

    /* ─── Scroll reveal (matching homepage) ─── */
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

    /* ─── Add favorite ─── */
    function initAddFavorite() {
        document.querySelectorAll('.add-favorite-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var loc = btn.getAttribute('data-location');
                if (!loc) return;

                fetch('/api/add-favorite', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location: loc }),
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.ok) {
                            btn.textContent = '\u2733 In Favorites';
                            btn.disabled = true;
                            document.querySelectorAll('.add-favorite-btn').forEach(function (b) {
                                b.textContent = '\u2733 In Favorites';
                                b.disabled = true;
                            });
                            var removeBtn = document.querySelector('.remove-favorite-btn');
                            if (removeBtn) removeBtn.style.display = '';
                        }
                    })
                    .catch(function () {});
            });
        });
    }

    /* ─── Remove favorite ─── */
    function initRemoveFavorite() {
        document.querySelectorAll('.remove-favorite-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var loc = btn.getAttribute('data-location');
                if (!loc) return;

                fetch('/api/remove-favorite', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location: loc }),
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.ok) {
                            document.querySelectorAll('.add-favorite-btn').forEach(function (b) {
                                b.textContent = '\u2733 Add to Favorites';
                                b.disabled = false;
                            });
                            btn.style.display = 'none';
                        }
                    })
                    .catch(function () {});
            });
        });
    }

    /* ─── Radar (Leaflet + NEXRAD) ─── */
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

        try {
            L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi', {
                layers: 'nexrad-n0q-900913',
                format: 'image/png',
                transparent: true,
                opacity: 0.6,
                attribution: 'Radar: NOAA/IEM',
            }).addTo(map);
        } catch (err) {
            try {
                L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi', {
                    layers: 'nexrad-n0r-900913',
                    format: 'image/png',
                    transparent: true,
                    opacity: 0.6,
                    attribution: 'Radar: NOAA/IEM',
                }).addTo(map);
            } catch (e) {
                // Radar unavailable
            }
        }

        L.marker([lat, lon]).addTo(map)
            .bindPopup('Your location')
            .openPopup();

        mapEl._leaflet_map = map;
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
                        trigger.textContent = 'Show details';
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
            plugins: {
                legend: { display: false },
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
            var tempCanvas = document.createElement('canvas');
            tempEl.appendChild(tempCanvas);
            new Chart(tempCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Temperature (\u00b0F)',
                        data: chartData.map(function (d) { return d.temp; }),
                        borderColor: c.accent,
                        backgroundColor: c.accentBg,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        borderWidth: 2,
                    }],
                },
                options: baseOpts,
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
                options: baseOpts,
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
                }),
            });
        }
    }

    /* ─── Day detail tabs ─── */
    function initDayDetail() {
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
        initAddFavorite();
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
            initDayDetail();
        },
        initAutocomplete: initAutocomplete,
        initUseLocation: initUseLocation,
        initRadar: initRadar,
        initSectionNav: initSectionNav,
        initExpandableCards: initExpandableCards,
        initCharts: initCharts,
        initRemoveFavorite: initRemoveFavorite,
        renderHourlyChart: renderHourlyChart,
        renderDayCharts: renderDayCharts,
        showLoading: showLoading,
        hideLoading: hideLoading,
    };
})();

document.addEventListener('DOMContentLoaded', Clearcast.init);
