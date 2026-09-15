const copyText = async (text) => {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  textarea.style.pointerEvents = 'none';
  document.body.appendChild(textarea);
  textarea.select();

  const copied = document.execCommand('copy');
  textarea.remove();

  if (!copied) {
    throw new Error('Clipboard copy was rejected');
  }
};

document.querySelectorAll('.copy-command').forEach((button) => {
  button.addEventListener('click', async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;

    const label = button.querySelector('.copy-text');
    const originalLabel = label ? label.textContent : '';

    try {
      await copyText(target.textContent.trim());
      button.classList.add('is-copied');
      button.setAttribute('aria-label', 'Install command copied');
      if (label) label.textContent = 'Copied';
    } catch (_) {
      button.classList.remove('is-copied');
      button.setAttribute('aria-label', 'Copy failed. Select the install command manually.');
      if (label) label.textContent = 'Select';

      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(target);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    window.setTimeout(() => {
      button.classList.remove('is-copied');
      button.setAttribute('aria-label', 'Copy install command');
      if (label) label.textContent = originalLabel;
    }, 1800);
  });
});
