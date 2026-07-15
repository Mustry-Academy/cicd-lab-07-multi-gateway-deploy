# Lab 07 — Deployments in a multi-gateway architecture

**Day 4 · afternoon session.** For once, you will not fork our repo. Everyone
works as a **contributor** on one shared, locked-down repository. Every push
to `main` auto-deploys onto your **own test gateway**, and every change to
`release.yaml` deploys to **a real production gateway** on the internet. You
first stand up that personal test gateway, then bring a project with your own
name live, then land one of five
team challenges on the shared oatmakers project, then build on each other's
work. Real reviews, real deploys, real merge conflicts.

The point of the afternoon: **use everything we learned and get some reps
in** — feature branch, commits, PR, tag, deploy, again and again until the
loop feels like muscle memory.

**Duration:** ~3 hours

* 60 min teaching ([`slides/teaching.html`](../slides/teaching.html))
* 30–45 min we-do (below, woven into the teaching)
* 60–75 min you-do ([`slides/assignment.html`](../slides/assignment.html) mirrors this file)
* Debrief — this is the last lab, so the debrief also closes the course

The full teaching content is written out in
[`docs/multi-gateway-deployments.md`](../docs/multi-gateway-deployments.md);
use it to re-read anything from the hour.

## Goal

You should leave this lab able to:

- Work as a **contributor on a shared, locked-down repo**: protected main,
  validated commits only, PRs with green checks, human review before merge
- Explain the two deploy channels: a push to `main` auto-deploys to **your
  test gateway**, while **only `release.yaml` decides what reaches
  production** — and why one is gated and the other is not
- Cut a **prefixed tag** (`<yourname>@v1.0.0`, `oatmakers@v2.0.X`) and explain
  why the tag must exist **before** `release.yaml` may point at it
- Read `runs-on: [self-hosted, cicd-capstone]` and explain how a runner
  label routes a deploy to one site's network
- Ship the lab 06 building blocks through a real pipeline: a **third-party
  module**, a **library JAR**, a **db-migration pair** and a **referenced
  secret**
- Share **one version stream with four other people**: pull main often, take
  the next free tag number, keep PRs small, and solve the merge conflicts
  that happen anyway
- Say when you would split the infra part (release files, gateway config)
  into its own repo — the teaching's option B — and when one repo is enough

## What you're working with

**One repo, and you are a contributor on it:**

```
git@github.com:Mustry-Academy/cicd-lab-07-multi-gateway-deploy.git
```

```
projects/
  oatmakers/            the shared team project (Part 2 lands here)
  <yourname>/           your own project (you create this in Part 1)
third-party-modules/    modules the pipeline installs (lab 06)
jar-files/jar/            library JARs → lib/core/gateway (lab 06)
db-migration/migrate/   golang-migrate pairs (lab 06)
release.yaml            what runs on production, the desired state
.github/workflows/      already written; you never touch these
```

**The repo is locked down, so no funny business:**

- Main is protected: nothing reaches it without a PR, green checks and an
  approval. There is no pushing to main. We tried. It says no, even to us.
- **Two deploy channels, two triggers.** Every push to `main` lands on
  **your own test gateway** automatically, through a workflow you set up in
  Part 0. Only a change to `release.yaml` reaches the **shared production
  gateway**, and that is the one behind the lock on the door.
- **Sam or Jasper approves every PR.** Two reviewers, five of you: there
  will be a queue. Small, tidy PRs jump it.
- Deploys run on the site 7 runner: `runs-on: [self-hosted, cicd-capstone]`.
  Already configured; you only ever see it in the action logs.

**Production is real, and you get admin on it:**

- <https://cloud.mustrysolutions.com> — login `admin` / `MergeIntoMain!`.
  Have a look around before you start, and please be gentle with it:
  everyone's work lands on this one gateway.

## The mental model, before you start

One repository, two jobs. The seam between them is still a version string:

- **`projects/` and the config answer "what have we built?"** Everything the
  gateway runs lives here: the projects and the config, which includes the
  Ignition tags. A git tag like `wout@v1.0.0` marks a version: a point in
  history you can deploy. Nothing gets compiled; the deploy ships the files
  as they are at that tag. A tag that was never pushed is a release that
  does not exist.
- **`release.yaml` answers "what runs on production, right now?"** One file,
  one production gateway (site 7). You change a version number, a deploy
  happens. Nothing deploys any other way.

In the teaching you saw **option B**: split the infra part (release files,
gateway config) into its own repo, owned by another team. Both are valid.
One repo keeps this lab small.

## Pre-flight

