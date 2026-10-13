"""pipeline-tool-stub: runs the pipeline's shared copy of this tool on this site, so every site always gets the
current checks (L-052). Fix or extend the tool in <workspace>/Workflow and Pipeline/website-pipeline/tools/,
never here. Site-only scripts sit beside this stub as ordinary files."""
import os
import runpy
import sys
from pathlib import Path

here = Path(__file__).resolve()
os.environ["SITE_ROOT"] = str(here.parent.parent)
shared = [p / "Workflow and Pipeline" / "website-pipeline" / "tools" / here.name for p in here.parents]
tool = next((t for t in shared if t.is_file()), None)
if tool is None:
    sys.exit(f"{here.name}: no Workflow and Pipeline/website-pipeline/tools/ above this site")
sys.argv[0] = str(tool)
runpy.run_path(str(tool), run_name="__main__")
