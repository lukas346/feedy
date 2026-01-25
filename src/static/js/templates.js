/**
 * HTML templates for JavaScript components
 * Centralizes inline HTML that was previously injected via innerHTML
 */

var Templates = (function() {
    /**
     * Get spinner HTML
     * @param {string} [size='h-4 w-4'] - Tailwind size classes
     * @returns {string} Spinner HTML
     */
    function spinner(size) {
        size = size || 'h-4 w-4';
        return '<div class="spinner ' + size + '"></div>';
    }

    /**
     * Create a spinner element
     * @param {string} [size='h-4 w-4'] - Tailwind size classes
     * @returns {HTMLElement} Spinner element
     */
    function createSpinner(size) {
        var div = document.createElement('div');
        div.className = 'spinner ' + (size || 'h-4 w-4');
        return div;
    }

    return {
        spinner: spinner,
        createSpinner: createSpinner
    };
})();
