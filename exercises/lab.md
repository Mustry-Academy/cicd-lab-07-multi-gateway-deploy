# Lab 07 — Deployments in a multi-gateway architecture

**Day 4 · afternoon session.** Everything so far deployed one repository to one
gateway. This lab lays out what changes when there are more: the reference
architectures, the repository layouts that map onto them, the releases folder
that records which version runs where, and the tag-ownership decision that has
to be made before any of it goes live.

**Duration:** ~3 hours

* 60 min teaching ([`slides/teaching.html`](../slides/teaching.html))
* 30–45 min we-do (below, woven into the teaching)
* 60 min you-do ([`slides/assignment.html`](../slides/assignment.html) mirrors this file)
* Debrief — this is the last lab, so the debrief also closes the course

The full teaching content is written out in
[`docs/multi-gateway-deployments.md`](../docs/multi-gateway-deployments.md);
use it to re-read anything from the hour.

## Goal

You should leave this lab able to:

- Recognize your own plant in one of the three **reference architectures**: standalone, frontend-backend, multi-site with an enterprise level
- Map a repository layout onto each architecture, and name the trade-offs: **one repo for everything**, **repo per site + enterprise**, **vendor repo per project**, **config repos split from a projects repo**
- Explain how a **shared library project** travels in each layout (one folder in a monorepo, or a git submodule pinned per repo)
- Explain where **self-hosted runners** live in a multi-site deploy (one per site, inside the site network, selected by `runs-on` labels) and why nothing needs inbound access
- Build a **releases folder**: one folder per environment, one file per gateway, each project pinned to a version, `rollout.yaml` for wave ordering, and dev tracking main unpinned
- Version projects independently inside one repository with **prefixed tags** (`oatmakers@v2.0.1` releases only that project), and say why the shared **parent project** (`oatmakers-shared`) is pinned per gateway alongside the projects, with one parent version per environment
- Run a **promotion as a pull request** in the releases repo, with review as the approval gate and `git revert` as the rollback
- Decide **who is the master of tags** (development, production, or split ownership), and write rules a pipeline can enforce

## Pre-flight

This assignment needs **no gateways and no Docker**. You need:

- A GitHub account you can create a repository on
- Your breakout room-mate added as a collaborator (they review your PRs)
- A browser or editor for markdown and yaml

---

## The scenario

All three parts work against this scenario. Copy it into `SCENARIO.md` during
the warm-up.

> **Oatmakers** runs **8 production sites**. Every site runs the same two
> Ignition projects, `oatmakers` (the HMI) and `oatmakers-packaging`, plus the
> shared library project `oatmakers-shared` that both depend on.
>
> Each site is getting a **backend gateway** (devices, tag providers, history),
> a **frontend gateway** (Perspective sessions) and a **site database**.
>
> An external **vendor** builds the **palletizer** project for sites 2 and 7.
> Contractually, the vendor **may not see anything except the palletizer
> project** — not the HMI, not the gateway config, not the other sites.
>
> Management wants an **enterprise level**: `gw-central` with a central
> database for company-wide reporting.
>
> Current versions in production: `oatmakers v2.0.0`,
> `oatmakers-packaging v1.4.0`, `oatmakers-shared v1.9.2`. A hotfix
> `oatmakers v2.0.1` has just been tagged and must be promoted: **site 4
> first** (it reported the bug), then the rest of the fleet, then central.
>
> Two incidents from last quarter, for Part 3:
>
> 1. Night shift at site 3 trimmed an alarm limit at 03:00 to silence a
>    nuisance alarm. Saturday's deploy shipped the tag export from Git and
>    silently put the old limit back.
> 2. A process engineer created ~40 new tags directly on site 6's production
>    gateway. Dev has never seen them; nothing can be tested against them; a
>    strict "make production match Git" deploy would delete them.

---

## We-do (instructor demos)

### Demo 1 — placing Oatmakers on the architecture map

1. The three reference architecture diagrams side by side (`architectures/`).
2. Oatmakers today: eight independent standalone gateways, no enterprise level.
3. Sketch the target live: frontend-backend per site, hub-and-spoke to central.

### Demo 2 — one release PR, end to end

1. A releases folder in the layout from the teaching, on screen.
2. Bump `oatmakers: v2.0.0 → v2.0.1` in `gw-site4-frontend.yaml` (the HMI
   runs on the frontend gateway), open the PR, read the diff as a release
   note.
