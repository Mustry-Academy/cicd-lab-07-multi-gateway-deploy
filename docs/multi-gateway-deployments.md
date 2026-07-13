# Deployments in a multi-gateway architecture

This document is the Lab 07 teaching hour written out in full. The slides
([`slides/teaching.html`](../slides/teaching.html)) are the presentation; this
is the version you can re-read.

**The framing for everything below: every situation is different.** Gateway
count, site count, team boundaries, vendors, IT constraints — no two plants
match. This lab does not hand you one right answer; it gives you the options
and the questions, so you can pick what is right for your situation and defend
the pick. We deliberately do not go deep into any single option. You already
own every building block (pipelines, self-hosted runners, file-based and
image-based deploys, secrets, db-migrations, from labs 03 to 06); what changes
with more gateways is not the deploy itself but the **routing**: which files
go to which gateway, triggered by what, in which order, and who is allowed to
decide.

Where the course left us: **one repository, one site, one logical gateway** in
three environments (local, dev, prod). Every section below is a controlled
change to that picture.

---

## Part 1 — Three reference architectures

The diagrams are in [`architectures/`](../architectures/) (Inductive
Automation's reference architectures). We stay at the map level: the goal is
to recognize the shape of your own plant, because the repository layout
follows the shape.

### Architecture 1 — standalone: one gateway does everything

Devices, tags, history, Perspective sessions: all on one gateway
(`architectures/one-gateway.png`). Most plants start here, and at the right
size it is a perfectly good place to stay.

- One box is one failure domain: PLC polling, history and every client
  session share the same CPU and the same restart.
- It strains when heavy Perspective load competes with device polling, and
  every deploy touches the box that also runs production.
- **CI/CD view:** one repo, one pipeline, one deploy target. Labs 04–06
  already built everything this architecture needs.

### Architecture 2 — frontend and backend gateways

Backend gateways own device connections, tag providers and history; a
frontend gateway owns the Perspective sessions; they talk over the gateway
network (`architectures/backend-frontend.png`).

- Why split: client sessions can no longer starve device polling, and you can
  redeploy or restart visualization without touching data collection.
- It scales: more frontends behind a load balancer, more backends per device
  group, without redesigning anything.
- **CI/CD view:** one plant, but **several deploy targets with different
  content** — projects mostly go to the frontend, device and tag config to
  the backends. The pipeline has to route. That routing is the new skill of
  this lab.

### Architecture 3 — multi-site with an enterprise level (hub and spoke)

Each site collects and runs locally; a central level aggregates history,
reporting and corporate clients
(`architectures/multi-site-enterprise-architecture.png`).

- Sites keep local autonomy: Edge or standard gateways collect and buffer at
  the plant; local clients keep working when the WAN link drops.
- The center aggregates: a central database service, enterprise reporting,
  corporate clients through load-balanced frontend gateways.
- **CI/CD view:** many targets in **different networks**. A self-hosted
  runner per site becomes the deploy agent inside each network, and "which
  version runs where" becomes a real bookkeeping problem. Both are solved
  later this hour (part 3).

---

## Part 2 — How repositories and pipelines map onto each architecture

### The baseline (labs 04–06)

```
oatmakers-repo/
├─ projects/
│  ├─ oatmakers/
│  └─ oatmakers-packaging/
├─ gateways/            # gateway config
├─ db-migration/
└─ .github/workflows/deploy.yml
```

One repository holds everything; one pipeline deploys it; one site, one
logical gateway, three environments (local → dev → prod).

### Frontend-backend: one repo, several projects, a config folder per gateway

Two gateways do not force two repositories. One repo can hold all projects
and all gateway config; the pipeline routes each piece to its gateway:

```
oatmakers-repo/
├─ projects/                  # one folder, all projects
│  ├─ oatmakers/              # HMI            → gw-frontend
│  ├─ oatmakers-packaging/    # HMI            → gw-frontend
│  └─ oatmakers-shared/       # shared library → both gateways
├─ gateways/                  # a config folder per gateway
│  ├─ gw-frontend/            # sessions, auth, gateway network
│  └─ gw-backend/             # devices, tag providers, history
└─ .github/workflows/deploy.yml
```

- Each project in `projects/` can deploy to a **different gateway**.
- `oatmakers-shared` is the library project the HMIs inherit from and the
  gateway scripts live in — it deploys to **both** gateways.
- Each gateway has its **own config folder** under `gateways/`.
- The payoff of one repo: a screen change and its tag change are **one PR** —
  reviewed together, deployed together, to two different gateways.

---

## Part 3 — The deploy mechanism: releases, promotion and the multi-site options

The architecture shows the shape; this is how anything actually moves. The
bookkeeping is a **releases folder**, usually its own small repository: one
folder per environment, one file per gateway, everything plain text under
version control. The fleet's state gets a `git log`.

```
oatmakers-releases/
├─ prod/
│  ├─ gw-site1-backend.yaml
│  ├─ gw-site1-frontend.yaml
│  ├─ gw-site4-backend.yaml
│  ├─ gw-site4-frontend.yaml
│  ├─ … sites 2, 3, 5 … 8 …
│  ├─ gw-central.yaml
│  └─ rollout.yaml          # wave ordering
├─ test/
│  └─ gw-test.yaml
└─ dev/
   └─ gw-dev.yaml           # tracks main, auto
```

One file per gateway, each project pinned to a version:

```yaml
# releases/prod/gw-site4-frontend.yaml
gateway: gw-site4-frontend
projects:
  oatmakers:           v2.0.1   # the hotfix
  oatmakers-packaging: v1.4.0
  oatmakers-shared:    v1.9.2   # shared library
```

This file **is** the record of what runs on `gw-site4-frontend`. Change the
file, and the pipeline makes it true.

`rollout.yaml` orders the waves for prod:

```yaml
# releases/prod/rollout.yaml
waves:
  - name: canary
    gateways: [gw-site4-backend, gw-site4-frontend]
    soak: 30m
  - name: fleet
    gateways: [sites 1 to 3 and 5 to 8]
  - name: enterprise
    gateways: [gw-central]
```

And dev is the deliberate exception — no pins:

```yaml
# releases/dev/gw-dev.yaml
gateway: gw-dev
track: main            # every merge deploys automatically
```

Pinning starts where humans need control: test and prod.

### A promotion is a pull request

1. **The PR:** bump `oatmakers: v2.0.0 → v2.0.1` in the canary site's
   frontend file (that is where the HMI runs). The
   diff *is* the release note: exactly what changes, exactly where.
2. **Review is the approval gate.** The reviewer approves a promotion, not
   code. Merging is the trigger; nobody logs into a gateway.
3. **Wave 1, the canary:** site 4's own runner deploys its two gateways,
   then health checks and a soak period.
4. **Later waves fan out** in `rollout.yaml` order — the fleet, then
   `gw-central` last. A failed verify in any wave stops everything after it.
5. **Rollback is `git revert`** of the release PR: the file goes back, the
   pipeline makes the old pins true again. No snowflake knowledge, no 02:00
   archaeology — the file is the state.

Dev never appears in this flow: it tracked main automatically since the merge
that started it all.

---

### Scaling to multi-site

You now hold every piece: the routing from Part 2, and the releases and
promotions from earlier in this part. Multi-site is those pieces multiplied —
the only new decisions are where the repository boundaries go, where the
runners live, and how versions are made inside a bigger repository.

### Option A — one repository deploying to every site

The same idea scaled out. One repo holds every project (including the shared
library `oatmakers-shared`), a config folder per gateway across all sites,
and the migrations:

```
oatmakers-repo/
├─ projects/
│  ├─ oatmakers/              # every site's HMI
│  ├─ oatmakers-packaging/
│  └─ oatmakers-shared/       # shared library, one copy
├─ gateways/
│  ├─ gw-site1-backend/ … gw-site8-frontend/
│  └─ gw-central/
├─ db-migration/migrate/      # runs at every site
└─ .github/workflows/deploy.yml   # matrix over sites
```

- **A self-hosted runner per site, and one at the enterprise level.** The
  workflow runs as a matrix; each site's job lands on that site's runner
  (`runs-on: [self-hosted, site-4]`), *inside* that site's network. Nothing
  needs inbound access.
- **db-migrations ship the same way:** each site's runner migrates that
  site's database before shipping the projects — exactly the lab 06 order.
- **Payoff:** the shared library is one folder in one repo — change it once
  and every site's next deploy carries it.
- **The release files from earlier in this part do the bookkeeping.** The
  repo says what exists; one file per gateway says which version runs where.

**A version tag per project.** One repo does not mean one version number. A
tag carries its project's name as a prefix, and CI treats the tag as a build
instruction, not a repo-wide stamp:

```
commit a41 ── oatmakers@v2.0.0
commit b52 ── oatmakers-packaging@v1.4.0
commit c63 ── (merge — no tag, nothing releases)
commit d74 ── oatmakers-shared@v1.9.2      ← the parent project
commit e85 ── oatmakers@v2.0.1             ← the hotfix
```

```
tag: oatmakers@v2.0.1
  → parse the prefix: "oatmakers"
  → build ONLY projects/oatmakers/
  → publish one artifact
```

The other folders are present in the checkout and completely ignored; their
version numbers don't move. Five commits, four tags, four independent version
sequences in one repository.

**The shared library is the parent project.** `oatmakers-shared` is versioned
and tagged like any other project, and every gateway runs it **next to** its
projects — the HMIs inherit from it. That is why it is pinned explicitly in
every gateway's release file:

```yaml
# releases/prod/gw-site4-frontend.yaml
projects:
  oatmakers:           v2.0.1   # its own tag
  oatmakers-packaging: v1.4.0   # its own tag
  oatmakers-shared:    v1.9.2   # the parent project, deployed alongside
```

Delivery is unchanged: release files, promotion by PR, `rollout.yaml` waves,
each site's runner delivering its own.

**One discipline: ship tested combinations only.** `oatmakers@v2.0.1` was
built and tested against whatever `oatmakers-shared` state commit `e85`
contained. Pair that artifact on a gateway with a *different* parent version
and you ship a combination that has never run together. Two mitigations:

1. **One `oatmakers-shared` version per environment.** Everything in test
   runs the same parent; everything in prod runs the same parent. What you
   tested together is what ships together, by construction. Start here.
2. **Record the dependency in the artifact.** At build time
   `git describe --tags --match 'oatmakers-shared@*'` names the parent state
   the build saw; write it into a manifest inside the artifact, and let the
   deploy refuse a gateway file that pairs the artifact with an untested
   parent (compatible-major matching, not exact-match). More machinery — add
   it the first time a site is pinned behind on the library.

### Option B — splitting into multiple repositories

Four splits, each answering a different question. Mix them freely.

1. **A repository per site, plus one for the enterprise level**
   (`oatmakers-site1` … `oatmakers-site8`, `oatmakers-enterprise`). Each site
   team owns its own repo and pipeline to its own gateways; the enterprise
   repo deploys `gw-central`. Cost: a change every site needs becomes eight
   PRs, and sites drift apart without bookkeeping.
2. **A repository per vendor project** (`palletizer-vendor`). One project,
   nothing else. The vendor works in it, and their pipeline deploys **only
   that project** to your gateways, alongside your own deploys. They never
   see the rest of the plant. Project-level deploys (lab 04) are what make
   this safe.
3. **Config repositories separate from one projects repository.** All
   projects combined in one repo keeps the shared library and cross-project
   review easy; gateway config per site lives in repos the infra team owns.
   Cost: a feature that needs both takes two PRs, in the right order.
4. **The shared library across repositories: git submodules.** If projects
   live in several repos, `oatmakers-shared` can be a git submodule: each
   repo pins a specific commit and upgrades deliberately. The pin is a
   version choice, and it shows up in the diff.

### Choosing: the trade-offs

| Layout | Strongest when | Watch out for |
|---|---|---|
| One repository for everything | One team; shared library used everywhere; a cross-gateway change should be one reviewable PR | Everyone sees everything; vendors need carve-outs; the repo grows with the fleet |
| Repository per site + enterprise | Site teams work at their own pace; access ends at the site boundary | A shared change is N PRs; sites drift apart silently |
| Vendor repository per project | External parties must contribute without seeing the plant | Disciplined project-level deploys; a clear interface contract (which tags and queries the project may expect) |
| Config repos + one projects repo | Infra and application are different teams; projects stay together for the shared library | One feature can need two PRs in two repos |

**Rule of thumb:** pick the *fewest* repositories that answer your actual
questions — who may see what, who owns what, how shared code travels.
Whatever you pick, more repos and more gateways raise the same question:
**which version runs where?** The releases folder from earlier in this part is what
answers it.

---

## Part 4 — Tag management: who is the master of tags?

Tags are the one data stream that also flows **against** the deploy
direction: they change on production, while everything else changes in Git.
Decide ownership before your first multi-gateway deploy, not after the first
overwritten setpoint.

### Two scenarios that really happen

1. **Operators change tags on production.** Night shift trims an alarm limit
   at 03:00 to stop a nuisance alarm. Saturday's deploy ships the tag export
   from Git: the limit is silently back to the old value. If operators may
   change tags on production, your deploy must not blindly overwrite them.
2. **Process engineers create tags on production.** Forty new tags, born
   directly on the prod gateway. Dev has never seen them: screens can't be
   tested against them, and a strict "make it match Git" deploy would even
   delete them. Tags born on production need a way back into dev and the
   repo.

### Three ownership models

| Model | How it works | Fits when |
|---|---|---|
| **Development is master** | Every tag change travels through the repo and the pipeline. Editing tags on production is forbidden (or exported back the same day). The deploy may overwrite the tag provider. | Tags change rarely and the dev team owns the process |
| **Production is master** | Tags are exported from prod into the repo on a schedule; the deploy never touches the tag provider; dev refreshes itself from those exports. | Engineers and operators live in the tag browser |
| **Split ownership** | Dev owns **structure** (UDT definitions, folders, new tags); production owns **values** (setpoints, alarm limits). The deploy ships definitions and never writes values — or you split by provider or folder. | Most plants — but only if the split is written down and enforced |

### The rule

There is no universal answer, but there must be **an** answer: written down,
agreed with operations, and enforced by the pipeline — what a deploy may
overwrite, what it must merge, and what it must never touch.
