/**
 * Global EPUB article selection and download handling.
 */

var EPUBSelection = (function() {
    var STORAGE_KEY = 'feedy.epubSelection';

    function getSelection() {
        try {
            var parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
            if (!Array.isArray(parsed)) return [];
            return parsed.filter(function(id) {
                return typeof id === 'string' && id.length > 0;
            });
        } catch (error) {
            return [];
        }
    }

    function saveSelection(ids) {
        var unique = [];
        ids.forEach(function(id) {
            if (unique.indexOf(id) === -1) unique.push(id);
        });
        localStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
    }

    function addArticle(id) {
        var ids = getSelection();
        if (ids.indexOf(id) === -1) {
            ids.push(id);
            saveSelection(ids);
        }
        updateUI();
    }

    function removeArticle(id) {
        saveSelection(getSelection().filter(function(selectedId) {
            return selectedId !== id;
        }));
        updateUI();
    }

    function toggleArticle(id) {
        if (getSelection().indexOf(id) === -1) {
            addArticle(id);
        } else {
            removeArticle(id);
        }
    }

    function clearSelection() {
        localStorage.removeItem(STORAGE_KEY);
        updateUI();
    }

    function getBar() {
        return document.getElementById('epub-selection-bar');
    }

    function updateUI() {
        var ids = getSelection();
        var bar = getBar();
        var count = ids.length;

        if (bar) {
            bar.classList.toggle('hidden', count === 0);
            document.body.style.paddingBottom = count > 0 ? '6rem' : '';

            var countEl = document.getElementById('epub-selection-count');
            if (countEl) {
                var template = countEl.dataset.template || '{count} selected';
                countEl.textContent = template.replace('{count}', String(count));
            }
        }

        document.querySelectorAll('[data-epub-select]').forEach(function(checkbox) {
            var id = checkbox.getAttribute('data-article-id') || checkbox.value;
            checkbox.checked = ids.indexOf(id) !== -1;
        });

        document.querySelectorAll('[data-epub-add]').forEach(function(button) {
            var id = button.getAttribute('data-article-id');
            var selected = ids.indexOf(id) !== -1;
            var label = selected ? button.dataset.removeText : button.dataset.addText;
            var textEl = button.querySelector('[data-epub-add-text]');
            if (textEl) {
                textEl.textContent = label;
            }
            button.title = label;
            button.setAttribute('aria-label', label);
            button.setAttribute('aria-pressed', selected ? 'true' : 'false');
            button.classList.toggle('text-rose-500', selected);
            button.classList.toggle('dark:text-rose-400', selected);
            if (button.classList.contains('epub-add-btn')) {
                button.classList.toggle('bg-rose-50', selected);
                button.classList.toggle('dark:bg-rose-900/20', selected);
                button.classList.toggle('border-rose-300', selected);
                button.classList.toggle('dark:border-rose-500', selected);
                button.classList.toggle('border-zinc-300', !selected);
                button.classList.toggle('dark:border-zinc-600', !selected);
                button.classList.toggle('text-zinc-500', !selected);
                button.classList.toggle('dark:text-zinc-400', !selected);
            }
        });
    }

    function showError(message, title) {
        if (window.Modal && typeof window.Modal.error === 'function') {
            return window.Modal.error(message, title);
        }
        window.alert(title + ': ' + message);
        return Promise.resolve();
    }

    function setDownloadLoading(button, loading) {
        if (!button) return;
        button.disabled = loading;
        button.setAttribute('aria-busy', loading ? 'true' : 'false');

        var textEl = button.querySelector('.btn-text');
        var spinnerEl = button.querySelector('.btn-spinner');
        if (textEl) textEl.classList.remove('hidden');
        if (spinnerEl) spinnerEl.classList.toggle('hidden', !loading);
    }

    async function responseErrorMessage(response, fallback) {
        var contentType = response.headers.get('content-type') || '';
        if (contentType.indexOf('application/json') !== -1) {
            try {
                var data = await response.json();
                if (typeof data.detail === 'string') return data.detail;
                if (Array.isArray(data.detail)) {
                    return data.detail.map(function(item) {
                        return item.msg || JSON.stringify(item);
                    }).join('\n');
                }
            } catch (error) {
                return fallback;
            }
        }

        try {
            var text = await response.text();
            return text || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function filenameFromDisposition(header) {
        if (!header) return null;
        var match = header.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
        if (!match) return null;
        return decodeURIComponent(match[1] || match[2]);
    }

    function localDateString() {
        var now = new Date();
        var year = String(now.getFullYear());
        var month = String(now.getMonth() + 1).padStart(2, '0');
        var day = String(now.getDate()).padStart(2, '0');
        return year + '-' + month + '-' + day;
    }

    function defaultFilename() {
        return 'feedy-' + localDateString() + '.epub';
    }

    function saveBlob(blob, filename) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(function() {
            URL.revokeObjectURL(url);
        }, 1000);
    }

    function refreshElement(elementId) {
        var element = document.getElementById(elementId);
        if (!element || !window.htmx) return;

        var url = element.getAttribute('hx-get');
        if (!url) return;

        window.htmx.ajax('GET', url, {
            target: '#' + elementId,
            swap: 'innerHTML'
        });
    }

    function refreshCurrentLists() {
        refreshElement('feeds-list');
        refreshElement('articles-list');
        refreshElement('favorites-list');
    }

    async function downloadSelected() {
        var bar = getBar();
        var ids = getSelection();
        var errorTitle = bar ? bar.dataset.errorTitle : 'Error';
        var noSelection = bar ? bar.dataset.noSelection : 'Select articles first.';
        var exportFailed = bar ? bar.dataset.exportFailed : 'Failed to export EPUB.';

        if (ids.length === 0) {
            await showError(noSelection, errorTitle);
            return;
        }

        var button = document.getElementById('epub-download-btn');
        setDownloadLoading(button, true);

        try {
            var endpoint = bar ? bar.dataset.endpoint : '/api/epub/export';
            var response = await fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({article_ids: ids})
            });

            if (!response.ok) {
                var message = await responseErrorMessage(response, exportFailed);
                await showError(message, errorTitle);
                return;
            }

            var blob = await response.blob();
            var filename = filenameFromDisposition(
                response.headers.get('content-disposition')
            ) || defaultFilename();
            saveBlob(blob, filename);
            clearSelection();
            refreshCurrentLists();
        } catch (error) {
            await showError(exportFailed, errorTitle);
        } finally {
            setDownloadLoading(button, false);
        }
    }

    function handleChange(event) {
        var target = event.target;
        if (!target || !target.matches || !target.matches('[data-epub-select]')) {
            return;
        }

        var id = target.getAttribute('data-article-id') || target.value;
        if (!id) return;

        if (target.checked) {
            addArticle(id);
        } else {
            removeArticle(id);
        }
    }

    function handleClick(event) {
        var target = event.target;
        if (!target || !target.closest) return;

        var addButton = target.closest('[data-epub-add]');
        if (addButton) {
            event.preventDefault();
            event.stopPropagation();
            var articleId = addButton.getAttribute('data-article-id');
            if (articleId) toggleArticle(articleId);
            return;
        }

        var clearButton = target.closest('#epub-clear-btn');
        if (clearButton) {
            event.preventDefault();
            clearSelection();
            return;
        }

        var downloadButton = target.closest('#epub-download-btn');
        if (downloadButton) {
            event.preventDefault();
            downloadSelected();
        }
    }

    function init() {
        document.body.addEventListener('change', handleChange);
        document.body.addEventListener('click', handleClick, true);
        document.body.addEventListener('htmx:afterSwap', updateUI);
        updateUI();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        add: addArticle,
        clear: clearSelection,
        remove: removeArticle,
        update: updateUI
    };
})();
