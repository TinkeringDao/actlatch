# Contributing

Contributions that improve reliability, test coverage, documentation, or simulation/platform support are welcome.

## Ground Rules

- Read and follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) in all issues, pull requests, commit messages, and discussions.
- Review [`LEGAL.md`](LEGAL.md) before submitting protocol, adapter, or hardware-interoperability changes. Clean-room boundaries and zero proprietary binary redistribution are strictly enforced.
- Do not include personal data, learner data, private network addresses, device serial numbers, MAC addresses, or credentials in code, tests, logs, or fixtures.
- Report security vulnerabilities privately via [`SECURITY.md`](SECURITY.md) rather than public issues.

## Local Verification

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

## Pull Request Workflow

1. Create a focused topic branch from `main` (`feat/...`, `fix/...`, `docs/...`, `chore/...`, `ci/...`).
2. Keep commits atomic, use Conventional Commit headers (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`), and sign all commits (`git config commit.gpgsign true`).
3. Run the repository's local build, linter, and unit-test suite before opening a pull request.
4. Open a pull request against `main` summarizing the problem, root cause or design choice, and verification output. All pull requests squash-merge onto `main` once `ci` and `security` checks pass.
