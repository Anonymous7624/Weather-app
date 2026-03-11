/**
 * Clearer Weather - Vanilla JS
 * Theme toggle, autocomplete, geolocation, loading state, favorites, auto-refresh
 */

const ClearerWeather = (function () {
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

        const stored = localStorage.getItem('clearer-weather-theme');
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
                localStorage.setItem('clearer-weather-theme', 'dark');
            } else {
                document.body.classList.remove('theme-dark');
                document.body.classList.add('theme-light');
                localStorage.setItem('clearer-weather-theme', 'light');
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
                hideSuggestions();
            }
        });

        function updateHighlight() {
            var items = dropdown.querySelectorAll('.suggestion-item');
            items.forEach(function (item, i) {
                item.setAttribute('aria-selected', i === selectedIndex);
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
                btn.textContent = 'Locating…';
                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        var lat = pos.coords.latitude.toFixed(4);
                        var lon = pos.coords.longitude.toFixed(4);
                        showLoading();
                        window.location.href = '/weather?location=' + lat + ',' + lon;
                    },
                    function () {
                        btn.disabled = false;
                        btn.textContent = '📍 Use My Location';
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
                            var removeBtn = document.querySelector('.remove-favorite-btn');
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
                            var addBtn = document.querySelector('.add-favorite-btn');
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

    function initAlertExpand() {
        document.querySelectorAll('.alert-expand-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var card = btn.closest('.alert-card');
                if (card) {
                    var expanded = card.getAttribute('data-expanded') === 'true';
                    card.setAttribute('data-expanded', !expanded);
                    btn.textContent = expanded ? 'Show details' : 'Hide details';
                }
            });
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
        initAlertExpand: initAlertExpand,
        initRemoveFavorite: initRemoveFavorite,
        showLoading: showLoading,
        hideLoading: hideLoading,
    };
})();

document.addEventListener('DOMContentLoaded', ClearerWeather.init);
