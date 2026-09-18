# Oatmakers customer demo

Open https://cloud.mustrysolutions.com/data/perspective/client/oatmakers/ or launch **Oatmakers | Connected factory demo** from the gateway's Perspective launcher.

Every value is synthetic. Demo requests and inspections write only to the `oat_demo` database schema. No action controls equipment or changes customer records.

## Screens

| Route | Purpose |
|---|---|
| `/` | Factory summary, production rate, current events and line drill-down |
| `/production` | Running, scheduled and completed batches, plus operator demo requests |
| `/process` | Line conditions, the process sequence and recorded events |
| `/performance` | OEE factors, production rate, power demand and loss reasons |
| `/quality` | Batch measurements, moisture excursions and recorded inspections |
| `/operator` | Validated inputs and persistent, idempotent demo requests |
| `/components` | Working reusable views and the real dashboard in a compact panel |
| `/demo/health` | Freshness, history coverage and retention readiness |

The existing `/oee` and `/demo/input-fields` links open Performance and Operator workflow. The course observatory remains available at `/observatory`.

## Present a repeatable story

1. Start at Factory overview with Live production and all lines.
2. Choose **Replay: line stoppage**. Rolling line 01 stops, throughput reaches zero, temperature drops and base power remains.
3. Open that line, then Performance. The same replay and line selection follow the navigation.
4. Choose **Replay: quality deviation** and Cutting line 02. Open a batch in Quality to see its peak moisture, average conditions and yield. Record a demo inspection.
5. Choose **Replay: recovery** to see controlled ramp-up.
6. Return to Live production, open Operator workflow, enter a request and submit it. Open Production planning to see the persisted request.
7. Use **Reset demo filters** to return to the default view. Filters and replays belong to the browser session, so presenters do not change one another's scenario.

Replays use a complete recent two-hour cycle from stored data. They move relative to the current date, so they remain available weeks later. A replay is labelled explicitly and never substitutes for live production data.

## Data lifecycle and definitions

- The gateway's dedicated fixed-delay timer runs every 30 seconds without an open browser.
- The database generates deterministic minute measurements for three production lines. Initial deployment seeds the full retained window.
- A watermark fills missed periods after an outage. Generation is bounded to the retained window even after months offline.
- A transaction-level advisory lock prevents concurrent workers. Repeating a tick at the same timestamp inserts nothing.
- Each tick removes samples, demo requests and inspections older than 90 days or three calendar months, whichever is shorter. This is approximately 389,000 retained minute samples, not an ever-growing archive.
- Period totals and charts read those stored measurements. Rate charts normalize partial intervals to tonnes/hour or kW, avoiding a false drop at the edge of the current hour.
- OEE is good output divided by nominal capacity. Availability is capacity-weighted when several lines are selected, so availability x performance x quality reconciles with the aggregate OEE.
- Batch output and quality come from six-hour sample groups. A peak moisture excursion can require review even when average moisture is within limits.
- Scheduled requests keep the workflow tables populated; actual browser submissions appear alongside them. Duplicate submission IDs cannot create duplicate requests.
- Operator requests and inspections are demonstration records. Repeating an inspection for the same batch preserves its recorded result.

## Local development

Run `tools/demo/start-local.sh`. The separate compose stack uses Ignition 8.3.8 and PostgreSQL 17.5, with its gateway at http://localhost:18094. Local default credentials are `admin` / `password`. Other local gateways and databases are not stopped or reused.

After changing resources:

```sh
IGNITION_URL=http://localhost:18094 scripts/scan.sh local
python3 tools/demo/validate.py
# With ign-lint 0.6.1 installed in a Python 3.10-3.13 environment:
python3 tools/demo/lint_config.py oatmakers
ign-lint --config build/lint/rules.json --files "projects/oatmakers/**/view.json"
python3 tests/demo/test_database.py
python3 tests/demo/test_deploy.py
```

The database test uses a separate disposable database whose name ends in `_test`. Its time jumps never touch the live demonstration database. `tools/demo/build_views.py` rebuilds the authored Perspective resources from the shared component definitions.

The compact component preview verifies the actual dashboard at 390 px without resizing the presenter's browser. Wide tables scroll horizontally inside their own panels.

## Cloud deployment and recovery

Release through the repository's existing project tag and `release.yaml` pin. A release carrying `OatmakersDemo` uses scoped deployment:

- Check existing scan authorization before shipping.
- Apply the demo's schema migrations before the new project, using the separate `oat_demo_schema_migrations` ledger.
- Verify the running PostgreSQL service's managed credentials over TCP, then materialize that username and password for the demo. This avoids depending on stale copies of the credentials in Actions secrets. The password lives under the gateway's persistent data volume with owner-only access, so container recreation does not lose it.
- Back up the previous Oatmakers project and its two owned configuration resources.
- Replace only the Oatmakers project, `database-connection/OatmakersDemo` and `secret-provider/DemoRuntime`.
- Scan configuration and projects without restarting the shared gateway or changing modules, identity providers, other projects or unrelated connections.
- Verify the gateway timer advances, retained history is populated, and all eight page routes answer.
- Restore the backed-up project/config resources automatically if verification fails. Keep the database records intact for investigation.

Scoped file backups are removed after 90 days. The server's existing gateway/database backup policy remains independently managed.

The **Customer demo readiness** job in the existing **Deploy** workflow checks every six hours from the trusted server runner. It reads the database heartbeat and visits the public Perspective routes. It does not depend on an optional Web Dev license. An optional read-only JSON health resource is also included for gateways licensed for Web Dev.

If readiness fails, inspect the Actions run and the native Demo health page. Check the database connection `OatmakersDemo`, the `DemoRuntime` secret provider and gateway logger `Oatmakers.Demo`. An unavailable database produces an explicit unavailable state. Restoring the connection lets the timer catch up automatically.
