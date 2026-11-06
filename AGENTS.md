# Working on UGV Nav

Read `CLAUDE.md` first. It holds the goal, the ML evaluation rules and the current
plan, and it wins where this file is more cautious or formal.

## Scope and collaboration

- Check Git status and the relevant files before editing; preserve existing work.
- Explain consequential engineering choices briefly, including their limits.
- The owner does the physical steps (wiring, power, flashing, driving). Software
  prepares them, keeps the robot in bounds and records what happened. Buy nothing
  and set up no paid service without permission.

## Implementation

- Prefer established libraries and simple typed Python modules. Keep names clear,
  functions small, public interfaces documented.
- Separate pure logic, device I/O, recording/replay and simulation. Replay and
  simulation must never move the robot.
- Make units, frames, timestamps, source mode and validity explicit. Use monotonic
  time for command deadlines.
- Physical control needs bounded commands, validated inputs, stop behaviour and
  timeout/link-loss handling.
- Add dependencies only when used. Check Python, OS, architecture and SDK
  compatibility, pin a tested environment, and document the install and run path.
- When importing code, record source revision, paths, licence and changes. Keep
  third-party notices. Review dataset and model licences.

## Evidence and privacy

- Keep plans, prior reports and tests done now apart. Record date, configuration,
  commands, result and limits.
- Credentials, private messages, purchase documents, network addresses and the AMP
  vault stay out of this repo. Commit only sanitized summaries.
- Run the smallest meaningful verification. Test control boundaries and data
  integrity. Don't add tests that mirror prose.
- Before finishing, check `git diff --check`, secrets, generated and untracked
  files. Report changes, checks, limits and the next task.
