# Versioned training inputs

`catalog.json` is seed input, not a public asset. Only S02 v1 is enabled initially.
S01–S05 share schema v1 and include routine traffic; complete detector acceptance
belongs to step 08. No fixture is copied from the browser prototype.

`events/training/` contains future schedules for the runner only. Keys are opaque
within each fixture; log records contain observations, not outcome labels.
`ground-truth/training.json` contains incident groups and evidence references for
the evaluator. It is not an exam rubric, score or learner feedback policy.

Public demo uses the separate benign snapshot in app/demo.py. No exam cases are
seeded. Future exam inputs must use `purpose=exam` in a separate restricted bank;
the training loader/seed/table reject that purpose. Exam admission remains closed
until lesson/level gates and pending policy decisions are implemented.

Container base/API: no fixture files. Runner: training events only. Seed/test
targets: restricted catalog/truth inputs. Do not deploy the seed/test image as an
API or worker. No static mount, retrieval indexing or frontend imports are allowed.

Seed canonical hash: SHA-256 of UTF-8 JSON, sorted keys, compact separators,
ensure_ascii=False, Pydantic v1-format defaults included. Existing versions are
immutable; seed conflicts abort the whole transaction instead of updating data.
Introduce new UUID/version files for revisions; keep old versions for replay.
