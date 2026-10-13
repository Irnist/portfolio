GSAP 3.15.0 (npm `gsap`, dist/*.min.js), self-hosted for sites with `GSAP motion: yes`.
Licence: GSAP Standard "no charge" licence (https://gsap.com/standard-license), free for commercial
client sites, every plugin included. Each file keeps its own licence header.

The build (`_src/build.py`) copies gsap.min.js plus only the plugins listed in `site_config.GSAP`
into dist/assets/js/vendor/gsap/. ScrollSmoother is left out on purpose: it takes over scrolling and
breaks main.js parallax. To add a plugin, copy its .min.js here from the same gsap version's dist/.
