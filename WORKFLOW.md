# TOUCHLINE — BUILD & DEVELOPMENT WORKFLOW (memory-aware)

**Why this file exists.** This workspace has ~1.9 GB RAM (no swap by default), 2 vCPUs,
but ~20 GB free disk. The old approach ran heavy Gradle/Chaquopy builds here, hit the
memory ceiling, and ended in repeated Java-kill/clean/rebuild loops. This workflow is
restructured so the environment is never the bottleneck.

> **Note on "the 20 GB environment":** the 20 GB is this machine's free **disk**, not a
> separate 20 GB-RAM box. There is no second environment reachable from this workspace
> (no SSH target is provisioned). Everything below runs in this one environment, tuned
> to its real limits. If a real 20 GB machine is ever provisioned (SSH access), the
> `android/` build moves there unchanged — same scripts, same caches — and this file's
> "build" phase simply points at it.

---

## Environment facts (measured)

| Resource | Value | Implication |
|---|---|---|
| RAM | 1.9 GB (+3 GB swap, added via `/swapfile`) | JVM heap capped at 900 MB; single worker |
| vCPUs | 2 | no parallel compilation |
| Disk | ~20 GB free | caches live on disk, not RAM |
| Python | 3.13 (`/usr/local/bin/python3`) | engine tests run natively here |
| Node | 20.x | `tests/ui_sanity.js` runs natively here |
| Toolchain | JDK 17 + Gradle 8.9 + SDK 34 in `/usr/local` | `sh android/setup_toolchain.sh` (once per fresh machine) |

**Swap is the load-bearing fix.** Without it, a build peak > ~1.4 GB triggers the OOM
killer mid-build (the old "kill Java and start over" loop). With 3 GB swap, peaks just
slow down. Setup (idempotent):

