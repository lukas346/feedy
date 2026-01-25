/**
 * Shared utility functions for Feedy UI
 */

/**
 * Set toggle value for mark-as-read button before HTMX request
 * @param {HTMLButtonElement} btn - Button element with data-is-read attribute
 */
function setToggleValue(btn) {
    // The actual value is set via htmx:configRequest event listener in the list partials
    // This function exists for compatibility with hx-on::before-request
}

/**
 * Set button loading state with spinner
 * @param {HTMLButtonElement} btn - Button element with .btn-text and .btn-spinner children
 * @param {boolean} loading - Whether to show loading state
 */
function setButtonLoading(btn, loading) {
    if (!btn) return;
    var textEl = btn.querySelector('.btn-text');
    var spinnerEl = btn.querySelector('.btn-spinner');
    if (loading) {
        btn.disabled = true;
        if (textEl) textEl.classList.add('hidden');
        if (spinnerEl) spinnerEl.classList.remove('hidden');
    } else {
        btn.disabled = false;
        if (textEl) textEl.classList.remove('hidden');
        if (spinnerEl) spinnerEl.classList.add('hidden');
    }
}

/**
 * Show full-page loading overlay
 * @param {string} text - Main text to display
 * @param {string} subtext - Secondary text to display
 */
function showLoadingOverlay(text, subtext) {
    var overlay = document.getElementById('loading-overlay');
    var textEl = document.getElementById('loading-overlay-text');
    var subtextEl = document.getElementById('loading-overlay-subtext');
    if (overlay) {
        if (textEl) textEl.textContent = text || '';
        if (subtextEl) subtextEl.textContent = subtext || '';
        overlay.classList.remove('hidden');
    }
}

/**
 * Hide full-page loading overlay
 */
function hideLoadingOverlay() {
    var overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
    }
}

/**
 * Animate item removal with fade, slide, and collapse
 * @param {HTMLElement} element - Element to animate out
 * @param {Function} callback - Function to call after animation completes
 */
function animateItemOut(element, callback) {
    element.style.transition = 'all 0.3s ease-out';
    element.style.opacity = '0';
    element.style.transform = 'translateX(-10px)';
    setTimeout(function() {
        element.style.height = element.offsetHeight + 'px';
        element.style.overflow = 'hidden';
        setTimeout(function() {
            element.style.height = '0';
            element.style.marginBottom = '0';
            element.style.padding = '0';
            setTimeout(function() {
                if (callback) callback();
            }, 200);
        }, 50);
    }, 200);
}

/**
 * Show success flash animation on element
 * @param {HTMLElement} element - Element to flash
 */
function showSuccessFlash(element) {
    var flash = document.createElement('div');
    flash.className = 'absolute inset-0 bg-emerald-500/10 rounded-xl pointer-events-none';
    flash.style.transition = 'opacity 0.5s ease-out';
    element.style.position = 'relative';
    element.appendChild(flash);
    setTimeout(function() {
        flash.style.opacity = '0';
        setTimeout(function() { flash.remove(); }, 500);
    }, 100);
}
