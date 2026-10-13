// Site behaviour: mobile nav, header scroll state, reveals, forms. No dependencies.
(() => {
  const doc = document.documentElement;
  doc.classList.add('js');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ------------------------------------------------------------ mobile nav
  const toggle = document.querySelector('[data-nav-toggle]');
  if (toggle) {
    const setOpen = open => {
      toggle.setAttribute('aria-expanded', String(open));
      doc.classList.toggle('nav-open', open);
    };
    toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && doc.classList.contains('nav-open')) { setOpen(false); toggle.focus(); }
    });
  }

  // ------------------------------------------------------------ header state
  // Fixed-height bar; .is-scrolled is styled with transform/opacity only.
  const header = document.querySelector('[data-header]');
  if (header) {
    let queued = false;
    const update = () => { header.classList.toggle('is-scrolled', window.scrollY > 40); queued = false; };
    window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  // ------------------------------------------------------------ reveals
  const reveals = document.querySelectorAll('.reveal');
  if (reveals.length && !reduceMotion && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-in'); io.unobserve(entry.target); }
    }), { rootMargin: '0px 0px -10% 0px' });
    reveals.forEach(el => io.observe(el));
  } else {
    reveals.forEach(el => el.classList.add('is-in'));
  }

  // ------------------------------------------------------------ parallax
  // Default speed: 50% of scroll (the user's standard, Macz 2026-10-07). Mark a full-bleed photo
  // <div class="media"><img data-parallax ...></div>; it moves by half its frame's offset from the
  // viewport top (transform: translateY only). CSS sizes it so the frame never shows a gap.
  // If SPEED changes, change the 50% / 50lvh in the CSS height formula to match.
  const SPEED = 0.5;
  const layers = [...document.querySelectorAll('[data-parallax]')];
  if (layers.length && !reduceMotion) {
    let ticking = false;
    const move = () => {
      const vh = window.innerHeight;
      layers.forEach(img => {
        const frame = img.parentElement.getBoundingClientRect();
        if (frame.bottom < -100 || frame.top > vh + 100) return;
        img.style.transform = `translate3d(0, ${(-frame.top * (1 - SPEED)).toFixed(1)}px, 0)`;
      });
      ticking = false;
    };
    const queue = () => { if (!ticking) { ticking = true; requestAnimationFrame(move); } };
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue);
    move();
  }

  // ------------------------------------------------------------ mobile nav: close after jumping to a section
  document.querySelectorAll('#site-nav a').forEach(a => a.addEventListener('click', () => {
    if (doc.classList.contains('nav-open')) toggle?.click();
  }));

  // ------------------------------------------------------------ work screens: "Scroll the page"
  // Same transform-only scroll-through as hover, for touch and keyboard users. Press again to go back up.
  document.querySelectorAll('[data-play]').forEach(btn => {
    const work = btn.closest('.work');
    const label = btn.firstChild;
    btn.hidden = false;
    btn.addEventListener('click', () => {
      const on = !work.classList.contains('is-playing');
      work.classList.toggle('is-playing', on);
      btn.setAttribute('aria-pressed', String(on));
      label.textContent = on ? 'Back to top' : 'Scroll the page';
    });
  });

  // ------------------------------------------------------------ copy email
  // The button stays hidden without JS (the email link above it still works).
  document.querySelectorAll('[data-copy]').forEach(btn => {
    if (!navigator.clipboard) return;
    btn.hidden = false;
    const status = btn.parentElement.querySelector('[data-copy-status]');
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        if (status) status.textContent = 'Copied to your clipboard.';
      } catch {
        if (status) status.textContent = 'Couldn’t copy. Select the address above instead.';
      }
    });
  });

  // ------------------------------------------------------------ poster lightbox
  // Each poster links to its large file, so without JS (or without <dialog>) the link still opens it.
  const dialog = document.querySelector('[data-lightbox-dialog]');
  if (dialog && typeof dialog.showModal === 'function') {
    const frame = dialog.querySelector('[data-lightbox-frame]');
    const caption = dialog.querySelector('[data-lightbox-caption]');
    let opener = null;
    document.querySelectorAll('a[data-lightbox]').forEach(link => link.addEventListener('click', e => {
      e.preventDefault();
      opener = link;
      const img = new Image();
      img.src = link.href;
      img.alt = link.querySelector('img')?.alt || '';
      frame.replaceChildren(img);
      caption.textContent = link.dataset.lightbox;
      dialog.showModal();
    }));
    // Click on the backdrop (outside the sheet) closes it; Escape and the Close button are native.
    dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => { frame.replaceChildren(); opener?.focus(); });
  }

  // ------------------------------------------------------------ forms
  const clean = v => (v == null ? '' : String(v).trim());
  const isBlank = v => !v || v === 'null' || v === 'undefined';
  const params = new URLSearchParams(location.search);

  document.querySelectorAll('[data-form]').forEach(form => {
    // URL prefill, guarded so a missing param never produces "the null"
    form.querySelectorAll('[data-prefill]').forEach(field => {
      const value = clean(params.get(field.dataset.prefill));
      if (isBlank(value)) return;
      if (field.tagName === 'SELECT') {
        if ([...field.options].some(o => o.value === value)) field.value = value;
      } else {
        const tpl = field.dataset.prefillTemplate;
        field.value = tpl ? tpl.replace('{value}', value) : value;
      }
    });

    // Phone becomes required when the visitor prefers a call or a text
    const pref = form.querySelector('[data-requires-phone]');
    const phone = form.querySelector('input[type="tel"]');
    const syncPhone = () => {
      if (!pref || !phone) return;
      const needs = pref.dataset.requiresPhone.split(',').map(s => s.trim()).includes(pref.value);
      phone.required = needs;
      phone.closest('.field')?.classList.toggle('is-required', needs);
    };
    pref?.addEventListener('change', syncPhone);
    syncPhone();

    const status = form.querySelector('[data-form-status]');
    const say = (msg, kind) => { if (status) { status.textContent = msg; status.dataset.kind = kind; } };
    const emptyFields = () => [...form.elements].filter(el =>
      el.name && !el.disabled && el.type !== 'submit' && el.type !== 'button' && clean(el.value) === '');

    form.addEventListener('submit', async e => {
      syncPhone();
      if (!form.checkValidity()) { e.preventDefault(); form.reportValidity(); return; }

      // data-native: let the browser post the form, but don't send fields left empty
      if ('native' in form.dataset) {
        emptyFields().forEach(el => { el.disabled = true; el.dataset.wasEmpty = ''; });
        return;
      }

      e.preventDefault();
      const endpoint = form.dataset.endpoint;
      if (!endpoint) {
        say('This form isn’t connected yet (preview build). Please call or email us instead.', 'error');
        return;
      }
      const data = new FormData(form);
      emptyFields().forEach(el => data.delete(el.name));
      const button = form.querySelector('[type="submit"]');
      if (button) button.disabled = true;
      say('Sending…', 'pending');
      try {
        const res = await fetch(endpoint, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
        if (!res.ok) throw new Error(String(res.status));
        form.reset();
        syncPhone();
        say(form.dataset.success || 'Thanks, we got your message and will get back to you soon.', 'ok');
      } catch {
        say('Something went wrong sending the form. Please call us instead.', 'error');
      } finally {
        if (button) button.disabled = false;
      }
    });
  });

  // Back/forward cache: re-enable fields disabled for a native submit
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('[data-form] [data-was-empty]').forEach(el => {
      el.disabled = false;
      delete el.dataset.wasEmpty;
    });
  });
})();
