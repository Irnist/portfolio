// pipeline-tool-stub: runs the pipeline's shared copy of this tool on this site, so every site always gets the
// current checks (L-052). Fix or extend the tool in <workspace>/Workflow and Pipeline/website-pipeline/tools/,
// never here. Site-only scripts sit beside this stub as ordinary files.
import { existsSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = fileURLToPath(import.meta.url);
process.env.SITE_ROOT = dirname(dirname(here));
let tool = null;
for (let dir = dirname(here); !tool && dir !== dirname(dir); dir = dirname(dir)) {
  const t = join(dir, 'Workflow and Pipeline', 'website-pipeline', 'tools', basename(here));
  if (existsSync(t)) tool = t;
}
if (!tool) {
  console.error(`${basename(here)}: no Workflow and Pipeline/website-pipeline/tools/ above this site`);
  process.exit(2);
}
process.argv[1] = tool;  // the shared tool checks argv[1] to know it was run directly
await import(pathToFileURL(tool).href);
