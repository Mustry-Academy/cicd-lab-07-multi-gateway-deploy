# Lab 07 — Deployments in a multi-gateway architecture

**Day 4 · afternoon session.** One exercise, end to end: you ship a real change
through a two-repo pipeline — tag a project, watch CI build exactly that
project, deploy it by pull request through dev → test → prod, then change the
shared parent project and watch the pipeline protect you from shipping an
untested combination.

**Duration:** ~3 hours

* 60 min teaching ([`slides/teaching.html`](../slides/teaching.html))
* 30–45 min we-do (below, woven into the teaching)
* 60–75 min you-do ([`slides/assignment.html`](../slides/assignment.html) mirrors this file)
* Debrief — this is the last lab, so the debrief also closes the course

The full teaching content is written out in
[`docs/multi-gateway-deployments.md`](../docs/multi-gateway-deployments.md);
use it to re-read anything from the hour.

<!-- TODO(infra): the two lab repos and their CI are not built yet. Needed:
     - ignition-projects: projects/{oatmakers-shared,oatmakers,oatmakers-packaging}/
       seeded with history and tags (oatmakers@v1.9.0/v2.0.0,
       oatmakers-packaging@v1.3.0/v1.4.0, oatmakers-shared@v1.9.0/v1.9.2),
       published artifacts for the current tags, plus a prepared BREAKING
       oatmakers-shared@v2.0.0 tag the instructor hands out in Part 4
     - ignition-projects CI: path-filtered tests per project; tag build that
       parses the prefix, builds only that folder, writes manifest.json
       (project/version/commit/requires) into the artifact; impact report
       posted on PRs that touch oatmakers-shared
     - ignition-gateways: gateways/{dev/gw-dev,test/gw-test,
       prod/gw-oatmakers-01,prod/gw-oatmakers-02}/release.yaml + rollout.yaml
     - ignition-gateways CI: plan posted on every PR; deploy on merge (pull
       artifact, ship, smoke test); topological ordering (parent before
       children); manifest guard (block major parent mismatch, allow
       compatible minor); second-approver rule scoped to prod/**
     - .ci/matrix.py (versions per gateway grid) and .ci/show-manifest.py
     - compose stack: four gateways + runner, sized for course laptops -->

## Goal

You should leave this lab able to:

- Read the fleet's state from the gateways repo (`matrix.py`) and explain why **the YAML file, not the gateway, is the source of truth**
- Ship a change to one project and watch **path-filtered CI** build and test only that project
- Explain why **merging is not deploying**: main means "built and could ship"
- Cut a **prefixed tag** (`oatmakers@v2.0.1`) and watch CI parse the prefix, build one folder, publish one artifact
- Read an artifact's **manifest** and say what `requires` records, and why
- Deploy by PR: a **one-line version bump** in a release file, a plan on the PR, merge as the trigger
- Promote dev → test → prod as **the same version moving through a sequence of files** — environments are directories on main, not branches
- Execute a **staged prod rollout** (one gateway first) and read the resulting drift in the matrix
- Change the **parent project** and watch: every child tested, an impact report on the PR, parent-first deploy ordering, children's versions untouched
- Explain how the **manifest check** refuses an untested parent/child combination, and why a compatible minor passes while a major is blocked

## What you're working with

Two repos, already set up for you. **The pipelines are already written. You
will not be writing CI today. You will be using it, and watching what it
does.**

`ignition-projects` contains three Ignition projects:

```
projects/
  oatmakers-shared/     inheritable parent. utility scripts, common styles.
  oatmakers/            the main site project. parent: oatmakers-shared
  oatmakers-packaging/  the packaging line project. parent: oatmakers-shared
```

`ignition-gateways` holds the desired state of every gateway:

```
gateways/
  dev/gw-dev/release.yaml
  test/gw-test/release.yaml
  prod/gw-oatmakers-01/release.yaml
  prod/gw-oatmakers-02/release.yaml
rollout.yaml
```

## The mental model, before you start

Two repos, two different jobs:

- **`ignition-projects` answers "what have we built?"** You merge, you tag, an
  artifact is published. This repo does not know gateways exist.
- **`ignition-gateways` answers "what is actually running, right now,
  where?"** You change a version number in a YAML file, and a deploy happens.

The seam between them is a **version string**. That's it. Nothing else
crosses.

The single most important thing to internalise today: **the gateway is not
the source of truth. The YAML file is.** If they disagree, the YAML file is
right and the gateway is wrong, and the drift detector will say so.

## Pre-flight

- Fork both repos, **Actions enabled** (same setup as labs 04–06).
- `cp .env.example .env` → `scripts/setup.sh` → the four gateways and the
  runner come up. `scripts/validate.sh` green before you start.
- You need a room-mate: the prod deploy requires a **second approver**.

---

## We-do (instructor demos)

### Demo 1 — placing Oatmakers on the architecture map

1. The three reference architecture diagrams side by side (`architectures/`).
2. Oatmakers today: eight independent standalone gateways, no enterprise level.
3. Sketch the target live: frontend-backend per site, hub-and-spoke to central.

### Demo 2 — one release PR, end to end

1. A releases folder in the layout from the teaching, on screen.
2. Bump `oatmakers: v2.0.0 → v2.0.1` in a release file, open the PR, read the
   diff as a release note.
3. Read `rollout.yaml` and narrate what the pipeline would do wave by wave,
   and what a `git revert` of the merge would do.

### Demo 3 — multi-site repo layouts on screen

1. Sketch option A (one repo for everything) and option B (splits) live,
   against the constraints from the teaching: the vendor and the shared library.
2. Where the runners live: one per site, `runs-on: [self-hosted, site-4]`,
   inside the site network, no inbound access needed.

## You do (breakout rooms) — one exercise, four parts

Follows [`slides/assignment.html`](../slides/assignment.html) 1:1.

### Part 1 (±10 min) — see the current state

Clone both repos and look at what's running.

```bash
git clone <url>/ignition-projects.git
git clone <url>/ignition-gateways.git

cd ignition-gateways
python .ci/matrix.py
```

You should get something like:

```
                  oatmakers-shared   oatmakers   oatmakers-packaging
gw-dev                 v1.9.2          v2.0.0          v1.4.0
gw-test                v1.9.2          v2.0.0          v1.4.0
gw-oatmakers-01        v1.9.2          v2.0.0          v1.4.0
gw-oatmakers-02        v1.9.2          v2.0.0          v1.4.0
```

Everything aligned. Enjoy it, it won't last.

Now look at the tags in the projects repo:

```bash
cd ../ignition-projects
git tag --list
```

```
oatmakers@v1.9.0
oatmakers@v2.0.0
oatmakers-packaging@v1.3.0
oatmakers-packaging@v1.4.0
oatmakers-shared@v1.9.0
oatmakers-shared@v1.9.2
```

Notice: **three independent version sequences in one repo.** `oatmakers` is
on v2.0.0 while `oatmakers-packaging` is on v1.4.0. They do not move
together. The tag prefix is what tells CI which project to build.

Confirm that:

```bash
git show oatmakers@v2.0.0 --stat
git log --oneline oatmakers@v1.9.0..oatmakers@v2.0.0 -- projects/oatmakers/
```

### Part 2 (±15 min) — ship a change to one project

You're going to fix something in `oatmakers` **only**. Nothing else should
move.

```bash
git switch -c fix/oatmakers-alarm-label
```

Open `projects/oatmakers/` and make a small, visible change. Change an alarm
label, a view title — whatever your instructor points you at.

```bash
git add projects/oatmakers/
git commit -m "fix: correct alarm label on line 2 overview"
git push -u origin fix/oatmakers-alarm-label
```

Open the PR. Watch the CI checks.

- **Observe:** only `oatmakers` tests run. `oatmakers-shared` and
  `oatmakers-packaging` are not built, not tested, not touched. That's
  path-filtered CI. In a poly-repo you'd get this for free; here you get it
  *and* you keep everything in one place.

Merge the PR.

- **Observe:** merging to main did **not** deploy anything. Main means
  "built and could ship," not "shipped." Nothing has moved yet.

Now tag it:

```bash
git switch main
git pull
git tag oatmakers@v2.0.1
git push origin oatmakers@v2.0.1
```

- **Observe:** the tag triggers a build. Watch the CI job parse the prefix
  `oatmakers`, build only that project, and publish `oatmakers-v2.0.1.zip`.

Check the artifact's manifest:

```bash
# from the CI artifact, or:
python .ci/show-manifest.py oatmakers v2.0.1
```

```json
{
  "project": "oatmakers",
  "version": "v2.0.1",
  "commit": "a3f9c21",
  "requires": { "oatmakers-shared": "v1.9.2" }
}
```

- **This is the important bit.** The build recorded which `oatmakers-shared`
  it was compiled and tested against. Remember this. It comes back in Part 4.

Still nothing has deployed. You have an artifact. That's all.

### Part 3 (±20 min) — deploy it, dev → test → prod

Now switch to the gateways repo. This is where deploys happen.

```bash
cd ../ignition-gateways
git switch -c deploy/oatmakers-v2.0.1-dev
```

Edit `gateways/dev/gw-dev/release.yaml`:

```diff
 gateway: gw-dev
 projects:
   oatmakers-shared:    v1.9.2
-  oatmakers:           v2.0.0
+  oatmakers:           v2.0.1
   oatmakers-packaging: v1.4.0
```

One line. Commit, push, open a PR.

```bash
git commit -am "deploy: oatmakers v2.0.1 to dev"
git push -u origin deploy/oatmakers-v2.0.1-dev
```

- **Observe:** the PR check runs a **plan**. It tells you exactly what will
  change on which gateway *before* you merge. Read it.

Merge.

- **Observe:** now it deploys. Watch the pipeline pull
  `oatmakers-v2.0.1.zip`, push it to gw-dev, and run the smoke test. Open the
  dev gateway and confirm your change is live.

The pattern you just executed: **the PR is the deploy request. The approval
is the change control. The merge is the trigger.**

Now promote to test. Same move, different file:

```bash
git switch main && git pull
git switch -c deploy/oatmakers-v2.0.1-test
# edit gateways/test/gw-test/release.yaml, same one-line bump
git commit -am "deploy: oatmakers v2.0.1 to test"
git push -u origin deploy/oatmakers-v2.0.1-test
```

- **Notice what promotion is:** the same version number moving right through
  a sequence of files. Not a merge between branches. **Environments are
  directories, all on main.** If you'd made them branches, you'd now be
  cherry-picking and fighting merge conflicts between dev and prod. You
  aren't.

Merge. Then prod, **one gateway only**:

```bash
# edit gateways/prod/gw-oatmakers-01/release.yaml
```

- **Observe:** the prod PR requires a **second approver**. Get your room-mate
  to approve it. Note that this rule is path-based — it applies to `prod/`
  and not to `dev/`.

Merge, and watch it deploy to gw-oatmakers-01 **and only that one**.
gw-oatmakers-02 is untouched. That's staged rollout: least critical first,
bake, then the rest.

```bash
python .ci/matrix.py
```

```
                  oatmakers-shared   oatmakers   oatmakers-packaging
gw-dev                 v1.9.2          v2.0.1          v1.4.0
gw-test                v1.9.2          v2.0.1          v1.4.0
gw-oatmakers-01        v1.9.2          v2.0.1          v1.4.0
gw-oatmakers-02        v1.9.2          v2.0.0  ←       v1.4.0
```

Drift is now visible. **That's the point of the matrix.**

### Part 4 (±15 min) — change the shared library

This is the interesting part.

```bash
cd ../ignition-projects
git switch -c feat/shared-timestamp-util
```

Add a function to `oatmakers-shared`'s script library. Something both
`oatmakers` and `oatmakers-packaging` could use.

```bash
git commit -am "feat: add format_shift_timestamp to oatmakers-shared"
git push -u origin feat/shared-timestamp-util
```

Open the PR. Now watch the CI carefully.

- **Observe:** this time, `oatmakers-shared` tests run **and so do
  `oatmakers` and `oatmakers-packaging` tests**. A change to the parent is a
  change to every child. CI knows this because they're in one repo and it can
  see the whole graph.
- **Observe:** the **impact report** posts on the PR. It statically scans
  every project for call sites of anything you touched. Read it. This is the
  thing that answers "I cannot possibly know what I just broke."

Merge and tag:

```bash
git switch main && git pull
git tag oatmakers-shared@v1.10.0
git push origin oatmakers-shared@v1.10.0
```

Deploy to dev. In `gateways/dev/gw-dev/release.yaml`:

```diff
-  oatmakers-shared:    v1.9.2
+  oatmakers-shared:    v1.10.0
   oatmakers:           v2.0.1
```

- **Observe the deploy ordering.** The parent must land before its children.
  Watch the pipeline topologically sort and deploy `oatmakers-shared` first.
  If it deployed `oatmakers` first, `oatmakers` would briefly reference a
  library that isn't there.
- **Observe what you did NOT have to do:** you did not bump `oatmakers` or
  `oatmakers-packaging`. Their versions are unchanged. The library moved;
  they didn't. Independent version sequences.

And note: this deploy **passed** the manifest check, even though
`oatmakers@v2.0.1` was built against `v1.9.2`. A compatible **minor** bump
(v1.9.2 → v1.10.0) is allowed. Semver doing its job.

**Now break it.** Ask your instructor for the breaking
`oatmakers-shared@v2.0.0` tag, and try to pair it with `oatmakers@v2.0.1` on
`gw-oatmakers-01`:

```
✗ gw-oatmakers-01
  oatmakers@v2.0.1 was built against oatmakers-shared@v1.9.2
  gateway declares oatmakers-shared@v2.0.0
  Major version mismatch. This combination has never been tested.
```

**This is the payoff for the manifest.** The artifact remembered what it was
built against, and the pipeline refused to ship a combination nobody has
ever run. Without this, that deploy succeeds and breaks at 2am.

---

## Definition of done

1. **Part 1:** you can read the matrix and name the three independent version
   streams in one repo.
2. **Part 2:** a merged PR, the tag `oatmakers@v2.0.1`, one published
   artifact whose manifest records `requires: oatmakers-shared v1.9.2` — and
   **nothing deployed**.
3. **Part 3:** v2.0.1 live on dev, test and gw-oatmakers-01 through three
   one-line PRs; the prod PR carries a second approval; gw-oatmakers-02 still
   runs v2.0.0 and `matrix.py` shows the drift.
4. **Part 4:** `oatmakers-shared@v1.10.0` live on dev, deployed **before**
   its children, with the children's versions untouched — and the
   major-version deploy **refused** by the manifest check, with you able to
   explain the error message line by line.

## Stretch (optional)

1. **Finish the rollout.** Promote v2.0.1 to `gw-oatmakers-02`, and read
   `rollout.yaml`: write one sentence in the PR on why gw-01 went first.
2. **Roll back.** `git revert` the gw-oatmakers-01 deploy PR and watch the
   pipeline put v2.0.0 back. Nobody logs into a gateway; the file is the
   state.
3. **Read the plan like an operator.** Open any merged deploy PR and
   reconstruct from its plan + logs exactly what changed, where, when, and
   who approved it. That's your audit trail — no archaeology.

## Debrief

Bring answers:

- The seam between the two repos is a version string. What else at your plant
  currently crosses that seam, and should it?
- Who at your plant should be able to merge in `ignition-gateways`? Is it the
  same list as `ignition-projects`?
- Where would the vendor from the teaching fit: which repo, which paths,
  which approvals?
- Who is the master of tags at your plant today (teaching Part 4), and does
  anything enforce it?
- And the course-closing question: **what will you build first, back at your
  own plant?**
