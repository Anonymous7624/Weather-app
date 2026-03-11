/**
 * Clearcast - Vanilla JS
 * Theme, autocomplete, geolocation, radar, charts, progressive disclosure
 */

const Clearcast = (function () {
    const loadingId = 'loading-overlay';
    const DEBOUNCE_MS = 300;

    function showLoading() {
        const el = document.getElementById(loadingId);
        if (el) el.classList.remove('hidden');
    }

    function hideLoading() {
        const el = document.getElementById(loadingId);
        if (el) el.classList.add('hidden');
    }

    function initThemeToggle() {
        const btn = document.querySelector('.theme-toggle');
        if (!btn) return;

        const stored = localStorage.getItem('clearcast-theme') || localStorage.getItem('clearer-weather-theme');
        if (stored === 'light' || (stored === null && window.matchMedia('(prefers-color-scheme: light)').matches)) {
            document.body.classList.remove('theme-dark');
            document.body.classList.add('theme-light');
        } else {
            document.body.classList.remove('theme-light');
            document.body.classList.add('theme-dark');
        }

        btn.addEventListener('click', function () {
            const isLight = document.body.classList.contains('theme-light');
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

    function initSearchForms() {
        const forms = document.querySelectorAll('form[action*="/weather"], form[action*="/weather?"]');
        forms.forEach(function (form) {
            form.addEventListener('submit', function (e) {
                const input = form.querySelector('input[name="location"]');
                if (input && input.value.trim()) {
                    showLoading();
                }
            });
        });
    }

    function initAutocomplete(inputId, dropdownId) {
        const input = document.getElementById(inputId);
        const dropdown = document.getElementById(dropdownId);
        if (!input || !dropdown) return;

        let debounceTimer;
        let selectedIndex = -1;
        let suggestions = [];

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
                const s = suggestions[idx];
                input.value = s.display_name;
                hideSuggestions();
                const form = input.closest('form');
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
                        const btn = document.createElement('button');
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
            const q = input.value.trim();
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
            const items = dropdown.querySelectorAll('.suggestion-item');
            items.forEach(function (item, i) {
                item.setAttribute('aria-selected', i === selectedIndex);
                if (i === selectedIndex) {
                    item.scrollIntoView({ block: 'nearest' });
                }
            });
        }

        input.addEventListener('blur', function () {
            setTimeout(hideSuggestions, 150);
        });

        document.addEventListener('click', function (e) {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                hideSuggestions();
            }
        });
    }

    function initUseLocation(selector) {
        document.querySelectorAll(selector).forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!navigator.geolocation) {
                    alert('Geolocation is not supported by your browser.');
                    return;
                }
                btn.disabled = true;
                const origText = btn.textContent;
                btn.textContent = 'Locating…';
                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        const lat = pos.coords.latitude.toFixed(4);
                        const lon = pos.coords.longitude.toFixed(4);
                        showLoading();
                        window.location.href = '/weather?location=' + encodeURIComponent(lat + ',' + lon);
                    },
                    function () {
                        btn.disabled = false;
                        btn.textContent = origText;
                        alert('Could not get your location. Please check permissions or try again.');
                    }
                );
            });
        });
    }

    function initAddFavorite() {
        document.querySelectorAll('.add-favorite-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const loc = btn.getAttribute('data-location');
                if (!loc) return;

                fetch('/api/add-favorite', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location: loc }),
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.ok) {
                            btn.textContent = '★ In Favorites';
                            btn.disabled = true;
                            const removeBtn = document.querySelector('.remove-favorite-btn');
                            if (removeBtn) removeBtn.style.display = '';
                        }
                    })
                    .catch(function () {});
            });
        });
    }

    function initRemoveFavorite() {
        document.querySelectorAll('.remove-favorite-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const loc = btn.getAttribute('data-location');
                if (!loc) return;

                fetch('/api/remove-favorite', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location: loc }),
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.ok) {
                            const addBtn = document.querySelector('.add-favorite-btn');
                            if (addBtn) {
                                addBtn.textContent = '★ Add to Favorites';
                                addBtn.disabled = false;
                            }
                            btn.style.display = 'none';
                        }
                    })
                    .catch(function () {});
            });
        });
    }

    function initRadar(lat, lon) {
        const mapEl = document.getElementById('radar-map');
        if (!mapEl || typeof L === 'undefined') return;

        lat = parseFloat(lat) || 39;
        lon = parseFloat(lon) || -98;

        const map = L.map('radar-map', {
            center: [lat, lon],
            zoom: 8,
            zoomControl: true,
        });
        L.control.zoom({ position: 'topright' }).addTo(map);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 19,
        }).addTo(map);

        try {
            const radarLayer = L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi', {
                layers: 'nexrad-n0q-900913',
                format: 'image/png',
                transparent: true,
                opacity: 0.6,
                attribution: 'Radar: NOAA/IEM',
            });
            radarLayer.addTo(map);
        } catch (err) {
            try {
                const fallback = L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi', {
                    layers: 'nexrad-n0r-900913',
                    format: 'image/png',
                    transparent: true,
                    opacity: 0.6,
                    attribution: 'Radar: NOAA/IEM',
                });
                fallback.addTo(map);
            } catch (e) {
                console.warn('Radar overlay unavailable, map only');
            }
        }

        L.marker([lat, lon]).addTo(map)
            .bindPopup('Your location')
            .openPopup();

        mapEl._leaflet_map = map;
    }

    function initSectionNav() {
        const pills = document.querySelectorAll('.nav-pill');
        const sections = document.querySelectorAll('.dashboard-section[data-section]');
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
                const sectionId = pill.getAttribute('data-section');
                const target = document.getElementById(sectionId) || document.querySelector('[data-section="' + sectionId + '"]');
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setActive(sectionId);
                    if (sectionId === 'radar') {
                        setTimeout(function () {
                            const mapEl = document.getElementById('radar-map');
                            if (mapEl && mapEl._leaflet_map) {
                                mapEl._leaflet_map.invalidateSize();
                            }
                        }, 300);
                    }
                }
            });
        });

        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    const id = entry.target.getAttribute('data-section') || entry.target.id;
                    if (id) setActive(id);
                }
            });
        }, { rootMargin: '-100px 0px -60% 0px', threshold: 0 });

        sections.forEach(function (s) {
            observer.observe(s);
        });
    }

    function initExpandableCards() {
        function toggleExpand(trigger, content, isExpanded) {
            if (isExpanded) {
                content.hidden = false;
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'true');
                    if (trigger.classList.contains('current-expand-btn')) {
                        trigger.textContent = 'Less details';
                    }
                    if (trigger.classList.contains('alert-card-trigger')) {
                        const chev = trigger.querySelector('.expand-chevron');
                        if (chev) chev.textContent = '▲';
                    }
                }
            } else {
                content.hidden = true;
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'false');
                    if (trigger.classList.contains('current-expand-btn')) {
                        trigger.textContent = 'More details';
                    }
                    if (trigger.classList.contains('alert-card-trigger')) {
                        const chev = trigger.querySelector('.expand-chevron');
                        if (chev) chev.textContent = '▼';
                    }
                }
            }
        }

        document.querySelectorAll('.current-expand-btn').forEach(function (btn) {
            const targetId = btn.getAttribute('data-expand-target');
            const content = document.getElementById(targetId);
            if (!content) return;
            btn.addEventListener('click', function () {
                const expanded = content.hidden;
                toggleExpand(btn, content, expanded);
            });
        });

        document.querySelectorAll('.alert-card-trigger').forEach(function (btn) {
            const content = btn.nextElementSibling;
            if (!content) return;
            btn.addEventListener('click', function () {
                const expanded = content.hidden;
                toggleExpand(btn, content, expanded);
            });
        });

        document.querySelectorAll('.hourly-card-trigger').forEach(function (btn) {
            const card = btn.closest('.hourly-card');
            const content = card ? card.querySelector('.hourly-expandable') : null;
            if (!content) return;
            btn.addEventListener('click', function () {
                const expanded = content.hidden;
                toggleExpand(btn, content, expanded);
                if (expanded) {
                    const placeholder = content.querySelector('.hourly-chart-placeholder');
                    if (placeholder && placeholder.dataset.index !== undefined) {
                        Clearcast.renderHourlyChart(placeholder, parseInt(placeholder.dataset.index, 10));
                    }
                }
            });
        });

        document.querySelectorAll('.daily-card-trigger').forEach(function (btn) {
            const card = btn.closest('.daily-card');
            const content = card ? card.querySelector('.daily-expandable') : null;
            if (!content) return;
            btn.addEventListener('click', function () {
                const expanded = content.hidden;
                toggleExpand(btn, content, expanded);
                if (expanded) {
                    const placeholder = content.querySelector('.daily-chart-placeholder');
                    if (placeholder && placeholder.dataset.periodIndex !== undefined) {
                        Clearcast.renderDailyChart(placeholder, parseInt(placeholder.dataset.periodIndex, 10));
                    }
                }
            });
        });
    }

    let chartHourlyData = [];

    function initCharts(data) {
        chartHourlyData = data || [];
    }

    function renderHourlyChart(placeholder, startIndex) {
        if (typeof Chart === 'undefined' || !chartHourlyData.length) return;
        if (placeholder.chartInstance) {
            placeholder.chartInstance.destroy();
        }
        const ctx = document.createElement('canvas');
        ctx.width = placeholder.offsetWidth || 280;
        ctx.height = 120;
        placeholder.innerHTML = '';
        placeholder.appendChild(ctx);

        const slice = chartHourlyData.slice(startIndex, startIndex + 12);
        const labels = slice.map(function (d) { return d.time; });
        const temps = slice.map(function (d) { return d.temp; });
        const precip = slice.map(function (d) { return d.precip; });

        const isDark = document.body.classList.contains('theme-dark');
        const textColor = isDark ? '#8b9cad' : '#656d76';

        placeholder.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Temp °F',
                        data: temps,
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Precip %',
                        data: precip,
                        borderColor: '#3fb950',
                        backgroundColor: 'rgba(63, 185, 80, 0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: textColor } },
                },
                scales: {
                    x: { ticks: { color: textColor, maxRotation: 45 } },
                    y: { type: 'linear', display: true, position: 'left', ticks: { color: textColor } },
                    y1: { type: 'linear', display: true, position: 'right', min: 0, max: 100, ticks: { color: textColor } },
                },
            },
        });
    }

    function renderDailyChart(placeholder, periodIndex) {
        if (typeof Chart === 'undefined' || !chartHourlyData.length) return;
        if (placeholder.chartInstance) {
            placeholder.chartInstance.destroy();
        }
        const ctx = document.createElement('canvas');
        ctx.width = placeholder.offsetWidth || 280;
        ctx.height = 120;
        placeholder.innerHTML = '';
        placeholder.appendChild(ctx);

        const start = Math.min(periodIndex * 6, Math.max(0, chartHourlyData.length - 24));
        const slice = chartHourlyData.slice(start, start + 24);
        if (!slice.length) return;
        const labels = slice.map(function (d) { return d.time; });
        const temps = slice.map(function (d) { return d.temp; });
        const precip = slice.map(function (d) { return d.precip; });

        const isDark = document.body.classList.contains('theme-dark');
        const textColor = isDark ? '#8b9cad' : '#656d76';

        placeholder.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Temp °F',
                        data: temps,
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Precip %',
                        data: precip,
                        borderColor: '#3fb950',
                        backgroundColor: 'rgba(63, 185, 80, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: textColor } },
                },
                scales: {
                    x: { ticks: { color: textColor, maxRotation: 45 } },
                    y: { ticks: { color: textColor } },
                },
            },
        });
    }

    function initAutoRefresh(intervalMs) {
        if (!intervalMs || intervalMs < 60000) return;

        const dash = document.querySelector('.dashboard[data-location]');
        if (!dash) return;

        const location = dash.getAttribute('data-location');
        if (!location) return;

        setInterval(function () {
            window.location.href = '/weather?location=' + encodeURIComponent(location);
        }, intervalMs);
    }

    function init() {
        initThemeToggle();
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
        initAutocomplete: initAutocomplete,
        initUseLocation: initUseLocation,
        initRadar: initRadar,
        initSectionNav: initSectionNav,
        initExpandableCards: initExpandableCards,
        initCharts: initCharts,
        initRemoveFavorite: initRemoveFavorite,
        renderHourlyChart: renderHourlyChart,
        renderDailyChart: renderDailyChart,
        showLoading: showLoading,
        hideLoading: hideLoading,
    };
})();

document.addEventListener('DOMContentLoaded', Clearcast.init);
