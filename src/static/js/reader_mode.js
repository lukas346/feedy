/**
 * Per-browser article link mode preference.
 */

var ReaderMode = (function() {
    var STORAGE_KEY = 'feedy.readerMode';
    var DEFAULT_MODE = 'reader';
    var MODES = ['reader', 'rss'];
    var REFRESHABLE_LIST_IDS = ['feeds-list', 'articles-list'];
    var REFRESH_ANIMATION_CLASSES = ['animate-slide-up', 'animate-fade-in'];

    var ACTIVE_CLASSES = [
        'border-blue-500',
        'bg-blue-50',
        'dark:bg-blue-900/20',
        'text-blue-700',
        'dark:text-blue-300'
    ];
    var INACTIVE_CLASSES = [
        'border-zinc-200',
        'dark:border-zinc-700',
        'hover:border-blue-400',
        'dark:hover:border-blue-500',
        'text-zinc-700',
        'dark:text-zinc-300'
    ];

    function isValidMode(mode) {
        return MODES.indexOf(mode) !== -1;
    }

    function getSavedMode() {
        try {
            var mode = localStorage.getItem(STORAGE_KEY);
            return isValidMode(mode) ? mode : null;
        } catch (error) {
            return null;
        }
    }

    function currentMode() {
        return getSavedMode() || DEFAULT_MODE;
    }

    function articleUrl(link, mode) {
        var attribute = mode === 'rss' ? 'data-original-url' : 'data-reader-url';
        return link.getAttribute(attribute) || link.getAttribute('data-reader-url');
    }

    function updateArticleLinks(mode) {
        document.querySelectorAll('[data-article-link]').forEach(function(link) {
            var url = articleUrl(link, mode);
            if (!url) return;

            link.setAttribute('data-active-url', url);
            if (link.tagName === 'A') {
                link.setAttribute('href', url);
            }
        });
    }

    function toggleClasses(element, classes, enabled) {
        classes.forEach(function(className) {
            element.classList.toggle(className, enabled);
        });
    }

    function updateButtons(mode) {
        document.querySelectorAll('[data-reader-mode-btn]').forEach(function(button) {
            var active = button.getAttribute('data-reader-mode-value') === mode;
            toggleClasses(button, ACTIVE_CLASSES, active);
            toggleClasses(button, INACTIVE_CLASSES, !active);
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function applyMode(mode) {
        if (!isValidMode(mode)) return;

        document.documentElement.setAttribute('data-reader-mode', mode);
        updateButtons(mode);
        updateArticleLinks(mode);
    }

    function saveMode(mode) {
        if (!isValidMode(mode)) return;

        try {
            localStorage.setItem(STORAGE_KEY, mode);
        } catch (error) {
            return;
        }
        applyMode(mode);
    }

    function isNestedInteractive(target, articleLink) {
        var interactive = target.closest('button, input, select, textarea, label, [role="button"]');
        if (interactive && interactive !== articleLink) return true;

        var anchor = target.closest('a');
        return anchor && anchor !== articleLink;
    }

    function openUrl(url) {
        window.open(url, '_blank', 'noopener');
    }

    function refreshCurrentLists() {
        if (!window.htmx) return;

        REFRESHABLE_LIST_IDS.forEach(function(elementId) {
            var element = document.getElementById(elementId);
            if (!element) return;

            var url = element.getAttribute('hx-get');
            if (!url) return;

            element.dataset.readerModeRefresh = 'true';
            window.htmx.ajax('GET', url, {
                target: '#' + elementId,
                swap: 'innerHTML'
            });
        });
    }

    function suppressRefreshAnimations(target) {
        REFRESH_ANIMATION_CLASSES.forEach(function(className) {
            target.querySelectorAll('.' + className).forEach(function(element) {
                element.classList.remove(className);
            });
        });
    }

    function markButtonRead(button) {
        button.dataset.isRead = 'true';
        button.classList.remove(
            'border-zinc-300',
            'dark:border-zinc-600',
            'text-zinc-500',
            'dark:text-zinc-400'
        );
        button.classList.add(
            'bg-green-50',
            'dark:bg-green-900/20',
            'border-green-300',
            'dark:border-green-500',
            'text-green-600',
            'dark:text-green-400'
        );

        if (button.dataset.unreadText) {
            button.title = button.dataset.unreadText;
            button.setAttribute('aria-label', button.dataset.unreadText);
        }
    }

    function updateReadState(articleLink) {
        articleLink.dataset.isRead = 'true';

        var row = articleLink.closest('[id^="article-item-"], [id^="feed-article-"]');
        if (row) {
            row.classList.add('is-read');
            row.style.opacity = '0.6';
        } else {
            articleLink.classList.add('is-read');
            articleLink.style.opacity = '0.6';
        }

        var button = articleLink.querySelector('.mark-read-btn');
        if (button) markButtonRead(button);
    }

    function markArticleRead(articleLink) {
        if (articleLink.dataset.isRead === 'true') return;

        var articleId = articleLink.getAttribute('data-article-id');
        if (!articleId) return;

        updateReadState(articleLink);
        return fetch('/api/articles/' + encodeURIComponent(articleId) + '/read', {
            method: 'PATCH',
            credentials: 'same-origin',
            keepalive: true,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({is_read: true})
        }).catch(function() {
            return;
        });
    }

    function handleClick(event) {
        var target = event.target;
        if (!target || !target.closest) return;

        var modeButton = target.closest('[data-reader-mode-btn]');
        if (modeButton) {
            event.preventDefault();
            saveMode(modeButton.getAttribute('data-reader-mode-value'));
            return;
        }

        var articleLink = target.closest('[data-article-link]');
        if (!articleLink || isNestedInteractive(target, articleLink)) return;

        var mode = currentMode();
        var url = articleLink.getAttribute('data-active-url') || articleUrl(articleLink, mode);
        if (!url) return;

        event.preventDefault();
        event.stopPropagation();
        var readRequest = markArticleRead(articleLink);
        if (readRequest) {
            readRequest.then(refreshCurrentLists);
        } else {
            refreshCurrentLists();
        }
        openUrl(url);
    }

    function init() {
        applyMode(currentMode());
        document.body.addEventListener('click', handleClick, true);
        document.body.addEventListener('htmx:afterSwap', function(event) {
            var target = event.detail.target;
            if (target && target.dataset.readerModeRefresh === 'true') {
                suppressRefreshAnimations(target);
                delete target.dataset.readerModeRefresh;
            }
            applyMode(currentMode());
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        apply: saveMode,
        current: currentMode
    };
})();
