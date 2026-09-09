# Music pacing fix status

The source fix is implemented. The FPGA's buffered audio demand now controls mixing, replacing one chunk per SDL dummy callback. Each wakeup refills toward 8,192 frames using at most four chunks. Both DDR and local FIFO occupancy count toward that target. An early wakeup does not advance the mixer; a late wakeup can mix several chunks. This corrects sustained rate mismatch without discarding samples or changing pitch.

The lifecycle reader now covers demand, mixing and publication together. Faulted, stale-epoch, unavailable and already-buffered paths do not advance the mixer. Ordinary non-transport playback retains its original callback path.

Validation completed before the user's build hold:

- Production adapter regression passed: 64 lifecycle cycles, concurrent shutdown admission, startup priming, full DDR/local queues, fault and stale-epoch rejection.
- Old pacing reproduced starvation (854 underflow steps in the deterministic slow-clock test).
- New pacing had zero underflows with slow and fast wakeups plus recurring 100 ms stalls. Minimum simulated buffered frames were 2,351 and 1,263. Sample publication totals matched all mixed source frames within resampler rounding.
- ARM engine build passed. This finished before the user instructed the agent to wait. No FPGA build was needed or run.
- Source diff whitespace check passed.

The new engine has NOT been deployed or tested on the MiSTer. The running game and installed package were not changed by this fix task. No claim of verified audible resolution is made yet.

**Hold:** no further builds or deployment until the user explicitly says to proceed. No build processes remained running when checked. Next authorized step is candidate packaging and a live queue trace covering several previous dropout intervals; confirm a stable bounded lead, no periodic drain/re-prime, no dropped PCM, and unchanged presentation behavior.

Exact source hashes and test receipt are in status.json. The original before-fix trace and diagnosis are in the parent report directory.
