# Brief

Fill in what you know and leave the rest blank. Claude works out everything else from links and photos.
Drop client photos, logos and screenshots into `client-assets/`.

Project type: sample           <!-- sample = portfolio piece (Claude invents missing details) · client = real business (facts only) -->

Business name:
What they do (one line):
Location / service area:
Phone:
Email:
Address:
Hours:
Links (existing site, Google Business Profile, Facebook, Instagram):

Who the customers are:
What makes them different (owner, history, real work, how they do it):
Pages needed (blank = Claude decides):
Main thing visitors should do (call / quote / book / visit):
Form endpoint (e.g. Formspree URL; blank = demo mode, listed at handoff):

Must have:
Must avoid:
Style references (links, or file names in client-assets/):

## Pre-answers (so Claude doesn't stop to ask)

Deploy preview: yes            <!-- noindex preview when the build passes QA -->
Deploy host: cloudflare        <!-- cloudflare (Workers static assets, ex-Pages: unlimited free bandwidth) · netlify -->
Use stock photos for gaps: yes
AI image prompts: no           <!-- yes = write image-generation prompts for the gaps instead of stock -->
Pause for direction review: no <!-- yes = stop after the homepage so you can review it -->
