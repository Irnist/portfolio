// GSAP motion for Ernest's portfolio (his request, 2026-10-10). Loaded after main.js and the self-hosted GSAP
// files (site_config.GSAP). Every animation on the site runs here; CSS only holds the states (open, scrolled,
// playing), so the page works and reads fully if this file never runs.
//
// Rules (CLAUDE.md + browser_qa.mjs motion pass):
// - Animate transform and opacity only (x, y, yPercent, scale, rotation, opacity), or a CSS variable that
//   styles.css turns into a transform or opacity (--hdr, --draw).
// - Everything sits inside the reduced-motion gate; reduced motion gets the plain, fully visible page.
// - The hero is never hidden at load (LCP). The signature moments live below the fold:
//   1. section headings: the words rise in one after another
//   2. process steps: an amber rule draws across each step in order, a project moving through its stages
//   3. print posters: dealt onto the page like prints landing on a table
// - Entrance moments replay each time they come back into view (the user's standard, 2026-10-09).
(() => {
  if (!window.gsap) return;
  const plugins = ['ScrollTrigger', 'SplitText'].map(n => window[n]).filter(Boolean);
  gsap.registerPlugin(...plugins);
  const mm = gsap.matchMedia();
  // Measure triggers in page order, whatever order this file creates them in (L-050)
  if (window.ScrollTrigger) ScrollTrigger.addEventListener('refreshInit', () => ScrollTrigger.sort());

  // A moment plays once its trigger is `at` of the way onto the screen from either edge, and resets only when
  // the trigger is fully off-screen, so the reset is never seen. Use on a paused tween or timeline.
  const inView = (trigger, at = 0.85) => {
    const check = self => {
      const anim = self.animation, r = self.trigger.getBoundingClientRect();
      if (anim && anim.paused() && r.top < innerHeight * at && r.bottom > innerHeight * (1 - at)) anim.restart(true);
    };
    const reset = self => self.animation && self.animation.pause(0);
    return { trigger, start: 'top bottom', end: 'bottom top', toggleActions: 'none none none none',
      onUpdate: check, onToggle: check, onRefresh: check, onLeave: reset, onLeaveBack: reset };
  };

  mm.add('(prefers-reduced-motion: no-preference)', () => {
    const cleanups = [];
    const listen = (target, type, fn, opts) => {
      target.addEventListener(type, fn, opts);
      cleanups.push(() => target.removeEventListener(type, fn, opts));
    };
    const watchClass = (el, onChange) => {
      const mo = new MutationObserver(() => onChange());
      mo.observe(el, { attributes: true, attributeFilter: ['class'] });
      cleanups.push(() => mo.disconnect());
    };

    // ---------------------------------------------------------- 1. section headings
    // <h2 data-gsap="split">: words rise and fade in. No line mask: a mask clips the long descenders of the
    // display serif (the "j" in "project"). SplitText keeps the full text as the heading's aria-label.
    if (window.SplitText && window.ScrollTrigger) {
      gsap.utils.toArray('[data-gsap="split"]').forEach(el => {
        const split = SplitText.create(el, {
          type: 'words', autoSplit: true,
          onSplit: self => gsap.from(self.words, {
            yPercent: 45, opacity: 0, duration: 0.7, ease: 'power3.out', stagger: 0.06,
            paused: true, scrollTrigger: inView(el, 0.88),
          }),
        });
        cleanups.push(() => split.revert());
      });
    }

    // ---------------------------------------------------------- 2. process steps
    // The amber rule on each step (li::after, scaleX(var(--draw))) draws in order, 1 to 4.
    const steps = document.querySelector('.steps');
    if (steps && window.ScrollTrigger) {
      const items = [...steps.children];
      gsap.fromTo(items, { '--draw': 0 }, {
        '--draw': 1, duration: 0.6, ease: 'power2.inOut', stagger: 0.3,
        paused: true, scrollTrigger: inView(steps, 0.8),
      });
      cleanups.push(() => items.forEach(li => li.style.removeProperty('--draw')));
    }

    // ---------------------------------------------------------- 3. print posters
    // Dealt onto the table: each sheet drops in with a slight tilt and settles square. Small angles around the
    // centre, so no corner reaches past the page gutter (L-046).
    const posters = document.querySelector('.poster-grid');
    if (posters && window.ScrollTrigger) {
      gsap.from(posters.children, {
        y: 56, rotation: i => [-2.5, 2, -1.5, 2.5, -2, 1.5][i % 6], opacity: 0, transformOrigin: '50% 50%',
        duration: 0.75, ease: 'power3.out', stagger: 0.09,
        paused: true, scrollTrigger: inView(posters, 0.85),
      });
    }

    // ---------------------------------------------------------- work cards rise in
    // Per card, so the lower rows of the concept grid play when they arrive; the second column a beat later.
    if (window.ScrollTrigger) {
      document.querySelectorAll('.work-grid').forEach(grid => [...grid.children].forEach((card, i) => {
        gsap.from(card, { y: 32, opacity: 0, duration: 0.7, delay: (i % 2) * 0.1, ease: 'power2.out',
          paused: true, scrollTrigger: inView(card, 0.9) });
      }));
    }

    // ---------------------------------------------------------- work screens: scroll through the site
    // Mouse hover, or the "Scroll the page" button (main.js toggles .is-playing), scrolls the screenshot to its
    // end in 7s and back up in under a second. CSS holds the same end states; the inline transform set here
    // overrides them while this runs, so the tween always starts from where the picture really is.
    document.querySelectorAll('.work').forEach(work => {
      const screen = work.querySelector('.browser__screen');
      const img = screen && screen.querySelector('img');
      if (!img) return;
      gsap.set(img, { y: 0 });
      let down = false;
      const go = on => {
        if (on === down) return;
        down = on;
        gsap.to(img, on
          ? { y: () => -(img.offsetHeight - screen.clientHeight), duration: 7, ease: 'sine.inOut', overwrite: true }
          : { y: 0, duration: 0.9, ease: 'power2.out', overwrite: true });
      };
      let hovered = false;
      const sync = () => go(hovered || work.classList.contains('is-playing'));
      listen(work, 'pointerenter', e => { if (e.pointerType === 'mouse') { hovered = true; sync(); } });
      listen(work, 'pointerleave', e => { if (e.pointerType === 'mouse') { hovered = false; sync(); } });
      watchClass(work, sync);
      cleanups.push(() => { gsap.killTweensOf(img); gsap.set(img, { clearProps: 'transform' }); });
    });

    // ---------------------------------------------------------- header
    // The backdrop fades in (--hdr, read by ::before) and the logo eases down once the page scrolls past 40px,
    // the same point main.js sets .is-scrolled.
    const header = document.querySelector('[data-header]');
    if (header && window.ScrollTrigger) {
      const brand = header.querySelector('.brand');
      const scrolled = (on, duration = 0.25) => {
        gsap.to(header, { '--hdr': on ? 1 : 0, duration, ease: 'power2.out', overwrite: 'auto' });
        if (brand) gsap.to(brand, { scale: on ? 0.95 : 1, duration, ease: 'power2.out', overwrite: 'auto' });
      };
      const st = ScrollTrigger.create({ start: 40, end: 'max', onToggle: self => scrolled(self.isActive) });
      scrolled(st.isActive, 0);
      cleanups.push(() => { header.style.removeProperty('--hdr'); if (brand) gsap.set(brand, { clearProps: 'transform' }); });
    }

    // ---------------------------------------------------------- mobile menu
    // Drops in on open, lifts away on close (main.js toggles .nav-open on <html>)
    const doc = document.documentElement, nav = document.querySelector('.site-nav');
    if (nav) {
      let open = doc.classList.contains('nav-open');
      watchClass(doc, () => {
        const now = doc.classList.contains('nav-open');
        if (now === open) return;
        open = now;
        if (getComputedStyle(nav).position !== 'fixed') return;  // desktop: the nav is inline, nothing to animate
        gsap.fromTo(nav, { autoAlpha: now ? 0 : 1, y: now ? -8 : 0 }, { autoAlpha: now ? 1 : 0, y: now ? 0 : -8,
          duration: 0.2, ease: now ? 'power2.out' : 'power2.in', overwrite: true, clearProps: 'opacity,visibility,transform' });
      });
    }

    return () => cleanups.forEach(fn => fn());
  });

  // Late images and fonts change heights after the triggers were measured
  if (window.ScrollTrigger) window.addEventListener('load', () => ScrollTrigger.refresh());
})();
