# Working on UGV Nav

Read `CLAUDE.md` first. It holds the goal, the working rules, the architecture and
the plan, and it wins where this file is more cautious or formal.

- Check Git status and the relevant files before editing; preserve existing work.
- The owner does the physical steps (wiring, power, flashing, driving). Buy nothing
  and set up no paid service without permission.
- Prefer established libraries and simple typed Python modules. Keep names clear,
  functions small, public interfaces documented.
- Add dependencies only when used. Check Python, OS, architecture and SDK
  compatibility, pin a tested environment, and document the install and run path.
- When importing code, record source revision, paths, licence and changes. Keep
  third-party notices. Review dataset and model licences.
- Run the smallest meaningful verification. Test control boundaries and data
  integrity. Don't add tests that mirror prose.
