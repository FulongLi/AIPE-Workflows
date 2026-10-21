/* No runtime dependencies; works from file:// and any static host. */
document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));

// A video slot stays a clearly labelled poster until the author supplies a source.
document.querySelectorAll('[data-video-slot]').forEach(figure => {
  const video = figure.querySelector('video');
  const placeholder = figure.querySelector('.media-placeholder');
  if (video?.querySelector('source[src]') || video?.getAttribute('src')) {
    video.hidden = false;
    if (placeholder) placeholder.hidden = true;
    video.addEventListener('error', () => {
      video.hidden = true;
      if (placeholder) {
        placeholder.hidden = false;
        const label = placeholder.querySelector('span');
        if (label) label.textContent = document.documentElement.lang.startsWith('zh')
          ? '视频暂时无法加载，请使用下方链接'
          : 'Video unavailable. Please use the link below.';
      }
    });
  }
});

const slides = [...document.querySelectorAll('.slide')];
if (slides.length) {
  let current = 0;
  const enter = document.querySelector('[data-present]');
  const exit = document.querySelector('[data-exit]');
  const previous = document.querySelector('[data-previous]');
  const next = document.querySelector('[data-next]');
  const counter = document.querySelector('[data-counter]');
  function show(index) {
    current = Math.max(0, Math.min(slides.length - 1, index));
    slides.forEach((slide, i) => {
      slide.classList.toggle('active', i === current);
      slide.inert = document.body.classList.contains('presenting') && i !== current;
    });
    counter.textContent = `${current + 1} / ${slides.length}`;
    previous.disabled = current === 0;
    next.disabled = current === slides.length - 1;
  }
  function leave() {
    document.body.classList.remove('presenting');
    slides.forEach(slide => { slide.inert = false; });
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    slides[current].scrollIntoView({ behavior: 'instant', block: 'start' });
    enter.focus({ preventScroll: true });
  }
  enter.addEventListener('click', () => {
    const nearest = slides.map(slide => Math.abs(slide.getBoundingClientRect().top - 100));
    current = nearest.indexOf(Math.min(...nearest));
    document.body.classList.add('presenting');
    show(current);
    exit.focus();
    document.documentElement.requestFullscreen?.().catch(() => {});
  });
  exit.addEventListener('click', leave);
  previous.addEventListener('click', () => show(current - 1));
  next.addEventListener('click', () => show(current + 1));
  document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('presenting') || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable) return;
    if (event.key === 'Escape') { event.preventDefault(); leave(); }
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) {
      // Allow focused navigation buttons to retain normal Space-key activation.
      if (event.key === ' ' && event.target.closest('button, a')) return;
      event.preventDefault(); show(current + 1);
    }
    if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) { event.preventDefault(); show(current - 1); }
    if (event.key === 'Home') { event.preventDefault(); show(0); }
    if (event.key === 'End') { event.preventDefault(); show(slides.length - 1); }
  });
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && document.body.classList.contains('presenting')) leave();
  });
  // Print CSS always includes every slide, including from presentation mode.
  window.addEventListener('beforeprint', () => slides.forEach(slide => { slide.inert = false; }));
  window.addEventListener('afterprint', () => show(current));
  show(0);
}
