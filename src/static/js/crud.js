/**
 * Generic CRUD operations module for Feedy
 * Provides reusable delete and action handlers with confirmation, animation, and error handling
 */

var CRUD = (function() {
    /**
     * Delete item with confirmation, loading state, animation, and list refresh
     * @param {Object} options
     * @param {string} options.endpoint - API endpoint to DELETE
     * @param {string} options.name - Display name for confirmation dialog
     * @param {HTMLElement} options.element - Button element that triggered the delete
     * @param {string|string[]} options.listIds - ID(s) of HTMX list(s) to refresh after delete
     * @param {Object} options.messages - i18n messages { confirm, title, error, errorTitle }
     * @param {string} options.messages.confirm - Confirmation message body
     * @param {string} options.messages.title - Confirmation dialog title
     * @param {string} options.messages.error - Error message on failure
     * @param {string} [options.messages.errorTitle] - Error dialog title (defaults to 'Error')
     * @param {string} [options.originalIcon] - SVG HTML to restore on button after error
     * @param {Function} [options.onSuccess] - Callback after successful delete
     */
    async function deleteItem(options) {
        var endpoint = options.endpoint;
        var name = options.name;
        var element = options.element;
        var listIds = Array.isArray(options.listIds) ? options.listIds : [options.listIds];
        var messages = options.messages || {};
        var originalIcon = options.originalIcon;
        var onSuccess = options.onSuccess;

        var confirmed = await Modal.confirm(
            messages.confirm || 'Are you sure?',
            (messages.title || 'Delete') + ' "' + name + '"?',
            { confirmText: messages.title || 'Delete', danger: true }
        );

        if (!confirmed) return false;

        var item = element ? element.closest('.settings-item') : null;

        if (item && element) {
            element.disabled = true;
            element.innerHTML = Templates.spinner();
        }

        var restoreButton = function() {
            if (element) {
                element.disabled = false;
                if (originalIcon) {
                    element.innerHTML = originalIcon;
                }
            }
        };

        try {
            var response = await fetch(endpoint, { method: 'DELETE' });

            if (response.ok) {
                if (item) {
                    animateItemOut(item, function() {
                        listIds.forEach(function(id) {
                            htmx.trigger('#' + id, 'refresh');
                        });
                        if (onSuccess) onSuccess();
                    });
                } else {
                    listIds.forEach(function(id) {
                        htmx.trigger('#' + id, 'refresh');
                    });
                    if (onSuccess) onSuccess();
                }
                return true;
            } else {
                restoreButton();
                await Modal.error(
                    messages.error || 'Failed to delete',
                    messages.errorTitle || 'Error'
                );
                return false;
            }
        } catch (error) {
            restoreButton();
            await Modal.error(
                messages.error || 'Failed to delete',
                messages.errorTitle || 'Error'
            );
            return false;
        }
    }

    /**
     * Perform async action with confirmation, loading overlay, and error handling
     * @param {Object} options
     * @param {string} options.endpoint - API endpoint
     * @param {string} [options.method='POST'] - HTTP method
     * @param {string} options.name - Display name for confirmation dialog
     * @param {HTMLElement} [options.element] - Button element that triggered the action
     * @param {Object} options.messages - i18n messages { confirm, title, error, errorTitle }
     * @param {boolean} [options.showOverlay] - Show loading overlay during action
     * @param {Object} [options.overlayText] - { text, subtext } for loading overlay
     * @param {string} [options.originalIcon] - SVG HTML to restore on button after completion
     * @param {Function} [options.onSuccess] - Callback with response on success
     * @param {string} [options.resultContainer] - ID of element to put response HTML into
     */
    async function action(options) {
        var endpoint = options.endpoint;
        var method = options.method || 'POST';
        var name = options.name;
        var element = options.element;
        var messages = options.messages || {};
        var showOverlay = options.showOverlay;
        var overlayText = options.overlayText || {};
        var originalIcon = options.originalIcon;
        var onSuccess = options.onSuccess;
        var resultContainer = options.resultContainer;

        var confirmed = await Modal.confirm(
            messages.confirm || 'Are you sure?',
            (messages.title || 'Confirm') + ' "' + name + '"?',
            { confirmText: messages.title || 'Confirm' }
        );

        if (!confirmed) return false;

        if (showOverlay) {
            showLoadingOverlay(overlayText.text || '', overlayText.subtext || '');
        }

        if (element && !showOverlay) {
            element.disabled = true;
            element.innerHTML = Templates.spinner();
        }

        var restoreButton = function() {
            if (element && originalIcon) {
                element.disabled = false;
                element.innerHTML = originalIcon;
            }
        };

        try {
            var response = await fetch(endpoint, { method: method });

            if (showOverlay) {
                hideLoadingOverlay();
            }

            if (response.ok) {
                if (resultContainer) {
                    var html = await response.text();
                    document.getElementById(resultContainer).innerHTML = html;
                }
                restoreButton();
                if (onSuccess) onSuccess(response);
                return true;
            } else {
                restoreButton();
                await Modal.error(
                    messages.error || 'Operation failed',
                    messages.errorTitle || 'Error'
                );
                return false;
            }
        } catch (error) {
            if (showOverlay) {
                hideLoadingOverlay();
            }
            restoreButton();
            await Modal.error(
                messages.error || 'Operation failed',
                messages.errorTitle || 'Error'
            );
            return false;
        }
    }

    return {
        delete: deleteItem,
        action: action
    };
})();
