# Visual review

These are the checks the scripts can't judge. Go through the `qa/shots/*-fold.png` screenshots (390 and 1440) for every page and skim the `-full` ones.

## Imagery
- [ ] Hero and banner photos: no text, license plates, logos or watermarks behind headlines at either width.
- [ ] Cut-out subjects (cars, products, people) are whole at every width. Fix the source crop; never hide a cut-off subject with oversize scaling or negative margins.
- [ ] Stock fits the locale and story (plates, architecture, climate, the right kind of vehicle or equipment).
- [ ] Real client photos hold the prominent spots and stay visible: no heavy overlay, no over-darkened hero.
- [ ] Each photo shows what the business actually sells (material, type, era). Wicker isn't poly; a modern Mustang isn't a classic build.
- [ ] Headline colour doesn't collide with the photo behind it (red text on a red car).
- [ ] Icons, dividers and small text on every dark or photo surface use the light ink, including at 390 where scrims thin out. The pixel check catches most cases; look at any it warns about (L-031/L-032).
- [ ] No third-party brand logos on any image (boards, signage, renders): they read as endorsements or an implied client list. Crop them out or skip the image (L-028).
- [ ] No near-duplicates: two shots from one shoot or of the same view count as a repeat unless they're shown together as one set (L-029).
- [ ] Callouts and annotations on photos sit on a part the photo actually shows. Check each one on a % grid over the full-size image before writing its copy (L-022).

## Identity
- [ ] Cover the logo: could this be any competitor's site? If yes, push the story harder.
- [ ] None of the template tells: an eyebrow over every heading, rows of icon-tile cards, a brand-name marquee, hero stat tiles, three testimonial cards in a row.
- [ ] No decorative colored glows or halos.
- [ ] Positioning reads true (a craftsman doesn't look like a discount dealer: no "was" prices, no hype copy).
- [ ] The homepage ends on a closing CTA beat, not on hours and a newsletter.
- [ ] The palette comes from the logo; the client's tagline and voice are used.

## Details
- [ ] Grids fill their rows at every breakpoint (no 2 orphans under a row of 4). No empty columns or floating half-rows.
- [ ] Icons mean what they say: ↗ only on external links, never on internal or tel links. Outline or decorative numerals read clearly.
- [ ] One name per destination in nav and footer.
- [ ] Menus close with their own button and with Escape. Anything JS-driven (open-now status) has a truthful no-JS state.
- [ ] Every interactive feature completes its loop (saved items have somewhere to view them).

## Mobile
- [ ] The tap-to-call is obvious in the header. On contact, the phone option sits above the long form.
- [ ] Sticky sub-navs and pill bars are centered and don't wrap awkwardly.
- [ ] Hours and spec tables keep their columns aligned. Long emails and URLs break cleanly.

## Motion
- [ ] Only transform and opacity animate. Reveals, marquees and parallax stop under reduced motion.
- [ ] Parallax (if asked for) runs at the 50% default on every full-bleed photo. Scroll through at 390 and 1440: no gap at a frame edge, and the deeper crop still shows the subject. browser_qa holds parallax still (reduced motion), so this is a by-eye check.
- [ ] The scrolled header state looks right. Pin `scrollY` before adding the class when you test it, or the scroll handler strips it.
