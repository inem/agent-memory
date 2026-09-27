# TAP source boundary

TAP Core captures HTTP observations and independently delivers them to readers.
The ChatGPT sessions pack turns eligible conversation bodies into immutable
versioned JSON snapshots, a latest-observed pointer, and a disposable readable
projection. Its output is the earliest existing session-shaped material for
agent-memory to consume without reimplementing the application's protocol.

Memory ingestion should address each observation by source, conversation, version,
and stable node identity where available. Its raw evidence remains immutable;
consumer progress belongs to agent-memory. A retry must not duplicate an
observation, and a changed current branch must not be treated as an appended
suffix. Distillation must distinguish newly observed nodes, changed nodes,
removed nodes, and a changed active path before it can safely supersede an
earlier memory. Missing capture cannot be inferred from the saved snapshots.

The current pack output is not yet a durable ordered change feed. Version
filenames identify content, while the latest pointer and one observation marker
describe only the latest observation. A directory scan can discover versions
but cannot reconstruct every observation order or safely infer that an unseen
version supersedes another. A live consumer needs either its own TAP reader
cursor over capture records or a pack-owned append-only observation feed with
stable delivery identity. The latter shares the application's parser without
making the pack responsible for memory decisions.

The first filesystem adapter reads only the latest pointer. It imports an
unchanged active-path prefix plus new visible nodes, and holds any divergence
for review. It neither claims complete intermediate observations nor attempts
to reconcile edits or alternate branches. This is a bounded capture path,
not a substitute for the eventual ordered observation feed.

The session index is an optional factual projection over the same versions for
history, graph queries, and comparisons. A searchable archive CLI is an access
tool over the saved material. Neither is required in the ingestion path.

Other conversation sources require their own session adapters: the current
ChatGPT sessions pack covers captured web conversation bodies, not Work desktop
rollouts, Claude sessions, or streamed response text absent from retained HTTP
bodies. Source coverage must be reported per adapter rather than inferred from
the fact that TAP was enabled.
