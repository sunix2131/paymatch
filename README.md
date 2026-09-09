# PayMatch

CLI for comparing internal payments with a bank or payment-provider statement. It reports matched rows, amount differences, missing records, duplicate references and ambiguous matches.

References are normalized before comparison; amount and timestamp tolerances are configurable. A tie stays unresolved instead of being assigned to whichever row happens to come first. The included statements are synthetic; the implementation contains no employer code or customer data.

## Pipeline

```text
CSV / JSON
    ↓
parse and normalize
    ↓
quarantine duplicate references
    ↓
generate candidates by currency, time window and normalized reference
    ↓
score configured evidence
    ↓
resolve unique mutual-best pairs
    ↓
JSON report + optional PostgreSQL audit record
```

The resolver is deliberately conservative. A pair is accepted only when each side is the other's unique highest-scoring candidate. Remaining connected candidate sets become `AMBIGUOUS`; input order and a lucky greedy traversal cannot decide which payment wins.

Possible outcomes:

```text
MATCHED
AMOUNT_MISMATCH
MISSING_INTERNAL
MISSING_EXTERNAL
DUPLICATE
AMBIGUOUS
REFERENCE_MISMATCH
```

Every result carries the involved IDs, score and evidence used to reach it.

## Numeric and time rules

- Amounts are parsed directly into `Decimal`, including JSON numeric literals. Difference calculations use enough local precision for both inputs, independently of the caller's decimal context.
- Signed amounts are supported, so refunds do not need a separate representation.
- Timestamps must contain an explicit UTC offset and are normalized to UTC. Microseconds are retained when testing the matching window.
- Candidates never cross currencies.
- Exact normalized references remain candidates outside the time window so amount discrepancies are visible rather than misreported as missing.

## Run the example

Requires Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

reconcile examples/internal.csv examples/external.csv \
  --rules examples/rules.yaml \
  --output report.json
```

Input columns:

```text
id,amount,currency,timestamp,reference
```

Reports are written through a temporary file and replaced only after a complete write. The output path cannot be an input statement or the rules file.

JSON may be an array of the same records or an object containing a `transactions` array. Duplicate IDs, naive timestamps, non-finite amounts and malformed currencies fail the run with the source row number.

## Matching policy

Rules are explicit and reviewable:

```yaml
rules:
  - type: exact_reference
    weight: 100

  - type: amount
    tolerance: "0.01"
    weight: 50

  - type: timestamp
    tolerance_seconds: 300
    weight: 20
```

Decimal tolerances are quoted in YAML to prevent the YAML parser from creating a binary float before the engine sees the value. Unknown rules and fields are rejected rather than ignored.

## Persist a run

The JSON report is self-contained. For an audit trail, pass a SQLAlchemy URL:

```bash
docker compose up -d postgres

reconcile examples/internal.csv examples/external.csv \
  --rules examples/rules.yaml \
  --database-url postgresql+psycopg://reconcile:reconcile@localhost:5432/reconcile
```

The run metadata, rules snapshot, summary and result groups are inserted in one transaction. PostgreSQL is the CI integration target; SQLite is useful for isolated tests and local inspection.

## Verification

```bash
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
mypy
pytest
```

The suite covers normalization, exact and fuzzy evidence, amount/reference mismatches, missing records, duplicate quarantine, ambiguous same-amount candidates, input-order independence, refunds, malformed input, CLI output, empty reports and atomic persistence. CI repeats the tests on Python 3.12 and 3.14 and exercises storage against PostgreSQL 17.

## Boundaries

- Duplicate detection currently uses repeated normalized references within one source and currency. A production policy may additionally scope duplicates by merchant or settlement batch.
- Inputs are CSV and JSON; XLSX is not supported.
- Candidate generation uses indexed timestamp windows plus reference lookup. Very large files would benefit from streaming ingestion and database-side candidate batches.
- `AMBIGUOUS` is intentionally not auto-resolved. An operational system should expose these groups to a reviewer and store the final manual decision.
- Foreign-exchange reconciliation is out of scope; each currency is reconciled independently.