3. Read `rollout.yaml` and narrate what the pipeline would do wave by wave,
   and what a `git revert` of the merge would do.

### Demo 3 — multi-site repo layouts on screen

1. Sketch option A (one repo for everything) and option B (splits) live,
   against the scenario's constraints: the vendor and the shared library.
2. Where the runners live: one per site, `runs-on: [self-hosted, site-4]`,
   inside the site network, no inbound access needed.

## You do (breakout rooms)

Follows [`slides/assignment.html`](../slides/assignment.html) 1:1. After the
warm-up, **everything goes through a feature branch and a PR** (GitHub flow),
reviewed by your room-mate.

### Warm-up (together) — create the design repo and place Oatmakers

1. Create `oatmakers-deployment-design` on your GitHub account (private is
   fine). Add your room-mate as collaborator.
2. Copy the scenario above into `SCENARIO.md`.
3. As a room: which reference architecture is one Oatmakers site today? Which
   is the company? What should the target be?
4. Commit `SCENARIO.md` to `main` — the last direct commit you make today.

### Part 1 (solo, ±20 min) — choose the architecture and repository layout

Branch: `design/architecture`. Deliverable: `ARCHITECTURE.md` with **all five
sections**:

```markdown
# Oatmakers deployment architecture

## Target architecture
<!-- which reference architecture per site and for the company, and 3 sentences why -->

## Repositories
<!-- a table: repo name · what's inside · who has access -->
| Repo | Contents | Access |
|---|---|---|

## Main repo file tree
<!-- projects/, a config folder per gateway, migrations, workflows -->

## Runners
<!-- site · machine · labels · which deploy jobs land on it -->
| Site | Machine | Labels | Deploys |
|---|---|---|---|

## What one deploy run does
<!-- trigger → what routes where → how it's verified -->
```

Your design must give a written answer to **both hard constraints**:

1. The vendor sees **only** the palletizer project.
2. `oatmakers-shared` reaches every project that needs it.

Open the PR; your room-mate's job is to poke one hole in the design. Answer
the hole **in the document**, then merge.

**Gate:** merged PR, five sections filled, both constraints answered in
writing.

### Part 2 (solo, ±25 min) — build the releases folder and promote v2.0.1

#### 2A — the folder

Branch: `design/releases`. Build:

```
releases/
├─ prod/
│  ├─ gw-site1-backend.yaml
│  ├─ gw-site1-frontend.yaml
│  ├─ gw-site4-backend.yaml
│  ├─ gw-site4-frontend.yaml
│  ├─ gw-central.yaml
│  └─ rollout.yaml          # wave ordering
├─ test/
│  └─ gw-test.yaml
└─ dev/
   └─ gw-dev.yaml           # tracks main, auto
```

(Sites 1 and 4 plus central are the minimum scope; the full fleet is stretch 1.)

One file per gateway, every project pinned. Each version is one of that
project's own **prefixed tags** (`oatmakers@v2.0.0` style — the tag names its
project, and CI builds only the folder the prefix names). The parent project
`oatmakers-shared` is pinned in **every** file, alongside the projects that
inherit from it. Everyone starts on `v2.0.0` — the hotfix is promoted in 2B,
not baked in here:

```yaml
# releases/prod/gw-site4-frontend.yaml
gateway: gw-site4-frontend
projects:
  oatmakers:           v2.0.0
  oatmakers-packaging: v1.4.0
  oatmakers-shared:    v1.9.2
```

```yaml
# releases/prod/gw-site4-backend.yaml
gateway: gw-site4-backend
projects:
  oatmakers-shared:    v1.9.2   # devices and tags are config; the backend
                                # runs the shared library the scripts live in
```

```yaml
# releases/dev/gw-dev.yaml
gateway: gw-dev
track: main            # every merge deploys automatically — no pins on dev
```

```yaml
# releases/test/gw-test.yaml
gateway: gw-test
projects:
  oatmakers:           v2.0.0
  oatmakers-packaging: v1.4.0
  oatmakers-shared:    v1.9.2
```

```yaml
# releases/prod/rollout.yaml — wave ordering for prod promotions
waves:
  - name: canary
    gateways: [gw-site4-backend, gw-site4-frontend]
    soak: 30m          # verify + wait before the next wave
  - name: fleet
    gateways: [gw-site1-backend, gw-site1-frontend]   # + sites 2-3, 5-8 at full scope
  - name: enterprise
    gateways: [gw-central]
```

