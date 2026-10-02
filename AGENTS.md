# Working on UGV Nav

## Scope and collaboration

- Build toward bounded navigation in a small test area — first the owner's room,
  then the owner's balcony (outdoor light) — with one evaluated ML contribution.
  `CLAUDE.md` holds the current working decisions and wins where this file is
  more cautious or formal.
  Explain consequential engineering choices briefly, including their limits.
- Inspect Git status and relevant files before editing; preserve existing work.
  Do not commit or push unless requested.
- Treat AMP as a read-only technical reference. Its historical architecture,
  governance, and plans are not requirements here.
- Hardware configuration, firmware changes, power changes, and physical movement
  require an explicitly scoped commissioning task. Local software work may
  proceed within the requested task. Do not purchase or provision paid services
  without explicit authorization.

## Implementation

- Build only the structure needed for the next observable result. Prefer
  established libraries and simple modules over a new framework.
- Use typed Python for orchestration unless another language serves a concrete
  need. Keep names clear, functions small, and public interfaces documented.
- Separate pure logic, device I/O, recording/replay, and simulation. Replay and
  simulation must not acquire physical actuation as a side effect.
- Make units, coordinate frames, timestamps, source mode, and validity explicit
  in sensor/command contracts. Use monotonic time for local command deadlines.
- Physical control must have bounded commands, validated inputs, stop behavior,
  and timeout/link-loss handling. A host process alone cannot establish stopping
  after host failure; verify the controller-side behavior before relying on it.
- Add dependencies only when used. Check target Python/OS/architecture and SDK
  compatibility, pin a tested environment, and document the install/run path.
- Record source revision, source paths, license/attribution, and changes when
  importing code. Keep third-party notices and review dataset/model licenses.

## Evidence and privacy

- Distinguish plans, prior reports, inspected artifacts, and tests performed now.
  Record date, configuration, commands, observed result, and limitations.
- Keep raw data, credentials, private correspondence, purchasing documents,
  network addresses/host identities, and the AMP vault/history out of this repo.
  Use ignored local storage; commit only reviewed, sanitized summaries/manifests.
- For ML, separate recording sessions across train/validation/test; freeze the
  test set before tuning. Record data/model versions and report failure cases.
- Run the smallest meaningful verification for the change. Test control
  boundaries and data integrity; do not add tests that just mirror prose/code.
- Before finishing, review changed-file scope, `git diff --check`, secrets and
  generated files. Inspect untracked files too. Report changes, verification,
  limits, and the next concrete task.