```sh
sudo dd if=/dev/zero of=/swapfile bs=1M count=3072
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

---

## Phase map

| Phase | Where | Cost | What |
|---|---|---|---|
| 1. Inspect | workspace | trivial | clone `--depth 1`, read docs, `git log`, tree walk |
| 2. Profile | workspace | trivial | `tests/perf_probe.py` (real HTTP, temp DB), `cProfile` on `tick_day` |
| 3. Fix | workspace | trivial | targeted edits only — no rewrites, no deletions |
| 4. Verify (sim) | workspace | ~5 min | `season_test` / `smoke` / `live_match` / `order_effect` / `ui_sanity` |
| 5. Build APK | workspace (tuned) | ~10–20 min cold, **~3–5 min warm** | `cd android && ./make_apk.sh` |
| 6. Verify APK | workspace | ~1 min | apksigner/aapt2 + asset spot-checks in the built APK |
| 7. Ship | network | trivial | commit + push + GitHub release; only the APK leaves this box |

Everything "heavy" in phases 1–4 is actually lightweight here because the game's engine
is pure-stdlib Python (world build ~1.7 s, a full 3-season sim ~4 min). The only
genuinely heavy step is the Gradle/Chaquopy build, and it is configured for it.

---

## Gradle build configuration (do not "improve" without re-reading this)

`android/gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx900m -XX:MaxMetaspaceSize=320m -Dfile.encoding=UTF-8
org.gradle.daemon=false        # no resident JVM — memory returns to the system after each build
org.gradle.parallel=false      # 2 cores; parallel workers double peak RSS
org.gradle.caching=true        # disk-backed local build cache: reuse .so/dex/aapt outputs
org.gradle.workers.max=1       # cap peak RSS (no parallel dex/ndk processes)
```

Rules of engagement:

1. **Never `gradle clean`.** The build cache (`/usr/local/gradle-home/caches/build-cache-1`)
   makes warm rebuilds minutes-fast. Wiping `app/build` is fine; wiping the Gradle cache is not.
2. **Never raise the heap** to "fix" slowness — it moves the OOM wall up, it doesn't remove
   it. If a build is slow, profile it; if it crashes, the config above + swap is the fix.
3. **Single variant only.** `assembleDebug`, `abiFilters "arm64-v8a"` — already minimal.
4. **Toolchain lives in `/usr/local`, not the repo.** Repo stays lean; `setup_toolchain.sh`
   is one-shot and idempotent.
5. **The game is not duplicated in git.** `make_apk.sh` stages `fm/` + `static/` + a pristine
   `world.seed.db` into the build tree at build time and `__pycache__` is stripped.

---

## Performance work — what was found (2026-09-11)

Profiling (`tests/perf_probe.py` + `cProfile` on `tick_day`) showed the in-game "clunk"
was the **matchday CONTINUE tap**: the world-simulation matchday tick cost 350–420 ms on
desktop (≈1.2–2 s on a mid-range phone via Chaquopy), vs ~30 ms on ordinary days.

Root causes (all in `fm/engine.py` / `fm/world.py`, no API/UI changes):

1. **Global cache invalidation every day.** `tick_day` ended with a worldwide `bump()`,
   invalidating every club's cached squad rows + best-XI strength — even though each club
   only plays one match per week. Fixed with a **structural content hash** per club
   (`squad_hashes`): one batched DB query per matchday verifies all 430 playing clubs;
   a club is only recomputed when something structural (injury, transfer, promotion,
   age-up) actually changed. Pure fatigue/fitness drift is excluded on purpose — it feeds
   only the small "condition" multiplier; letting it go up to a week stale shifts AI
   expected goals by <1%, far below the sim's own Poisson noise.
2. **Goal distribution re-read every scoring team's squad from the DB** and re-parsed
   attribute strings per goal (23,794 parses/matchday). Now reuses the cached squad rows
   and precomputes the goal/assist weight vectors per team — **RNG call sequence is
   byte-identical, so results are unchanged**.
3. **`unpack_attrs` re-parsed the same attribute string thousands of times** — now a
   memoized parse (fresh dict per call, so mutation-safe).
4. **Redundant sorts** in best-XI selection (rows already come back `ORDER BY ca DESC`).
5. **`complete_transfer` did a global cache bust ~3×/day** from world transfer activity —
   now invalidates only the two affected clubs (`bump_clubs`).

Measured effect (same machine, same seeds):

| Metric | Before | After |
|---|---|---|
| Warm matchday tick (desktop) | 350–420 ms | **100–129 ms** |
| Cold matchday tick (desktop) | ~360 ms | ~350 ms |
| 3-season integration run | 283 s | **250 s** |
| League goal-rate drift (per division) | — | ≤ ±0.08 goals/match |
| `live_step` (live match) p50 | 8 ms | 10 ms (unchanged, was never the problem) |

All test suites pass: `season_test` (3 seasons), `smoke`, `live_match` (full e2e),
`order_effect` (statistical proof touchline orders still change outcomes),
`ui_sanity` (21 screens / 52 handlers / 17 hooks).

Reproduce:

```sh
python3 tests/perf_probe.py            # hot-path timings through the real HTTP API
python3 tests/season_test.py WXC 3     # deterministic 3-season integration
```

**Deliberately NOT done** (would be a rewrite, not an optimization): Kotlin/native
rewrites of any screen or system. The UI layer (`fm/static/app.js`) was audited — it
renders incrementally with a paced 240 ms loop and 1–8 ms screen payloads; the lag was
100% in the Python matchday tick, and it is now fixed at the source.

---

## If a build still misbehaves

1. Read `/tmp/apk_build.log` first — 90% of failures are a missing SDK package or a
   dependency download hiccup, not memory.
2. Memory: `free -h` while it runs. If swap usage climbs past ~2 GB, the build is doing
   more than this project should; check for stray daemons (`ps aux | grep java`) and
   stop them, don't kill the build.
3. Stale state: `rm -rf app/build app/.gradle` (never `/usr/local/gradle-home/caches`).
4. First run on a truly fresh machine: `sh android/setup_toolchain.sh` (JDK17 export
   happens *after* the JDK download — a fresh-machine bug fixed 2026-09-11).