PR, review against the checklist: every gateway has a file · the parent is
pinned in each · **the same `oatmakers-shared` version across all of prod**
(tested together = ships together) · dev is unpinned. Merge.

#### 2B — the promotion

1. **Canary PR:** branch `promote/v2.0.1-wave1`. Bump `oatmakers` to `v2.0.1`
   in **`gw-site4-frontend.yaml` only** (the HMI runs on the frontend
   gateway; the backend file doesn't pin `oatmakers` at all). Title:
   `Promote oatmakers v2.0.1 to prod (wave 1: site 4)`.
2. **Review:** your room-mate checks four things: only site 4 changed · the
   pin matches the tagged hotfix (`oatmakers@v2.0.1`) · the parent version is
   untouched · `rollout.yaml` says site 4 goes first. They approve; you merge.
3. **Narrate the machine:** as a PR comment, write what a pipeline would log:
   which runner picks the job up, what it deploys (the project **and its
   parent**, to that one site), what it verifies during the soak, and which
   gateways stay unchanged.
4. **Fleet PR:** branch `promote/v2.0.1-wave2`, bump the remaining prod files
   that pin `oatmakers` (`gw-site1-frontend.yaml` and `gw-central.yaml` in
   the minimum scope). Review, merge.
5. Read the audit trail you just created:
   `git log --oneline releases/prod/`.

**Gate:** two merged promotion PRs, each reviewed, and you can say how
rollback works (revert the PR; the pipeline makes the old pins true again).

### Part 3 (solo, ±15 min) — write the tag-ownership policy

Branch: `design/tags`. Deliverable: `TAGS.md`:

```markdown
# Tag ownership at Oatmakers

## The model
<!-- development is master / production is master / split ownership -->
<!-- 2 sentences: why this fits Oatmakers -->

## The rules (enforceable by a pipeline)
1. Who may create tags, and where:
2. What a deploy may overwrite:
3. What a deploy must never touch:
4. How tags created on production reach dev and the repo:
5. What happens to operator setpoints on deploy day:

## The cost
<!-- one honest sentence about what this model gives up -->
```

Your room-mate reviews by attacking the policy with both scenario incidents
(the 03:00 alarm limit, the 40 engineer-created tags): every rule must survive
both. Then merge.

**Gate:** merged `TAGS.md` with one model, five enforceable rules and one
honest cost.

---

## Definition of done

1. **Part 1:** `ARCHITECTURE.md` merged, five sections filled, both hard
   constraints answered in writing.
2. **Part 2:** complete `releases/` folder (every gateway in scope has a
   file, the parent pinned in each at one `oatmakers-shared` version across
   prod, dev is unpinned, `rollout.yaml` has three waves) and two merged,
   reviewed promotion PRs.
3. **Part 3:** `TAGS.md` merged and it survived both incidents in review.

## Stretch (optional)

1. **All eight sites, plus disaster recovery.** Extend `releases/prod/` to
   the full fleet and add `gw-dr.yaml`. Decide which wave DR belongs in, and
   whether it should lag prod on purpose. Write the answer into
   `rollout.yaml` as a comment.
2. **The vendor's release file.** Add the palletizer project to the site 2
   and site 7 release files with the vendor's own version numbers. Decide
   whether the vendor may open promotion PRs in your releases repo, or hands
   versions over another way. Write the rule into `ARCHITECTURE.md`.
3. **Cut the tags for real.** In your design repo, create the prefixed tags
   your release files reference: `git tag oatmakers@v2.0.0`,
   `git tag oatmakers@v2.0.1`, `git tag oatmakers-shared@v1.9.2`. Then add
   one sentence to `ARCHITECTURE.md`: what does CI do with the prefix?
   (From the teaching: parse it, build only that project's folder, publish
   one artifact.)
4. **Sketch the submodule.** In `ARCHITECTURE.md`, sketch what changes if
   `oatmakers-shared` becomes a git submodule in a repo-per-site layout:
   which repos contain it, what the pinned commit means, and what a library
   upgrade looks like as PRs. No commands needed — it's the shape that
   matters.

## Debrief

Bring answers:

- Which repository layout did your room choose, and where did you disagree?
- What belongs in a release file that we didn't include — modules, a config
  version, migrations?
- Who is the master of tags at **your** plant today, and does anything
  enforce it?
- And the course-closing question: **what will you build first, back at your
  own plant?**
