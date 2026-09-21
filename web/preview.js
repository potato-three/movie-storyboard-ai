// Gradio HTML's constant template keeps this stage alive across value updates.
// Payloads are JSON, and all captions use textContent (never user-supplied HTML).
const mount = element.querySelector('.sb-preview-mount');
const shell = document.createElement('div');
shell.innerHTML = '<div class="sb-stage"><div class="sb-placeholder">开始提取后，这里将平滑预览已处理的镜头</div><img class="sb-layer" alt=""><img class="sb-layer" alt=""></div><div class="sb-caption" aria-live="polite"></div><div class="sb-note"></div>';
mount.appendChild(shell);
const stage = shell.querySelector('.sb-stage');
const layers = [...shell.querySelectorAll('.sb-layer')];
layers.forEach(layer => layer.setAttribute('aria-hidden', 'true'));
const caption = shell.querySelector('.sb-caption');
const note = shell.querySelector('.sb-note');
const placeholder = shell.querySelector('.sb-placeholder');
let active = -1;
let pending = null;
let busy = false;
let timer = null;
let epoch = 0;
let displayed = null;
let lastDisplay = -Infinity;
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

function schedule() {
  if (busy || !pending || !element.isConnected) return;
  clearTimeout(timer);
  const waitMs = pending.automatic ? Math.max(0, 1000 - (performance.now() - lastDisplay)) : 0;
  timer = setTimeout(pump, waitMs);
}

async function pump() {
  if (busy || !pending || !element.isConnected) return;
  const item = pending;
  pending = null;
  if (item.id === displayed) { schedule(); return; }
  busy = true;
  const generation = epoch;
  const nextIndex = active === 0 ? 1 : 0;
  const incoming = layers[nextIndex];
  const outgoing = active < 0 ? null : layers[active];
  let animations = [];
  let timeout;
  try {
    // Only the hidden layer gets a new src; the visible frame is never cleared.
    incoming.style.opacity = '0';
    incoming.style.transform = 'translateX(7%)';
    incoming.style.zIndex = '2';
    incoming.src = item.src;
    await Promise.race([
      incoming.decode(),
      new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('decode timeout')), 8000); })
    ]);
    clearTimeout(timeout);
    if (generation !== epoch || !element.isConnected) return;
    if (!incoming.naturalWidth) throw new Error('empty image');
    // If a newer request arrived while decoding, coalesce to the latest one.
    // Finish a successful decode first: continuous fast input cannot starve display.
    if (outgoing) outgoing.style.zIndex = '1';
    const duration = reducedMotion.matches ? 0 : 480;
    animations.push(incoming.animate([
      { opacity: 0, transform: 'translateX(7%)' },
      { opacity: 1, transform: 'translateX(0)' }
    ], { duration, easing: 'cubic-bezier(.22,.61,.36,1)', fill: 'forwards' }));
    if (outgoing) {
      // Keep the old layer opaque UNDER the fading-in image: this gives a
      // cross-dissolve without exposing the empty stage halfway through.
      animations.push(outgoing.animate([
        { transform: 'translateX(0)' }, { transform: 'translateX(-4%)' }
      ], { duration, easing: 'cubic-bezier(.22,.61,.36,1)', fill: 'forwards' }));
    }
    await Promise.all(animations.map(animation => animation.finished));
    incoming.style.opacity = '1';
    incoming.style.transform = 'translateX(0)';
    if (outgoing) {
      outgoing.style.opacity = '0';
      outgoing.setAttribute('aria-hidden', 'true');
    }
    incoming.setAttribute('aria-hidden', 'false');
    active = nextIndex;
    displayed = item.id;
    lastDisplay = performance.now();
    placeholder.hidden = true;
    // Caption and shot number are committed together with the decoded frame.
    incoming.alt = item.caption;
    caption.textContent = item.caption;
    stage.dataset.shot = String(item.no);
    stage.dataset.previewId = item.id;
    note.textContent = generation === epoch ? (item.automatic
      ? '自动预览约每秒更新；实际处理进度以上方状态为准。'
      : '手动浏览 · 所有原图和运动图均已保存。') : '正在扫描新视频；本次预览就绪前保留上一张画面。';
  } catch (error) {
    if (generation === epoch) note.textContent = '这一镜预览加载失败，保留上一张画面；可重新选择镜头。';
    incoming.style.opacity = '0';
  } finally {
    clearTimeout(timeout);
    animations.forEach(animation => animation.cancel());
    busy = false;
    schedule();
  }
}

function receive() {
  // Also tolerate a framework remount: reattach the same nodes, not blank images.
  const currentMount = element.querySelector('.sb-preview-mount');
  if (currentMount && shell.parentElement !== currentMount) currentMount.appendChild(shell);
  let item;
  try { item = JSON.parse(props.value || '{}'); } catch { return; }
  if (item.reset) {
    epoch += 1;
    pending = null;
    clearTimeout(timer);
    note.textContent = active < 0 ? '正在扫描视频，等待第一个镜头…' : '正在扫描新视频；本次预览就绪前保留上一张画面。';
    return;
  }
  if (item.error) { note.textContent = item.error; return; }
  if (!item.id || !item.src) return;
  // Selecting the current shot also cancels any still-pending different shot.
  pending = item;
  schedule();
}
watch('value', receive);
receive();

// Scope wheel protection to the shot slider, leaving page scroll elsewhere alone.
if (!window.__storyboardWheelGuard) {
  window.__storyboardWheelGuard = true;
  document.addEventListener('wheel', event => {
    if (event.target instanceof Element && event.target.matches('#shot_position input[type="range"]')) {
      event.preventDefault();
    }
  }, { passive: false, capture: true });
}
