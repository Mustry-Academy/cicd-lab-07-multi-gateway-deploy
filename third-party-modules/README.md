# third-party-modules/

Third-party `.modl` files the pipeline installs on the gateway — the lab 06
move. A module lands here in the same PR that registers it in
[`services/modules.json`](../services/modules.json) with its
`certFingerprint` and `licenseAgreementHash`; CI fails the PR if the two
disagree. The deploy ships the binaries, rewrites the gateway's manifest, and
restarts the gateway only when something actually changed.

Nick's Part 2 challenge (the Embr Charts module) is the first entry here.
For reference, the values lab 06 recorded for Embr (same signer, so the
fingerprint should match; verify the license hash against what the gateway
logs if it refuses the module):

```json
"certFingerprint": "e5a3cf3f06627c175b68b0122ac8f2c3f9c992e2",
"licenseAgreementHash": 3266212556
```
