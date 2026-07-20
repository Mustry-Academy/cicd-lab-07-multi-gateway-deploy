# Windows / WSL setup

Read this once, before Lab 02. It takes five minutes and prevents the file
permission problems that otherwise cost you half a lab.

If you are on macOS or Linux, you can skip this page.

## The one rule that matters

**Clone the lab repos inside the WSL filesystem, not on your Windows drive.**

```bash
# Good — the Linux side, fast and permission-clean
cd ~
git clone <lab-repo-url>
cd <lab-repo>
code .            # opens VS Code connected to WSL

# Bad — the Windows side, causes permission errors
cd /mnt/c/Users/<you>/Documents
git clone <lab-repo-url>
```

Anything under `/mnt/c`, `/mnt/d` and friends is your Windows disk seen through
a translation layer. There, file ownership is decided by Windows, not by your
WSL user, so:

- `chmod` and `chown` appear to succeed but do not stick,
- Docker bind mounts lose permission bits,
- the gateway container and your WSL user disagree about who owns a file,
- and the only thing that seems to help is running WSL as a Windows
  administrator, which hides the problem and makes the next lab worse.

`scripts/setup.sh` refuses to run from those paths and tells you how to move.

You can tell where you are at any time:

```bash
pwd
# /home/you/cicd-lab-04-...   -> good
# /mnt/c/Users/you/...        -> move it
```

To move an existing clone:

```bash
mv /mnt/c/Users/<you>/<lab-repo> ~/<lab-repo>
cd ~/<lab-repo>
scripts/setup.sh
```

## Never use sudo for the labs

If a lab command fails with "permission denied", `sudo` is the wrong fix.
Every file `sudo` creates is owned by root, which is what causes the *next*
permission error. `scripts/setup.sh` refuses to run under `sudo` for that
reason.

The two legitimate uses of `sudo` in this course are installing packages
(`sudo apt install ...`) and the one-off repairs `setup.sh` asks permission for.
Nothing else.

If you already ran something with `sudo` and now have root-owned files, just
re-run `scripts/setup.sh` — it detects them and offers to hand them back to you.

## Docker Desktop

Docker must be usable from WSL without `sudo`:

1. Docker Desktop → Settings → Resources → **WSL integration**
2. Enable integration for your distro
3. Apply & restart

Check it:

```bash
docker run --rm hello-world
```

If that needs `sudo`, integration is not set up correctly. Fix it there rather
than working around it.

## Enable metadata on Windows drives (optional)

Only relevant if you keep *other* projects on `/mnt/c`. It lets Windows-drive
paths store Linux ownership at all:

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[automount]
enabled = true
options = "metadata,umask=022,fmask=011"
EOF
```

Then, from PowerShell:

```powershell
wsl --shutdown
```

Reopen your terminal. `scripts/setup.sh` offers to write this for you.

## Checking your setup

From any lab repo:

```bash
scripts/test-preflight.sh
```

That verifies the checks themselves. To confirm your actual machine is sane:

```bash
pwd                                    # must NOT start with /mnt/
docker run --rm hello-world            # must work without sudo
scripts/setup.sh                       # must run without sudo
git status                             # must be clean, no permission errors
```

## Why the gateway no longer runs as root

Earlier versions ran the Ignition container as `root`, so every file it wrote
into `projects/` and `services/config/` was root-owned and you needed `sudo` to
edit your own project files.

The container now runs as the image's own user (uid 2003) with your group added,
and `setup.sh` makes the bind-mounted directories group-writable. Files the
gateway writes stay editable by you.

If you have gateway data volumes from an earlier run, they still contain
root-owned files and the gateway will fail to start with:

```
Property file 'data/gateway.xml' exists, but isnt readable or writable.
```

`scripts/setup.sh` detects and repairs that automatically. If you would rather
start clean:

```bash
scripts/teardown.sh --volumes
scripts/setup.sh
```
