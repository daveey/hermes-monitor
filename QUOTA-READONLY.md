# Quota polling must not rotate credentials

Problem: `_fetch_account_usage` called the core API with its refresh-capable
`read_only=False` default. The independently reviewed `96b44c70` source still
has this call, despite its read-only credential-snapshot documentation.

Why 1: the poller supplied provider/token but not the `read_only` keyword.
Why 2: credential-snapshot isolation and usage fetching were treated as one
read-only boundary. They are separate: the core selects dedicated Codex/xAI
non-refreshing fetchers only when `read_only=True`.
Root (happened): the plugin wrapper did not select that core contract.
Root (not caught): prior fakes accepted provider/token only; their assertions
covered pool selection and store snapshots rather than refresh-path selection.
Recurrence: inspected `568245ad` (read-only credential snapshots). Its changes
did not close this usage-fetch seam; this correction extends that protection.

Countermeasures:
- Pass `read_only=True` explicitly, including the no-token singleton path.
- Do not retry without it on older cores. Unsupported cores produce an
  unavailable quota rather than a potentially mutating fallback.
- Ten new contract cases cover four providers with/without a token, async
  results, and legacy-core refusal. Test providers are controlled doubles;
  they do not perform OAuth refresh, network I/O or credential writes.
- Existing Anthropic legacy token-isolation behavior is retained. Its direct
  core fetcher reads the explicit token; it is not a Codex/xAI refresh path.

Proof: `tests/test_usage_readonly_contract.py` fails 10/10 when the original
call is restored on the frozen source base and passes after the correction.
`python tests/run_readonly_checks.py` additionally exercises existing quota
and worker transformations while refusing any SQLite connection creation.
SQLite/credential-store integration tests are explicitly excluded from that
cohort, not claimed as passing. The regular full suite is separate.

This source correction alone is not an installation, source-review enrollment,
or quiet-start admission receipt. Those require independent exact-head review,
normal pin propagation, installed-byte parity and live acceptance separately.
