"""Finite TAP background command for the agent-memory session importer."""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    context = json.loads(os.environ["TAP_COMMAND_CONTEXT"])
    config = context.get("config", {})
    binary = config.get("mem-bin")
    store = config.get("memory-store")
    profile = Path(context["profile"])
    source = profile / "data" / "readers" / "chatgpt.sessions"
    if not binary or not Path(binary).is_absolute() or not store or not Path(store).is_absolute():
        print("Configure absolute mem-bin and memory-store paths", file=sys.stderr)
        return 2
    result = subprocess.run(
        [binary, "--store", store, "--json", "sync-tap-sessions", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
