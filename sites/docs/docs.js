(() => {
  'use strict';

  async function copyCommand(ev) {
    const target = ev.currentTarget.getAttribute('data-copy-target');
    const source = target ? document.getElementById(target) : null;
    if (!source) return;
    const text = source.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      ev.currentTarget.textContent = 'Copied';
    } catch (err) {
      ev.currentTarget.textContent = 'Select text to copy';
    }
    window.setTimeout(() => { ev.currentTarget.textContent = ev.currentTarget.dataset.originalLabel || 'Copy'; }, 1600);
  }

  function bindCopyButtons() {
    document.querySelectorAll('[data-copy-target]').forEach((button) => {
      button.dataset.originalLabel = button.textContent;
      button.addEventListener('click', copyCommand);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindCopyButtons);
  } else {
    bindCopyButtons();
  }
})();
