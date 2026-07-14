# The capstone gateway — a real, shared deploy target

Reference reading for the capstone. Short on purpose: this page tells you what
the shared gateway is and how your pipeline reaches it. Everything about how
the server itself is built and operated lives with the instructors.

## 1. What it is

Throughout the labs you deployed to gateways running on your own laptop. The
capstone ends differently: your pipeline ships to a **real Ignition 8.3
gateway on a real server with a public IP**, shared by the whole cohort.

|  |  |
|---|---|
| Gateway web UI | https://cloud.mustrysolutions.com |
| Runs | Ignition 8.3, standard edition, instructor-managed |
| Your access | Through your pipeline, and the web UI to see the result |

## 2. How your pipeline reaches it

The same way it reached your lab gateways — nothing new to learn, which is
the point:

- Your capstone repo gets a **self-hosted runner** (provided by the
  instructors) that can reach the gateway.
- Deploys authenticate with an **Ignition API token**, handed to you as a
  GitHub **environment secret** (`IGNITION_API_KEY`) — the Lab 04/06
  mechanism: ship files, trigger a scan, smoke-check.

## 3. Ground rules

- **No credentials in Git.** Same iron rule as Lab 06 — on a shared gateway a
  leaked secret is everyone's problem, not just yours.
- **No admin access.** You don't get the gateway admin password or SSH to the
  server; if something needs an admin (a database connection, a module), ask
  an instructor. If your deploy can't do something without admin rights,
  that's a design signal — pipelines deploy with scoped tokens, not root.
- **Shared machine.** Name your project after your team; don't touch other
  teams' projects.

## 4. Why you can't just SSH in (and why that's the lesson)

The server accepts key-only SSH from instructors, exposes exactly three
ports (SSH, HTTP, HTTPS), and the gateway itself sits behind a TLS reverse
proxy — it never faces the internet directly. The gateway's own stack is
deployed the same way you deploy projects: from a Git repo, through a
pipeline, with secrets kept out of version control. In other words: the
infrastructure under your capstone practices what the course preaches.

Curious how the server itself is built? The whole stack is in this repo under
[`capstone/`](../capstone/) — compose file, TLS proxy, deploy workflow,
runbook and security model. Reading it after the course is a worked example
of everything the labs taught, applied to the infrastructure you deployed to.
