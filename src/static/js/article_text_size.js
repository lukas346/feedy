/**
 * Global article text size preference.
 */

var ArticleTextSize = (function() {
    var STORAGE_KEY = 'feedy.articleTextSize';
    var DEFAULT_SIZE = 'medium';
    var SIZES = ['small', 'medium', 'large', 'xlarge'];

    function isValidSize(size) {
        return SIZES.indexOf(size) !== -1;
    }

    function getSavedSize() {
        try {
            var size = localStorage.getItem(STORAGE_KEY);
            return isValidSize(size) ? size : null;
        } catch (error) {
            return null;
        }
    }

    function currentSize() {
        return getSavedSize() || DEFAULT_SIZE;
    }

    function applySize(size) {
        if (!isValidSize(size)) return;
        document.documentElement.setAttribute('data-article-text-size', size);
    }

    function saveSize(size) {
        if (!isValidSize(size)) return;
        try {
            localStorage.setItem(STORAGE_KEY, size);
        } catch (error) {
            return;
        }
        applySize(size);
        updateButtons(size);
    }

    function clearSize() {
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (error) {
        }
        document.documentElement.removeAttribute('data-article-text-size');
        updateButtons(DEFAULT_SIZE);
    }

    function updateButtons(size) {
        document.querySelectorAll('[data-article-text-size-btn]').forEach(function(button) {
            var buttonSize = button.getAttribute('data-article-text-size-value');
            var active = buttonSize === size;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function handleClick(event) {
        var target = event.target;
        if (!target || !target.closest) return;

        var logoutLink = target.closest('a[href="/logout"]');
        if (logoutLink) {
            clearSize();
            return;
        }

        var button = target.closest('[data-article-text-size-btn]');
        if (!button) return;

        event.preventDefault();
        saveSize(button.getAttribute('data-article-text-size-value'));
    }

    function clearAfterLogoutRedirect() {
        var params = new URLSearchParams(window.location.search);
        if (params.get('logged_out') !== '1') return;

        clearSize();
        params.delete('logged_out');

        var query = params.toString();
        var url = window.location.pathname + (query ? '?' + query : '') + window.location.hash;
        window.history.replaceState({}, document.title, url);
    }

    function init() {
        var size = getSavedSize();
        if (size) {
            applySize(size);
        }
        updateButtons(currentSize());
        clearAfterLogoutRedirect();
        document.body.addEventListener('click', handleClick, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        apply: saveSize,
        clear: clearSize
    };
})();