- Accept the **contributor invite** for the repo (check your GitHub
  notifications). No fork this time.
- Clone it: `git clone git@github.com:Mustry-Academy/cicd-lab-07-multi-gateway-deploy.git`
- Open <https://cloud.mustrysolutions.com> and log in with
  `admin` / `MergeIntoMain!`. That gateway is your deploy target all lab.

### Local development — where you actually build

Production is never your dev box. The repo brings its own local stack, the
same move as every previous lab:

```bash
./scripts/setup.sh             # compose up + first-boot fix, idempotent
open http://localhost:8088     # admin / password
```

> **Coming straight from lab 06?** Shut its stack down first
> (`docker compose down` in that repo) — it holds ports **8088, 8090 and
> 5432**, all three of which this lab needs.

- **The local gateway bind-mounts the repo.** `./projects`,
  `./services/config` and `./services/modules.json` ARE the gateway's file
  tree: a save in the Designer lands in your working tree immediately, so
  `git status` is your export step. Review the diff; commit only what you
  meant to change (the `.gitignore` keeps gateway-owned noise out).
- **First boot needs one fix-up — `setup.sh` does it:** commissioning
  stamps a temporary identity into the mounted config (`temp` user source,
  rewritten `security-properties`). `setup.sh` turns that into the standard
  local identity — `default` user source, **admin / password** — and leaves
  `git status` clean. Re-run it any time; CI blocks the PR if the
  commissioning churn ever sneaks into a commit.
- **Local database:** `ignition` on `localhost:5432`
  (`ignition` / `lab07-postgres-pw`). Test your migration pairs with
  `scripts/migrate.sh up` before they ever reach the PR.
- **Referenced secrets work locally too:** `dev/secrets/` is mounted at
  `/run/secrets/` in the local gateway — the same path the file secret
  provider reads on production — with the local database's login in it.
- **Library JARs** load from `lib/core/gateway`, which can't be
  bind-mounted; copy them in once
  (`docker cp jar-files/jar/<jar> lab07-gateway:/usr/local/bin/ignition/lib/core/gateway/`)
  and restart the container.
- The loop is always: **build locally → see it in `git diff` → PR → tag →
  release.yaml → live.**

---

## We-do (instructor demos)

### Demo 1 — placing Oatmakers on the architecture map

1. The three reference architecture diagrams side by side (`architectures/`).
2. Oatmakers today: eight independent standalone gateways, no enterprise level.
3. Sketch the target live: frontend-backend per site, hub-and-spoke to central.

### Demo 2 — one release PR, end to end

1. The lab repo's `release.yaml` on screen: one file, one production gateway.
2. Bump a pinned version, open the PR, read the diff as a release note.
3. Merge and watch the deploy action pick the job up on the site 7 runner
   (`runs-on: [self-hosted, cicd-capstone]`), and what a `git revert` of
   the merge would do.

### Demo 3 — multi-site repo layouts on screen

1. Sketch option A (one repo for everything — what this lab uses) and option B
   (splits) live, against the constraints from the teaching: the vendor and
   the shared library.
2. Where the runners live: one per site, `runs-on: [self-hosted, site-4]`,
   inside the site network, no inbound access needed.

## You do (breakout rooms) — a setup, then three parts

Follows [`slides/assignment.html`](../slides/assignment.html) 1:1.

### Part 0 (±15 min) — stand up your personal test gateway

Everyone does this once, at the start, then leaves it running all afternoon.
It gives you a second local gateway that auto-deploys **every merge to
`main`**, so you can see a change land somewhere safe before it is ever
tagged for production. It reuses building blocks you already own: a
self-hosted runner (labs 03-06), a `push: [main]` workflow, and Ignition's
config modes (lab 04).

**1. Give the test gateway its own clone.** Your working clone is yours: you
will be mid-branch all afternoon, and a deploy must never yank it around.
The test gateway tracks `main` from a second, dedicated clone **next to**
your working one:

```bash
git clone git@github.com:Mustry-Academy/cicd-lab-07-multi-gateway-deploy.git ../lab07-test
```

**2. Start the provided test pair.** This is not a docker course, so the
repo already carries both halves behind a compose **profile**: a
`test-gateway` on port `8090` (booted in **dev config mode**,
`-Dignition.config.mode=dev` — the mode ships in the config export,
`services/config/resources/dev/`) and a `test-runner` for your laptop,
labelled with your name. One command:

```bash
LAB_USER=<yourname> RUNNER_TOKEN=<ask Sam or Jasper> \
  docker compose --profile test up -d
```

