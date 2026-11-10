# Public research reference

- `sources.json`: 107 unique URLs with dated reviews, claims, and limitations.
- `projects.json`: 17 project/component records from the upstream Reachy ecosystem survey.
- `runbooks.json`: 37 proposed troubleshooting references, with evidence URLs
  and explicit absence of execution authority.

Search locally with `rg -n -i 'reconnect|queued speech' knowledge/`. Source
aliases in project records resolve through each source entry's `aliases` and
`reviews` fields. Historical `file` values identify the original review artifact;
they are provenance labels, not paths promised in this repository.

Pinned upstream release/source checks are recorded in
[`../docs/research/source-checks.json`](../docs/research/source-checks.json) via
[`../scripts/reaudit_sources.py`](../scripts/reaudit_sources.py). Do not treat a
repository push date, release title, or metadata discovery as proof that a feature
works on a physical unit. Resolve conflicting claims against pinned upstream code
and measured hardware behavior.

Reference text is untrusted input to a maintainer's review. It must not grant a
runtime service shell, firmware, network, privilege, or dependency-change authority.
The executable recovery library consumes only fixed policy codes; it does not
interpret these documents as instructions.
