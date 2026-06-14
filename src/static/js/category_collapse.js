/**
 * Category collapse handling for HTMX-loaded category cards.
 */

var CategoryCollapse = (function() {
    var STORAGE_PREFIX = 'feedy.collapsedCategories.';

    function storageKey(scope) {
        return STORAGE_PREFIX + scope;
    }

    function readCollapsed(scope) {
        try {
            var parsed = JSON.parse(localStorage.getItem(storageKey(scope)) || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    function writeCollapsed(scope, categoryIds) {
        try {
            localStorage.setItem(storageKey(scope), JSON.stringify(categoryIds));
        } catch (error) {
            return;
        }
    }

    function updateStoredState(scope, categoryId, collapsed) {
        var categoryIds = readCollapsed(scope).filter(function(value) {
            return value !== categoryId;
        });

        if (collapsed) categoryIds.push(categoryId);
        writeCollapsed(scope, categoryIds);
    }

    function setCardState(card, collapsed) {
        var panel = card.querySelector('[data-category-collapse-panel]');
        var button = card.querySelector('[data-category-collapse-toggle]');
        var icon = card.querySelector('[data-category-collapse-icon]');

        card.dataset.categoryCollapsed = collapsed ? 'true' : 'false';
        if (panel) panel.hidden = collapsed;

        if (button) {
            var label = collapsed ? button.dataset.expandText : button.dataset.collapseText;
            button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            if (label) {
                button.setAttribute('aria-label', label);
                button.title = label;
            }
        }

        if (icon) {
            icon.style.transition = 'transform 150ms ease';
            icon.style.transform = collapsed ? 'rotate(-90deg)' : 'rotate(0deg)';
        }
    }

    function apply(root) {
        var context = root && root.querySelectorAll ? root : document;
        var cards = [];

        if (context.matches && context.matches('[data-category-collapse-card]')) {
            cards.push(context);
        }

        context.querySelectorAll('[data-category-collapse-card]').forEach(function(card) {
            cards.push(card);
        });

        cards.forEach(function(card) {
            var scope = card.dataset.categoryCollapseScope || 'default';
            var categoryId = card.dataset.categoryCollapseId;
            if (!categoryId) return;

            setCardState(card, readCollapsed(scope).indexOf(categoryId) !== -1);
        });
    }

    function handleClick(event) {
        var target = event.target;
        if (!target || !target.closest) return;

        var button = target.closest('[data-category-collapse-toggle]');
        if (!button) return;

        var card = button.closest('[data-category-collapse-card]');
        if (!card) return;

        var scope = card.dataset.categoryCollapseScope || 'default';
        var categoryId = card.dataset.categoryCollapseId;
        if (!categoryId) return;

        event.preventDefault();
        event.stopPropagation();

        var collapsed = card.dataset.categoryCollapsed !== 'true';
        setCardState(card, collapsed);
        updateStoredState(scope, categoryId, collapsed);
    }

    function init() {
        document.body.addEventListener('click', handleClick, true);
        document.body.addEventListener('htmx:afterSwap', function(event) {
            apply(event.detail.target);
        });
        apply(document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        apply: apply
    };
})();