Registering a runner needs repo-admin rights, which contributors don't
have — that's why the registration token comes from us. It's only needed on
the FIRST start; the registration persists afterwards. Plain
`docker compose up -d` keeps starting only the dev stack; the test pair only
rides the `--profile test` flag. Your runner's label is
`[self-hosted, <yourname>-local]` — only jobs asking for that label run on
your machine.

**3. Add your own workflow file** named for you,
`.github/workflows/test-<yourname>.yml`. It triggers on push to `main`, runs
on your label and fast-forwards the **test clone** to `main` (your runner
already has it mounted at `/workspace/lab07-test`). That is all it does: the
test gateway runs in **dev config mode**, which watches the mounted files
and applies changes as they land — no restart, no scan call. The production
gateway runs in prod mode, where nothing applies until the deploy's
authenticated scan:

```yaml
name: test-<yourname>
on: { push: { branches: [main] } }
jobs:
  deploy:
    runs-on: [self-hosted, <yourname>-local]
    steps:
```

**4. PR it in like anything else** — branch, PR, green checks, approval,
merge. The only file you touched is your own workflow.

**Verify it works:** open a small PR that changes a dashboard view. Once it
merges to `main`, watch your `test-<yourname>` workflow run on your runner
and **the change appear on `localhost:8090` on its own** — no tag, no
`release.yaml` bump.

- **Observe:** the runner **label** is the whole routing story. Five people
  can each have a `push: [main]` workflow and each one deploys only to its
  owner’s test gateway. It is the same mechanism as the site-labelled
  production runner, `runs-on: [self-hosted, cicd-capstone]`.
- **Observe:** your working clone never moved. The pipeline owns the test
  clone; you own yours. That separation is exactly why the production
  gateway gets its files from a **tag**, not from somebody’s desk.

**Part 0 gate:** your `test-<yourname>.yml` merged in, your test gateway and
runner up, and a dashboard change proven to land on `localhost:8090` on its
own after a merge to `main`.

### Part 1 (±20 min) — create your project and bring it live

Everyone does this part alone. It is the full loop every deploy in this lab
uses: PR → review → tag → release.yaml → live.

**1. Clone and branch** (no fork — your branch goes to the shared repo):

```bash
git clone git@github.com:Mustry-Academy/cicd-lab-07-multi-gateway-deploy.git
cd cicd-lab-07-multi-gateway-deploy
git switch -c feature/<yourname>-project
```

**2. Add your project:** `projects/<yourname>/` with one simple Perspective
view that shows your name.

```bash
git add projects/<yourname>/
git commit -m "feat: add <yourname> project with welcome view"
git push -u origin feature/<yourname>-project
```

**3. Open the PR.** Watch the checks, then wait for Sam or Jasper to
approve. If you get review comments, address them and push again — same PR.

- **Observe:** only your project's checks run. Path-filtered CI: five people
  can open five PRs and nobody waits on anyone else's tests.

**4. Merge.**

- **Observe:** merging deployed **nothing**. Main means "built and could
  ship", not "shipped". Your project is not on production yet.

**5. Tag your release** — this is what makes the release *exist*:

```bash
git switch main
git pull
git tag <yourname>@v1.0.0
git push origin <yourname>@v1.0.0
```

- The tag is the release: a named version of your project that
  `release.yaml` can point at. Nothing gets built — the deploy will simply
  check out this tag and copy your project's files.

**6. Pin it in `release.yaml`** — new branch, one line:

```diff
 gateway: oatmakers-site-7
 projects:
   oatmakers:        v2.0.0
+  <yourname>:       v1.0.0
```

```bash
git switch main && git pull
git switch -c deploy/<yourname>-v1.0.0
git commit -am "deploy: <yourname> v1.0.0 to production"
git push -u origin deploy/<yourname>-v1.0.0
```

PR, approval, merge.

- **Observe:** the deploy action runs on the site 7 runner, checks out your
  tag and copies your project's files to the gateway. That is why the tag
  came first: `release.yaml` can only point at versions that exist.

**7. Verify live:** open <https://cloud.mustrysolutions.com>
(`admin` / `MergeIntoMain!`) and find your view.

**Part 1 gate:** your project, your tag, your line in `release.yaml`, your
view live on production.

### Part 2 (±35 min) — five challenges on the shared oatmakers project

One project, five contributors, one version stream. Everything in these
challenges is a move you made in an earlier lab; the new part is doing it
together.

**The rules:**

- All work lands in `projects/oatmakers/` plus the lab 06 folders
  (`third-party-modules/`, `jar-files/jar/`, `db-migration/`).
