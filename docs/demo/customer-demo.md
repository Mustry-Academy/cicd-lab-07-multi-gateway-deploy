# Oatmakers customer demo

Open https://cloud.mustrysolutions.com/data/perspective/client/oatmakers/ or launch **Oatmakers | Connected factory demo** from the Perspective launcher. Reload an existing session after a release.

All measurements and requests are simulated. Writes are confined to the `oat_demo` database schema and `[default]OatmakersDemo` memory tags. No screen controls equipment or changes customer records.

## Screens

| Route | Purpose |
|---|---|
| `/` | Five-second throughput, current shift output, line conditions and alerts |
| `/scada` | Original peeling and heating drawings in Mustry Pan Zoom View; click measurements for history |
| `/production` | Mustry Resource Timeline with shift, day, hour and week navigation; click a batch for details |
| `/performance` | Mustry Date Time Range Picker controlling historical charts and aggregate metrics |
| `/quality` | Mustry Data Grid for batches in the selected dates, with measurement and inspection details |
| `/operator` | Validated request form alongside an independently scrolling Mustry Data Grid |
| `/demo/health` | Telemetry age, retained history and continuity status |

Legacy `/process`, `/oee` and `/demo/input-fields` links open SCADA, Performance and Operator workflow. The course observatory remains at `/observatory`. The component library is removed from the customer navigation and routes.

## Demonstration walkthrough

1. Watch the factory throughput and line readings change every five seconds.
2. Open SCADA. Pan, zoom or use a point of interest. Switch between peeling and heating, then click a temperature or pressure reading.
3. In the history popup, choose a live preset or exact calendar dates and times. The selected range controls the database query. Manual selections stop following the clock.
4. Open Production planning, change between shift and week scales, and inspect a batch.
5. In Quality, choose older dates, select a batch, inspect its measurements and record a demo inspection.
6. In Operator workflow, create a request. It appears in the grid and remains after reloading. The form has no internal scrollbar.

## Data lifecycle

The dedicated gateway timer runs every five seconds even without a browser. It records deterministic, changing measurements for three lines and writes their latest values to the SCADA memory tags. Tag-history popups query the same recorded source. A disconnected source shows unavailable readings rather than invented browser values.

Fine telemetry is retained for 48 hours. Minute history, requests and inspections are retained for the shorter of 90 days and three calendar months. First deployment seeds the retained history. Watermarks fill gaps after downtime, bounded by those retention windows. Database advisory locks prevent overlapping generators and repeated timestamps insert nothing.

Five-second production quantities sum to their minute totals. Charts use fine data for recent ranges and minute data for older ranges, with at most approximately 900 plotted points. Line filters and explicit start/end timestamps are applied in SQL. Throughput and power are normalized by the represented duration. The overview emphasizes current operation; slower aggregate efficiency metrics are on Performance.

Batch output and quality are derived from six-hour recorded groups. A peak moisture excursion can require review despite an acceptable average. Requests and inspections are persistent demo records; repeated submission IDs cannot create duplicates.

## Mustry UI module

The pinned signed `Mustry_UI-0.5.2.modl` is built from the source commit and Actions run recorded in `tools/demo/mustry-ui-version.json`. The signed module and signature-verification build steps passed. The dry-run workflow subsequently failed in its unrelated PDF documentation footer step; no public module release was published by this change. The module manifest marks it as free, so it does not rely on a trial license.

Screens use the module's Date Time Range Picker, Resource Timeline, Data Grid and Pan Zoom View. The module has no chart renderer; the shared history view pairs its range picker with a styled native Perspective XY chart. The picker output, not a separate preset dropdown, defines the queried range.

## Local development

`compose.demo.yml` isolates Ignition 8.3.8 and PostgreSQL 17.5 at http://localhost:18096, with local gateway credentials `admin` / `password`. Run `tools/demo/start-local.sh`. Other local gateways are not stopped or reused. The module initializer seeds the native 8.3.8 module registry and the signed UI module on a fresh volume.

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

Database tests use a disposable `_test` database. They check real SQL, exact history ranges, line filters, moving fine telemetry, quantity reconciliation, retention, idempotency and recovery after weeks or months offline. Deployment tests preserve unrelated resources and verify idempotent module installation. `build_views.py` regenerates the Perspective resources. The SCADA SVG assets are committed geometry; rebuilding the views requires no external project checkout.

## Cloud deployment and recovery

Release through an immutable project tag and the `release.yaml` pin. The scoped workflow checks scan access, resolves the running PostgreSQL service's managed credentials and applies migrations using the separate `oat_demo_schema_migrations` ledger. The demo password stays in the persistent gateway data volume with owner-only access.

The installer verifies the module checksum and manifest, backs up the existing module registry and binary, then merges only the Mustry UI entry. Other registrations are preserved. A changed module requires one controlled gateway restart; an unchanged install does not restart. If startup fails, the prior registry and binary are restored. Project-only changes continue to use hot scans.

The deployment backs up and replaces only the Oatmakers project and its `OatmakersDemo` connection and `DemoRuntime` secret provider. It verifies that the five-second heartbeat advances, retained history is populated and all seven public routes respond. A failed app verification restores the previous project and owned configuration without deleting database records. The additive free UI module can remain loaded with the previous project.

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

## SCADA presentation

The SCADA design follows the level-2 example on slide 38 of Graham Nasby's
[2017 ISA-101 and high-performance HMI presentation](https://www.grahamnasby.com/files_publications/NasbyG_2017_HighPerformanceHMIs_IntelligentWastewaterSeminar_WEAO_sept14-2017_slides-public.pdf):
blue PV, green SP, grey process equipment and an always-visible trend. Colour
is accompanied by explicit labels and abnormal-condition text.

The drawing and pan/zoom content are transparent on one grey background.
The embedded trend stays outside the zoom transform. Selecting a measurement
changes the trend; changing the process area resets the drawing to fit.

SP values are read-only nominal simulation targets, not plant control writes.
Power is consumption and has no SP. The temperature and moisture trend limits
come from the demo's existing quality specifications. The OatMakers SVG logo
is embedded in the project so deployment does not depend on a gateway image.

Local verification covers both process areas, zoom out to 46%, zoom in to
141%, automatic fit on area changes, PV selection, live chart data and the
seven-page runtime readiness check.
