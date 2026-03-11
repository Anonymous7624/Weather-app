/**
 * Clearcast Homepage — animations, theme toggle, scroll effects
 */

(function () {
    'use strict';

    function initTheme() {
        var btn = document.querySelector('.theme-toggle-hp');
        if (!btn) return;

        var stored = localStorage.getItem('clearcast-theme') || localStorage.getItem('clearer-weather-theme');
        if (stored === 'light' || (stored === null && window.matchMedia('(prefers-color-scheme: light)').matches)) {
            document.body.classList.remove('theme-dark');
            document.body.classList.add('theme-light');
        }

        updateToggleIcon();

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
            updateToggleIcon();
        });

        function updateToggleIcon() {
            btn.textContent = document.body.classList.contains('theme-light') ? '\u{1F319}' : '\u{2600}\u{FE0F}';
        }
    }

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
            threshold: 0.12,
            rootMargin: '0px 0px -40px 0px'
        });

        elements.forEach(function (el) {
            observer.observe(el);
        });
    }

    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(function (link) {
            link.addEventListener('click', function (e) {
                var target = document.querySelector(link.getAttribute('href'));
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTheme();
        initNavScroll();
        initScrollReveal();
        initSmoothScroll();
    });
})();