- **Finished means live:** merge your PR, cut the **next free**
  `oatmakers@v2.0.X` tag, bump `release.yaml` by PR.
- Five people, one version stream: **pull main often**. If someone claimed
  your tag number while you were typing, take the next one.
- Sam or Jasper still approves everything. Small PRs get through the queue
  first.

**Nick — add the Embr Charts module and build a chart screen**

- Download the module from
  <https://github.com/mussonindustrial/embr/releases/tag/releases%2F8.3%2F2026.6.17>.
- Add it to `third-party-modules/` and register it in
  `services/modules.json` with its `certFingerprint` and
  `licenseAgreementHash` — the lab 06 move. The pipeline installs it; no
  hands on the gateway.
- Build a Perspective screen with a nice chart on it.
- Verify on production: Config → Modules shows Embr Charts **Running**, and
  your chart renders.

**Stephan — use the Commons Lang3 JAR in a string reversing function**

- The `commons-lang3` JAR is **already in the repo**, in `jar-files/jar/` —
  we did the lab 06 download-and-pin move for you. Your job is to use it.
- Add a project script function that reverses a string:

  ```python
  from org.apache.commons.lang3 import StringUtils
  flipped = StringUtils.reverse("Ignition")
  ```

- Build a Perspective screen that **calls your function** and shows the
  result: **noitingI**, live on production.

**Tom — the database connection, a migration with a seed, a view on the data**

- Create the DB connection using the **referenced secret**
  `POSTGRES_USERNAME`. The secret is already on the environment: you
  reference it, you never see the value. Lab 06's secrets ladder, for real.
- Write a migration pair in `db-migration/migrate/` — `.up.sql` creates the
  tables and seeds them, `.down.sql` undoes it. **Always pairs.**
- Build a Perspective view that queries the seeded data.
- Verify on production: the connection is **Valid**, the migration ran, your
  view shows rows.

**Wout — tags and a simulator device with live values**

- Add an **OPC UA simulator device** (the programmable device simulator) to
  the gateway config.
- Create tags on it and use them on a Perspective screen.
- Deploy: the device config and the tags travel with the pipeline, like
  everything else.
- Verify on production: **values changing live**, on a gateway you never
  logged into to configure.

**Gregory — historize the live tags and build a dashboard**

- Enable **tag history** on Wout's tags, storing into Tom's database
  connection.
- Build a dashboard view visualising that history.
- You will be merging into files the others just changed. **Merge conflicts
  are part of the challenge**, not an accident.

**Part 2 gate:** your challenge is live on production through a reviewed PR,
an `oatmakers@v2.0.X` tag you cut yourself, and a `release.yaml` bump that
went through review.

### Part 3 (extra) — use each other's work

Everything from Part 2 is now shared infrastructure. This part has no
script: **work together, build fast, get through the PRs.**

- **Cross the challenges:** store more tags in the database, add to the
  migration scripts, put an Embr chart on Tom's data, call Stephan's
  function from your view. Anything goes, as long as it ships by PR.
- **Keep PRs small and fast.** One small change that merges beats a big one
  that sits in review while main moves under it.
- **Stay current:** pull main often and rebase your branch. Most merge
  conflicts die before they are born.
- **Solve the conflicts that do happen.** With five people in one project
  they will. That is not the pipeline failing you; that is the pipeline
  making the collision visible *before* production.

---

## Definition of done

Everything on this list is visible on GitHub or on the production gateway;
nothing needs your laptop.

0. **Part 0:** your `test-<yourname>.yml` workflow and `test-<yourname>`
   gateway merged in, and a dashboard change proven to land on
   `localhost:8090` on its own after a merge to `main`.
1. **Part 1:** `projects/<yourname>/` merged through an approved PR, the tag
   `<yourname>@v1.0.0` built, your line in `release.yaml`, and your view
   **live on cloud.mustrysolutions.com**.
2. **Part 2:** your challenge merged and **live on production** via an
   `oatmakers@v2.0.X` tag you cut yourself and a reviewed `release.yaml`
   bump.
3. **Part 3:** at least one merged PR that **builds on someone else's
   work**, and at least one review comment or unblock you gave someone else.

## Debrief

Bring answers:

- One repo carried five contributors to one production gateway today. When
  would you split it, like the teaching's option B — and which part would
  you split off first?
- Who may merge what at your plant, and who are your Sam and Jasper?
- What does "only validated commits reach main" mean in your organisation,
  and what enforces it?
- Who is the master of tags at your plant today (teaching Part 4), and does
  anything enforce it?
- And the course-closing question: **what will you build first, back at your
  own plant?**
