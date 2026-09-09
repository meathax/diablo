# Music skip root cause — 9 September 2026

The running ARM audio producer is paced by SDL's dummy device, independently of the FPGA's fixed 48 kHz consumption clock. SDL mixes/publishes a callback, then sleeps for the nominal buffer duration. Callback work and wakeup overhead are added to that delay. Production is slightly too slow, so the prebuffer drains. The FPGA then stops consuming until it has re-primed 8,192 frames, producing a short audible silence each time.

## Live proof

Inspected the existing running Diablo process without restarting, changing configuration, loading a core, or modifying product code. Candidate 082083dc76f53113f6fc8c6047dd1ecc74d0eb1781e25e093f4199a86d9f9113 is selected in the process environment. Target engine and RBF file hashes match the local candidate package manifest. Local audio-path source hashes also match the candidate manifest. This is newer than the candidate pointer in .mister/state.json. Hashes identify the release files; the FPGA behavior was additionally measured live.

A read-only 50-second shared-memory capture at approximately 10 ms intervals contains 4,869 samples:

- Producer rate: 47,709.86 stereo frames/second, about 0.60% below 48,000.
- Mean observed publication interval: 46.708 ms; ideal interval for 1,024 source frames at 22,050 Hz: 46.440 ms. Publication timestamps have 10 ms sampling quantization; the mean is over the full trace, not a measurement of callback execution time.
- Independently inferred FPGA consumption during uninterrupted playback: 47,997.66 frames/second, consistent with 48,000 given asynchronous queue-status publication.
- Two drain/refill events start around 13.06 and 38.28 seconds, 25.22 seconds apart.
- During each event the local queue holds at approximately 2,229, then 4,458, then 6,688 frames across multiple samples instead of decreasing. Playback resumes after the fourth callback takes the queue above 8,192. This is the RTL re-prime behavior, implying roughly 140–160 ms of silence for these events. No speaker recording was made; duration is inferred from the queue trace and RTL.
- Live log: zero callback drops/dropped frames and zero resyncs. This rules out chunk-discard backpressure or epoch resynchronization as the mechanism in this capture.

## Responsible code

- support/scripts/mister_launcher.py:473 explicitly selects SDL_AUDIODRIVER=dummy; confirmed in /proc/3332/environ.
- support/cmake/arm-transport.cmake:169–181 forces 22,050 Hz, stereo, 1,024 source frames per callback. The configured INI buffer value is overridden here.
- support/cmake/arm-transport.cmake:226–228 publishes PCM synchronously after Aulib mixes the callback.
- SDL_audio.c:736 calls the application callback; :782–785 then sleeps floor(samples*1000/frequency) milliseconds for the dummy work-buffer path. At this configuration the sleep is 46 ms, in addition to callback work, locking, and scheduling. It has no deadline correction or FPGA queue feedback. Exact local dependency excerpts are preserved in sdl-pacing-evidence.txt.
- support/reference/mister_pcm_resampler.hpp:80–83 uses a fixed 22,050-to-48,000 ratio; it does not correct the wall-clock production deficit.
- rtl/diablo_pcm_player.sv:286–294 emits zero when playback cannot pop; :304–310 stops at an empty queue and requires PRIME_SAMPLES before restarting. Diablo.sv:222 sets PRIME_SAMPLES=8192.

Increasing FIFO capacity alone cannot cure sustained rate mismatch; it only postpones the next drain. The corrective layer is producer pacing tied to absolute audio deadlines and/or FPGA queue consumption, with bounded jitter buffering. The exact share of mixing, memory-copy and scheduler time was not profiled; it is not necessary to establish the measured sustained rate deficit and refill mechanism.

## Why existing diagnostics understate it

Current rtl/diablo_pcm_player.sv:123 defines producer_has_samples as producer_sequence != fetch_sequence. Lines 293 and 316–317 gate underrun counting and snapshot capture on that condition. Consequently, empty-producer silence is mostly invisible. The count rises only briefly while new samples are fetched during re-priming, even when playback is still stopped with a nonempty local queue. The event snapshot can remain uncommitted because it additionally requires queue_depth==0.

The two audible-length refill episodes incremented the counter by only 82 and 84; those numbers must not be converted directly into total silence duration. The live event record was all zero/uncommitted. Thus a zero or small underrun count is not evidence of uninterrupted audio on this build.

## Evidence files

- live-50s.json: raw sample arrays [elapsed_seconds, producer, consumer, capacity, record_bytes, underruns, resyncs, pcm_epoch, local_queue]. Read-only /dev/mem mapping at 0x3fe00000; PCM control at offset 80.
- analysis.json: calculated rate, event transitions, and five-second queue windows.
- live-initial.txt: existing engine-log tail and configuration excerpt.
- live-snapshot.json: live PCM controls and uncommitted event snapshot at offset 424.
- target-identity.json: process transport/audio environment and release file hashes; no credentials.
- sdl-pacing-evidence.txt: exact local SDL implementation excerpts.

No fix or rebuild was performed. Diagnosis is complete for the observed periodic dropout; unrelated future audio symptoms would need their own evidence.
