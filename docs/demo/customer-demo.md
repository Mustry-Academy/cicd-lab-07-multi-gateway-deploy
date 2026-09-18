# Oatmakers customer demo

Open https://cloud.mustrysolutions.com/data/perspective/client/oatmakers/ or launch **Oatmakers | Connected factory demo** from the Perspective launcher. Reload an existing session after a release.

All measurements and orders are simulated. Writes are confined to the `oat_demo` database schema and `[default]OatmakersDemo` memory tags. No screen controls equipment or changes customer records.

## Screens

| Route | Purpose |
|---|---|
| `/` | One-second throughput, current shift output, line conditions and alerts |
| `/scada` | Separator A process drawing with live instruments, embedded vessel trends and read-only detail popups |
| `/production` | Mustry Resource Timeline with shift, day, hour and week navigation; click a batch for details |
| `/performance` | Mustry Date Time Range Picker controlling historical charts and aggregate metrics |
| `/quality` | Mustry Data Grid for batches in the selected dates, with measurement and inspection details |
| `/operator` | Production-order entry form alongside an independently scrolling Mustry Data Grid |
| `/demo/health` | Telemetry age, retained history and continuity status |

Legacy `/process`, `/oee` and `/demo/input-fields` links open SCADA, Performance and Production orders. The course observatory remains at `/observatory`. The component library is removed from the customer navigation and routes.

## Demonstration walkthrough

1. Watch the factory throughput and line readings change every second.
2. Open SCADA. Inspect the complete Separator A process and its vessel trends, then click an instrument for its live detail popup.
3. On Performance, choose a live preset or exact calendar dates and times. The selected range controls the database query. Manual selections stop following the clock.
4. Open Production planning, change between shift and week scales, and inspect a batch.
5. In Quality, choose older dates, select a batch, inspect its measurements and record a demo inspection.
6. In Production orders, create a production order. It appears in the grid and remains after reloading. The form has no internal scrollbar.

## Data lifecycle

The dedicated gateway timer runs every second even without a browser. It records deterministic, changing measurements for three lines and writes their latest values to the OatMakers memory tags. Tag-history popups query the same recorded source. A disconnected source shows unavailable readings rather than invented browser values.

Fine telemetry is retained for six hours. Minute history, orders and inspections are retained for the shorter of 90 days and three calendar months. First deployment seeds the retained history. Watermarks fill gaps after downtime, bounded by those retention windows. Database advisory locks prevent overlapping generators and repeated timestamps insert nothing.

One-second production quantities sum to their minute totals. Charts use fine data for recent ranges and minute data for older ranges, with at most approximately 900 plotted points. Line filters and explicit start/end timestamps are applied in SQL. Throughput and power are normalized by the represented duration. The overview emphasizes current operation; slower aggregate efficiency metrics are on Performance.

Batch output and quality are derived from the line-specific recorded production plan. A peak moisture excursion can require review despite an acceptable average. Requests and inspections are persistent demo records; repeated submission IDs cannot create duplicates.

## Mustry UI module

The pinned signed `Mustry_UI-0.5.2.modl` is built from the source commit and Actions run recorded in `tools/demo/mustry-ui-version.json`. The signed module and signature-verification build steps passed. The dry-run workflow subsequently failed in its unrelated PDF documentation footer step; no public module release was published by this change. The module manifest marks it as free, so it does not rely on a trial license.

Screens use the module's Date Time Range Picker, Resource Timeline, Data Grid. The module has no chart renderer; the shared history view pairs its range picker with a styled native Perspective XY chart. The picker output, not a separate preset dropdown, defines the queried range.

## Local development

`compose.demo.yml` isolates Ignition 8.3.8 and PostgreSQL 17.5 at http://localhost:18096, with local gateway credentials `admin` / `password`. Run `tools/demo/start-local.sh`. The named lab gateway is reconciled with the current checkout; unrelated gateways are not stopped. The module initializer seeds the native 8.3.8 module registry and the signed UI module on a fresh volume.

After changing resources:

```sh
IGNITION_URL=http://localhost:18096 scripts/scan.sh local
python3 tools/demo/validate.py
# With ign-lint 0.6.1 in Python 3.10-3.13:
python3 tools/demo/lint_config.py oatmakers
ign-lint --config build/lint/rules.json --files "projects/oatmakers/**/view.json"
python3 tests/demo/test_database.py
python3 tests/demo/test_deploy.py
```

