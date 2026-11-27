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
- Refuse absent or empty explicit tokens before importing core; never discover
  an ambient singleton or load a mutable credential pool. `read_only=True`
  alone does not prevent core's no-token credential resolution/refresh.
- Pass `read_only=True` explicitly only with an explicit snapshot token.
- Do not retry without it on older cores. Unsupported cores produce an
  unavailable quota rather than a potentially mutating fallback.
- Eighteen contract cases cover four providers with/without a token, rejection
  before core imports, async results and legacy-core refusal. Three additional
  real-core dispatch cases cover denied resolver seams, Codex 401/default-control
  and Anthropic's actual clone path. External effects are recording doubles,
  not live OAuth/HTTP/credential-store proof. Core-dependent cases explicitly
  skip when core is unavailable; the local core-enabled cohort exercises them.
- Removed dead mutable-pool/singleton collectors and their `use_pool` switch;
  migrated their useful tests to the production immutable-snapshot collector.
- Existing Anthropic legacy token-isolation behavior is retained. Its direct
  core fetcher reads the explicit token; it is not a Codex/xAI refresh path.

Proof: `tests/test_usage_readonly_contract.py` fails 10/10 when the original
call is restored on the frozen source base and passes after the correction.
`python tests/run_readonly_checks.py` additionally exercises existing quota
and worker transformations while refusing any SQLite connection creation.
SQLite/credential-store integration tests are explicitly excluded from that
cohort, not claimed as passing. The regular full suite is separate.

## Independent review F1 correction

Problem: review 6093558291 demonstrated that the wrapper still reached ambient
Codex/Anthropic credential resolution with no explicit token, despite the doc's
read-only claim. Production snapshot routes already excluded empty tokens.
Why 1: `read_only` selects the HTTP refresh implementation, not all credential
resolution; core's Codex no-token resolver still uses refresh_if_expiring=True.
Why 2: the wrapper retained unused mutable-pool collectors and singleton fallback.
Root (happened): credential discovery was not fenced at the wrapper boundary.
Root (not caught): synthetic no-token fetchers modeled a stronger read_only
contract than core actually offers. The review traced and exercised real core.
Recurrence: successor correction to the original omitted-keyword fix; not a
claim that the shipped routes performed a live mutation.
Proof: the new assertions on the reviewed head produced 12 failures (4 unwanted
no-token core calls and 8 imports-before-refusal), with 55 passes/1 skip/5
excluded SQL tests. The corrected contract passes 18/18. Final core-enabled
SQL-denying cohort passes 71 tests, excluding 5 SQL integrations. Five isolated
mutants (guard deletion, empty-string bypass, omitted/False read_only, dropped
token) are killed; the unmodified baseline is green. Real-core tests use denied
credential seams and recording HTTP doubles, never actual provider calls.

## Independent review F2 correction

Problem: review 6093720310 reproduced a whitespace-only snapshot token reaching
Codex `resolve_codex_runtime_credentials(refresh_if_expiring=True)` through the
production collector. OpenRouter also entered ambient provider resolution.
Why 1: the wrapper's truthiness guard accepted whitespace, while core strips it
and therefore treats the same value as missing.
Why 2: immutable auth snapshots preserve raw token values; the boundary had no
shared normalization rule with its downstream consumer.
Root (happened): emptiness semantics differed across the credential boundary.
Root (not caught): missing-token fixtures used only None and the empty string,
not whitespace or malformed raw snapshot values; fake fetchers did not normalize.
Recurrence: successor to F1, not a new live credential-write claim. The reviewer
used recording/raising effects; actual OAuth, HTTP and storage were not invoked.
Countermeasure: require a string, strip it, refuse an empty result before importing
core, and pass only the normalized explicit token. No coercion of malformed values.
Proof: tests on unchanged reviewed production 87c9cfd produced 36 failures and
88 passes (5 SQL integrations excluded), including genuine real-core collector
failures. Corrected SQL-denying cohort: 124 passes / 5 excluded. Contract cases
cover four providers, whitespace, non-string values, and normalized valid tokens;
19 new real-core cases cover direct refusal, both affected snapshot routes and
an explicit-token HTTP-only control. External effects remain recording doubles.
The Anthropic real-core test additionally refuses generic dispatch so deleting
the isolated clone cannot pass that test through core's newer implementation.

This source correction alone is not an installation, source-review enrollment,
or quiet-start admission receipt. Those require independent exact-head review,
normal pin propagation, installed-byte parity and live acceptance separately.
