/**
 * Article favorite toggle handling for HTMX-loaded lists.
 */

var ArticleFavorites = (function() {
    var ACTIVE_CLASSES = [
        'bg-rose-50',
        'dark:bg-rose-900/20',
        'border-rose-300',
        'dark:border-rose-500',
        'text-rose-500',
        'dark:text-rose-400'
    ];
    var INACTIVE_CLASSES = [
        'border-zinc-300',
        'dark:border-zinc-600',
        'text-zinc-500',
        'dark:text-zinc-400'
    ];

    function toggleClasses(element, classes, enabled) {
        classes.forEach(function(className) {
            element.classList.toggle(className, enabled);
        });
    }

    function setButtonState(button, isFavorite) {
        var label = isFavorite ? button.dataset.removeText : button.dataset.addText;
        var icon = button.querySelector('svg');

        button.dataset.isFavorite = isFavorite ? 'true' : 'false';
        button.setAttribute('aria-pressed', isFavorite ? 'true' : 'false');
        button.setAttribute('aria-label', label);
        button.title = label;
        if (icon) icon.setAttribute('fill', isFavorite ? 'currentColor' : 'none');

        toggleClasses(button, ACTIVE_CLASSES, isFavorite);
        toggleClasses(button, INACTIVE_CLASSES, !isFavorite);
    }

    function updateArticleButtons(articleId, isFavorite) {
        document.querySelectorAll('[data-favorite-toggle][data-article-id="' + articleId + '"]').forEach(function(button) {
            setButtonState(button, isFavorite);
            button.disabled = false;
            button.removeAttribute('aria-busy');
        });
    }

    function setArticleButtonsBusy(articleId, busy) {
        document.querySelectorAll('[data-favorite-toggle][data-article-id="' + articleId + '"]').forEach(function(button) {
            button.disabled = busy;
            if (busy) {
                button.setAttribute('aria-busy', 'true');
            } else {
                button.removeAttribute('aria-busy');
            }
        });
    }

    function refreshFavoritesList(articleId) {
        var list = document.getElementById('favorites-list');
        if (!list) return;

        var url = list.getAttribute('hx-get');
        if (url && window.htmx) {
            window.htmx.ajax('GET', url, {
                target: '#favorites-list',
                swap: 'innerHTML'
            });
            return;
        }

        document.querySelectorAll('[data-favorite-list-row]').forEach(function(row) {
            if (row.getAttribute('data-article-id') === articleId) row.remove();
        });
    }

    async function toggleFavorite(button) {
        var articleId = button.getAttribute('data-article-id');
        if (!articleId) return;

        var isFavorite = button.dataset.isFavorite === 'true';
        var nextState = !isFavorite;

        setArticleButtonsBusy(articleId, true);
        try {
            var response = await fetch('/api/articles/' + encodeURIComponent(articleId) + '/favorite', {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({is_favorite: nextState})
            });

            if (!response.ok) return;
            updateArticleButtons(articleId, nextState);
            if (!nextState) refreshFavoritesList(articleId);
        } catch (error) {
            return;
        } finally {
            setArticleButtonsBusy(articleId, false);
        }
    }

    function handleClick(event) {
        var target = event.target;
        if (!target || !target.closest) return;

        var button = target.closest('[data-favorite-toggle]');
        if (!button) return;

        event.preventDefault();
        event.stopPropagation();
        toggleFavorite(button);
    }

    function init() {
        document.body.addEventListener('click', handleClick, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        update: updateArticleButtons
    };
})();
