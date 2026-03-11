/**
 * Clearer Weather - Vanilla JS
 * Theme toggle, loading state, favorites, auto-refresh
 */

const ClearerWeather = (function () {
    const loadingId = 'loading-overlay';

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
            form.addEventListener('submit', function () {
                const input = form.querySelector('input[name="location"]');
                if (input && input.value.trim()) {
                    showLoading();
                }
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
                            btn.textContent = '★ Added to Favorites';
                            btn.disabled = true;
                        }
                    })
                    .catch(function () {});
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
        showLoading: showLoading,
        hideLoading: hideLoading,
    };
})();

document.addEventListener('DOMContentLoaded', ClearerWeather.init);
