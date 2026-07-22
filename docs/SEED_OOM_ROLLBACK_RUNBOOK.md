# Runbook: seed node OOM-killed mid-deploy, rollback aborted

## What this covers

A `tools/deploy_seed.sh` run fails its test gate, the automatic rollback
itself fails partway through, and the seed is left with `netcoin-node.service`
down and no working source on disk. This happened for real on seed3
(18.226.74.252) on 2026-07-22 deploying commit `1680b77`.

## How to recognize it

- `systemctl status netcoin-node.service` shows `inactive (dead)` with
  `Result: oom-kill`, or the service keeps auto-restarting and immediately
  dying again.
- The deploy log shows a wall of `F`s partway through the pytest run, then
  `Killed` and `!! tests failed; rolling back source`.
- Immediately after that: `rm: cannot remove '.../netcoin-v2/netcoin':
  Directory not empty` (or similar) — the rollback's own `rm -rf` failed,
  and because the script runs under `set -euo pipefail`, that failure
  aborted the script **before** it restored the previous source or
  restarted the service. `/opt/netcoin/netcoin-v2` is left half-empty
  (usually just a stray `__pycache__`).

This exact failure mode is fixed in `tools/deploy_seed.sh` as of the commit
that added this runbook — the rollback now renames the broken tree aside
(a single atomic op that can't fail the way a recursive delete can) instead
of `rm -rf`-ing it in place, and every step in the rollback path is
best-effort so a cleanup failure can never block the actual restore or
service restart. New deploys should self-heal from this specific failure.
This runbook is for older systemd state, or if some other partial-failure
mode shows up that the fix doesn't cover.

## Root cause (not a code regression)

Check whether the *other* seeds passed the same commit's test suite first.
If they did, this is almost certainly seed-specific resource pressure, not
a bug in the deployed code:

```bash
free -h
swapon --show
sudo dmesg | grep -i 'killed process' | tail -20
```

Known contributing factors seen in the wild:
- **No swap configured** on a memory-constrained instance (~1GB RAM). Any
  burst above physical RAM is an instant hard kill instead of graceful
  degradation.
- **`/tmp` as a size-capped tmpfs sitting at 100% full** from accumulated
  `mktemp -d` staging/backup directories and uploaded deploy zips from past
  runs, never cleaned up. This eats directly into the same RAM budget the
  test run and node need. `tools/deploy_seed.sh` now clears artifacts older
  than 2 hours automatically at the start of every run, but a box that's
  been neglected for a while may still need one manual cleanup.
- **A runaway/crash-looping unrelated OS process** (seen: `fwupd-refresh`
  repeatedly OOM-killed and respawned by systemd, burning ~130MB each cycle
  on a box that has none to spare).

## Recovery steps

1. **Restore working source from the deploy's own backup.** Every deploy
   saves the pre-deploy tree to a fresh `mktemp -d` before touching
   anything (logged as `Saving current source for rollback -> /tmp/tmp.XXXX`).
   If that directory is still present:
   ```bash
   sudo rm -rf /opt/netcoin/netcoin-v2
   sudo cp -a /tmp/tmp.XXXX/netcoin-v2 /opt/netcoin/netcoin-v2
   sudo chmod -R a+rX /opt/netcoin/netcoin-v2
   ```
   If it's gone, fall back to a `netcoin-v2.bak-*` snapshot under
   `/opt/netcoin/` (older, but a full known-good tree).

2. **Restart and health-check:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start netcoin-node.service
   curl -s http://127.0.0.1:28444/info   # expect {"ok": true, ...}
   ```
   If it OOM-kills again immediately (`Mem peak` far below what a normal
   node needs), the box itself is out of headroom — go to step 3 before
   retrying the deploy.

3. **Fix the resource pressure** (only if step 2 recurs):
   ```bash
   # Add swap if none exists
   swapon --show   # empty output = no swap
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

   # Free a full /tmp tmpfs
   df -h /tmp
   sudo find /tmp -maxdepth 1 -name 'tmp.*' -exec rm -rf {} +
   sudo rm -rf /tmp/pytest-of-root

   # Stop a crash-looping unrelated service if dmesg shows one
   sudo systemctl stop <unit>.timer <unit>.service
   sudo systemctl disable <unit>.timer
   sudo systemctl mask <unit>.service
   ```

4. **Retry the deploy** once the node is confirmed healthy and stable:
   ```bash
   sudo bash /opt/netcoin/netcoin-v2/tools/deploy_seed.sh --zip /tmp/netcoin-<sha>.zip
   ```

## Prevention checklist for new seeds

- Provision with swap from day one, sized at least to the instance's RAM.
- Confirm `/tmp` has enough headroom for two full source-tree copies plus
  the venv/test run's own scratch usage — not just the zip upload.
- Don't assume every seed has identical hardware; a box that's fine for
  seed1/seed2 can still be too tight for the full test suite if it's
  smaller or has less free memory at deploy time.
