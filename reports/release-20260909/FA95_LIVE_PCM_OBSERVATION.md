# fa95 live PCM observation

Read-only state dump during the untimed full-Diablo session. No reset,
transport write, or game shutdown performed.

- ARM ready=1, FPGA ready=1, fault=0; epoch `0x3d7e4be9`.
- Current PCM producer=consumer=7641407; local queue=1340;
  underruns=27425; resyncs=0. Frame display sequence is active.
- Latched starvation event commit=3, matching epoch, cycle=2850833953:
  producer=fetch=consumer=6760906; local queue=0; underruns=20182;
  player state=`0x000007c8`; arbiter=`0x1000000000000081`.

At this recorded event the FPGA had fetched every sample the observed
producer sequence advertised. This supports investigating producer supply or
stream transitions, rather than assuming an unfetched DDR backlog. It does
not prove the cause, exclude delayed producer publication, or establish
audible impact. The deployed RTL counts empty sample ticks, not distinct
glitches. Current queue recovery does not erase the captured starvation.

The utility was built from `support/transport/transport_state_dump.cpp` with
the recorded GCC 15.2 ARM cross compiler and deployed only as
`/tmp/fa95-live-state-dump-arm`. Its shared-memory mapping is read-only.

## Producer investigation

The ARM callback mixes through SDL_audiolib and immediately calls
`PublishPcmBytes`. Publication failures count dropped frames; observed health
reports have zero dropped frames. A read-only task snapshot found the
`SDLAudioP2` thread in `hrtimer_nanosleep` (not proof of its state at starvation).
The retained SDL audio loop uses a relative buffer-duration `SDL_Delay` after
callback work when using its work buffer. Callback cost and scheduling can
therefore affect cadence independently of the FPGA clock. This is a hypothesis
requiring actual format/cadence evidence, not a confirmed root cause or a
reason to change the running session yet.