Database tests use a disposable `_test` database. They check real SQL, exact history ranges, line filters, moving fine telemetry, quantity reconciliation, retention, idempotency and recovery after weeks or months offline. Deployment tests preserve unrelated resources and verify idempotent module installation. `build_views.py` regenerates the Perspective resources. The separator geometry is generated by `build_separator.py`; rebuilding requires no external project checkout.

## Cloud deployment and recovery

Release through an immutable project tag and the `release.yaml` pin. The scoped workflow checks scan access, resolves the running PostgreSQL service's managed credentials and applies migrations using the separate `oat_demo_schema_migrations` ledger. The demo password stays in the persistent gateway data volume with owner-only access.

The installer verifies the module checksum and manifest, backs up the existing module registry and binary, then merges only the Mustry UI entry. Other registrations are preserved. A changed module requires one controlled gateway restart; an unchanged install does not restart. If startup fails, the prior registry and binary are restored. Project-only changes continue to use hot scans.

The deployment backs up and replaces only the Oatmakers project and its `OatmakersDemo` connection and `DemoRuntime` secret provider. It verifies that the one-second heartbeat advances, retained history is populated and all seven public routes respond. A failed app verification restores the previous project and owned configuration without deleting database records. The additive free UI module can remain loaded with the previous project.

The Deploy workflow's readiness job runs every six hours. It reads database health directly and checks public routes, so it does not require a Web Dev license. The optional `/system/webdev/oatmakers/api/demo-health` endpoint also returns health where Web Dev is available. An HTTP route check alone does not validate rendering; release review additionally exercises the real screens in a browser.

For failures, inspect Actions, Demo health, database connection `OatmakersDemo`, secret provider `DemoRuntime` and gateway logger `Oatmakers.Demo`. Restoring the connection lets the timer catch up automatically. Scoped project backups expire after 90 days; the server's broader backup policy is managed independently.

## Local startup

Run `tools/demo/start-local.sh` from this lab checkout. It reconciles the local
database, applies migrations, recreates the gateway to load the current project
and pinned module, scans resources and resets the development trial. Existing
gateway and database volumes are retained. The default URL is
`http://localhost:18096/data/perspective/client/oatmakers/`.

To use port 8088, stop any other gateway using that port, then run
`DEMO_HTTP_PORT=8088 tools/demo/start-local.sh`. The root demo-oatmakers project
is a separate application with different pages and backend dependencies.

## Separator reference screen

SCADA uses a complete Separator A process layout based on the supplied reference:
a horizontal vessel, connected inlet/export/drain piping, instrument badges,
valve and pump symbols, and three trends inside the vessel. The scene preserves
its 1740:910 aspect ratio. SCADA keeps the normal application sidebar, logo and page header. The separator
is one view inside the application, with no separate process navigation bar.

Instrument, device, stream, trend and detail elements are reusable embedded
Perspective views under `Demo/Separator/`. Readings and the one-hour trend are
from a deterministic, read-only separator simulation, separate from the
OatMakers production database. Instrument and connected-equipment clicks open a detail popup. No view writes
to plant controls.

Performance initializes its picker outputs and embedded range parameters before
bindings evaluate. Null or pending ranges return a valid empty chart. Error
overlays remain enabled. `tests/demo/test_view_startup.py` verifies startup states
and the transition to a valid history query.

Geometry uses a common design coordinate system for piping, instrument circles,
value badges, valve bodies and highlighted frames. Device flow ports share the
same axis as their connected pipes. Instrument leads stop at circle boundaries,
and pneumatic lines stop at the AS/I-P enclosures instead of crossing their text.

## Separator navigation

`Demo/Separator/Process` contains the complete diagram and its live bindings in
fixed 1740 by 910 coordinates. `Demo/SCADA` embeds it with Mustry Pan & Zoom.
Wheel zoom, drag-to-pan, zoom buttons, reset, fit and the minimap are enabled.
The sidebar and page header stay outside the zoom transform. The view and
module content are transparent on the same grey background.

The order-entry page uses Production orders, Order number, Planned quantity,
Planned bags and Create order. It saves the same order records as before.
