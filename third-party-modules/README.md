# third-party-modules/

Third-party `.modl` files the pipeline installs on the gateway — the lab 06
move. A module lands here in the same PR that registers it in
[`services/modules.json`](../services/modules.json) with its
`certFingerprint` and `licenseAgreementHash`; CI fails the PR if the two
disagree. The deploy ships the binaries, rewrites the gateway's manifest, and
restarts the gateway only when something actually changed.

Nick's Part 2 challenge (the Embr Charts module) is the first entry here.
Where the two trust values come from is the lab 06 move — the module and the
gateway will tell you; this README won't.
