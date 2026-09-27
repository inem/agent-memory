# agent-memory.sessions TAP pack

This command-only pack schedules `mem sync-tap-sessions` every two minutes using
TAP Core's background command host. It reads the output of the already enabled
`chatgpt.sessions` pack in the same profile. It does not capture HTTP traffic,
parse responses or install host hooks.

Build with TAP Pack SDK, install and enable the artifact with the
`command.execute` and `background.run` grants. Supply an absolute executable
and store path at enable time:

```sh
python3 /path/to/tap-pack-sdk/sdk.py --core /path/to/tap-core build \
  integrations/tap-memory --out /tmp/agent-memory-pack
cat > /tmp/agent-memory-config.json <<'JSON'
{"mem-bin":"/absolute/path/to/mem","memory-store":"/absolute/path/to/agent-memory-store"}
JSON
/path/to/tap --profile /absolute/profile pack install \
  /tmp/agent-memory-pack/agent-memory.sessions-0.1.0.tap-pack
/path/to/tap --profile /absolute/profile pack enable agent-memory.sessions \
  --version 0.1.0 --grant-origin https://chatgpt.com \
  --grant-capability command.execute --grant-capability background.run \
  --config /tmp/agent-memory-config.json
```

The `chatgpt.sessions` reader must be enabled on the same TAP profile.
`tap memory sync` runs one pass manually. The output reports archived messages
and divergent conversations; a divergence does not silently rewrite history.

Distillation is an independent step: invoke `mem distill` against the same
store on the cadence appropriate for the agent. This pack schedules capture
only; it does not launch a model on every TAP interval.
