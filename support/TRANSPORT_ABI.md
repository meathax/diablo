# ARM–FPGA transport ABI

`support/transport/transport_abi.json` is the one source for the transport's
fixed layout. `generate_transport_abi.py` produces the C++ view used by the ARM
wrapper and the SystemVerilog constants used by the FPGA. Generated output must
be current before a build or test. The current ABI identity is major `1`, minor
`1`; changing checksum interpretation increments the minor identity so an old
peer cannot silently treat the new flags as equivalent.

The ABI defines an offset layout within a region supplied and owned by the
MiSTer platform. It deliberately has no absolute DDR address and does not open
`/dev/mem`. A target mapping backend may attach only after it has verified a
platform reservation of at least `SHARED_BYTES`, mapping alignment and cache/DMA
coherency. The native test pattern remains independent until that hardware proof
exists.

| Region | Offset | Size | Owner / use |
| --- | ---: | ---: | --- |
| Control page | `0x000000` | 4 KiB | Identity, epochs, queue control, frame ownership and fault state |
| Three indexed frame slots | `0x001000` | 912 KiB | ARM writes only a free slot; each slot contains 640×480 indices and an RGB888 palette |
| Input events | `0x0E5000` | 8 KiB | FPGA/Main producer, ARM consumer; snapshot recovery accompanies overflow |
| Stereo S16 PCM ring | `0x0E7000` | 128 KiB | ARM producer, FPGA consumer; capacity is not the playback target |
| Command records | `0x107000` | 64 KiB | ARM producer, FPGA consumer |
| Command payload | `0x117000` | 192 KiB | Referenced by bounded command records |

The first software command-renderer format is implemented in
`support/reference/mister_command_renderer.hpp`. Each fixed 32-byte record is
executed in order and currently supports clipped `FillRect`, overlap-safe
`CopyRect` and `End` (which carries a 64-bit completion fence); the buffer is bounded at 2,048 records and rejects an
unsupported opcode or capacity overflow. This establishes the CPU reference
semantics before command publication and FPGA execution are added. Evidence:
`.mister/evidence/software-command-renderer-test-20260907.json`.

`support/reference/mister_command_transport.hpp` publishes the fixed records and
payload bytes with the same epoch and bounded-cursor rules as the other ARM
rings. It writes payload data first, applies a release fence, then publishes the
record cursor; wrap and full-ring cases are covered by the host test. The
`diablo_command_consumer` RTL now validates both rings, executes clipped indexed
fills and overlap-safe copies through a supplied target pixel base, accepts target
slots 0–2 at the ABI's 311,296-byte stride, acknowledges consumer cursors and
publishes completion fences. Randomized busy/read-delivery backpressure is
covered by its RTL fixture. The consumer is now instantiated behind the top-level
arbiter with audio/input priority preserved, and the integrated RBF has passed
Quartus timing; controlled DevilutionX scene submission remains a separate gate.
Evidence:
`.mister/evidence/software-command-transport-test-20260907.json` and
`.mister/evidence/fpga-command-consumer-test-20260907.json` and
`.mister/evidence/fpga-command-consumer-build-20260907.json`.

The final packed-fill RTL was rebuilt and loaded as
`Diablo_command_consumer_rectmerge64_20260907.rbf` (SHA-256
`4142126272d5b8613b990e6ecc5c25687e9c4c54d8a2c9d37fe7508bae4a77f5`). FillRect
rows are emitted as aligned 64-bit byte-enable writes; the ARM scene builder
also coalesces identical changed runs vertically. A real ARM DevilutionX scene
publisher drove the command ring while the FPGA consumer executed it: the fresh
dummy-SDL timedemo rendered 140 frames at 12.1 FPS and the no-reload relaunch
rendered 127 frames at 11.1 FPS, with command cursors equal, completed fences and
`arm=1`, `fpga=1`, `fault=0` in both state dumps. Physical HDMI, vblank, speakers,
controllers, deterministic full-scene equality and zero-underrun audio remain
separate gates. Evidence:
`.mister/evidence/arm-command-scene-live-hardware-20260907.json`.

The minimum reservation is 2 MiB. Unused tail space is intentionally reserved
for compatible expansion, not available to an endpoint. Every offset and size is
validated before use; no descriptor can address past the attachment.

Each session begins with a new nonzero epoch. The ARM clears and initializes the
control page, writes all pixels and palette entries, issues a release fence, then
moves the slot from `ArmWriting` to `Ready`. The FPGA acquires `Ready`, changes
it to `FpgaDisplaying`, and may return it to `Free` only after the scanout path
has switched away at a known vblank boundary. A reset, unknown epoch, malformed
descriptor or queue overflow makes the affected endpoint fault/quiesce rather
than reuse uncertain memory.

## Control-page publication and health ownership

`magic` is the control page's publication marker. The ARM clears it while it
initializes every identity, epoch and descriptor field, issues a release fence,
then writes the complete magic value last. The FPGA must not accept any other
field until it has read that complete marker. This prevents a reset-time reader
from attaching to a partially initialized page.

The 64-bit status word at control offsets `0x20..0x27` is split by ownership:
the ARM owns `arm_state` in bytes `0x20..0x23`, and the FPGA owns `fpga_state`
in bytes `0x24..0x27`. FPGA status writes must assert only byte enables
`0xf0`, even when reporting a fault. They must preserve the ARM half while the
ARM is publishing or replacing a session. Fault code and detail use their own
full 64-bit word at offsets `0x28..0x2f`.

The implemented bounded reader retries after a fault so a valid ARM publication
can recover without an FPGA reload. Its board receipt proves clean attachment,
malformed-magic rejection and stale-slot rejection at the selected MiSTer
reservation.

The implemented C++ view checks mapping size/alignment, layout identity, epochs,
ring dimensions, slot bounds and frame ownership. It includes host-side models
of the ARM/FPGA transitions so stale sessions and displayed-buffer reuse are
rejected. The RTL check consumes a C++ walking-bit fixture and verifies byte
order, offsets and record fields. It does not substitute for target cache
maintenance, real DDR visibility or a hardware reset test.

## Indexed framebuffer scanout

`rtl/diablo_framebuffer_scanout.sv` polls only the fixed 64-bit descriptor
fields, claims the newest same-epoch `Ready` slot using the FPGA-owned state
lanes, and copies its 256-entry RGB888 palette into local dual-port M10K. Pixel
data remains in the ARM-owned shared-DDR slot and reaches `ascal` through its
dedicated 128-bit f2h-DDR port. This avoids a per-frame copy through the core's
single 64-bit control port.

The scanner changes `FB_BASE` only at `FB_VBL`, enables indexed 640x480 scanout
only after the palette is committed, and frees the former displayed slot at the
same vblank that activates the pending slot; ordered ownership writes complete
before the slot can be reclaimed. The hardware receipt proves cold-boot attachment,
two ARM-published frames claimed by FPGA scanout, and safe reuse of the retired
slot. It proves protocol state transitions and timing closure; HDMI image
inspection, game rendering, audio and input remain separate validation work.

The control reader now rechecks the publication marker, session epoch and ARM
component state while attached. A changed session detaches and runs the existing
bounded full validation, so a second ARM launch can reattach without reloading the
RBF. At the vblank that activates a pending frame, the scanout immediately
retires the former displayed slot and writes its display epoch,
`last_presented_frame_id` and the header display epoch using the FPGA-owned byte
lanes, preserving the ARM producer epoch. The control reader accepts that
nonzero FPGA-owned display epoch while still validating the ARM-owned producer
epoch. The final Quartus build and board
display-ack receipt are `.mister/evidence/fpga-transport-display-ack-build-20260906.json`
and `.mister/evidence/transport-display-ack-hardware-20260906.json`.

## Stereo PCM queue

The PCM ring contains little-endian four-byte records: signed 16-bit left then
signed 16-bit right. The ARM owns `producer_sequence` and writes every sample
before releasing its new sequence. The FPGA validates ring capacity, record
size and epoch; it owns `consumer_sequence` and writes only that upper 32-bit
half of the control word (`ddram_be=0xf0`).

The FPGA local FIFO holds 1,024 stereo records (21.33 ms at 48 kHz) in bounded
block RAM, fetches two records per 64-bit DDR read, and publishes consumer
progress in 32-record batches (at most 0.67 ms of producer-visible delay),
flushing a short final batch when the producer cursor is caught up. Periodic
control polls refresh only the ARM producer cursor; they never rewind the FPGA
prefetch cursor. The shared core DDR arbiter locks every outstanding read
response to its requester and gives this bounded audio traffic priority over
descriptor/palette reads. Indexed pixels still use the scaler's dedicated
f2h-DDR port, so PCM cannot displace the video pixel stream. A starvation or
invalid sequence outputs silence and increments an underrun or resynchronization
counter; it never reuses uncertain samples.

The transport-aware ARM audio overlay hooks the pinned SDL_audiolib callback.
The ARM mixer stays at 22.05 kHz to avoid making the game-thread audio mix pay
the full 48 kHz cost; the callback performs a stateful linear upsample to 48 kHz
stereo and publishes contiguous PCM bytes through ArmPublishPcmBytesFast. This
fast producer checks only the session epoch and ring occupancy after attachment,
then copies the wrapped ring segments and release-publishes the producer cursor.
A fresh-RBF real-engine smoke logged 4,457-4,458 output frames per callback with
no PCM backpressure and arm=1, fpga=1, fault=0. Evidence:
.mister/evidence/arm-audio-pcm-transport-20260907.json and
.mister/evidence/arm-engine-transport-audio-build-20260907.json.

The audio-enabled 90-second timedemo reached 2,611 frames in 89.68 seconds
(29.1 FPS), with 23 rate-limited frame fallback notices, no PCM backpressure and
no transport fault. The current 1,024-sample RBF was compiled with Quartus
17.0.2, loaded on MiSTer, and exercised by the real ARM process; active samples
kept `pcm_resyncs=0` but recorded nonzero underruns. The board SDL binary has no
ALSA target, so physical left/right output and zero-underrun qualification are
still unavailable. Combined shared-DDR stress, real-vblank frame pacing and the
approximately 60 FPS target also remain open. Evidence:
`.mister/evidence/fpga-pcm-fifo1024-build-20260907.json`,
`.mister/evidence/arm-fpga-pcm-fifo1024-hardware-20260907.json`,
`.mister/evidence/arm-audio-driver-probe-20260907.json`,
`.mister/evidence/arm-engine-transport-audio-timedemo-20260907.json` and
`.mister/evidence/arm-pcm-health-20260907.json`.

## Input event ring

The input ring is a 256-record, 32-byte circular queue at `0x0E5000`. The FPGA
owns the low `producer_sequence` half of the input control word and the ARM owns
the high `consumer_sequence` half. A producer publication uses `ddram_be=0x0f`
only after all four record words are visible. The FPGA polls the consumer cursor
periodically, so an ARM consumer can reclaim space without racing an event write.

Each record is four little-endian 64-bit words:

| Word | Low 32 bits | High 32 bits |
| --- | --- | --- |
| 0 | sequence | capture timestamp (core-clock ticks) |
| 1 | event type | event code |
| 2 | signed value 0 | signed value 1 |
| 3 | joystick/button snapshot low 32 bits | snapshot high 32 bits |

Event types are `1=keyboard`, `2=mouse`, `3=joystick`, and `4=focus`. Keyboard
codes carry the extended bit and scan code; mouse codes carry packet buttons and
wheel, with signed X/Y deltas in values 0/1; joystick events carry signed left
and right analog words and the current 32-bit joystick button mask; focus events
carry the two MiSTer menu/reset button bits in value 0. The FPGA advances the
source baseline only once per captured edge, preserving a later change while a
record is being written.

When `producer_sequence-consumer_sequence` reaches 256, the FPGA never
overwrites an unread record. It drops the edge and increments its diagnostic
overflow counter in `RingControl::dropped`; the ARM can read that monotonic
counter with `ArmInputDropped`, refresh `InputSnapshot` and establish a new
consumer cursor before relying on subsequent deltas. This bounded drop path is
covered by the RTL and ABI tests; physical keyboard/mouse/controller traffic and
the ARM snapshot recovery are still board-validation work.

The generated ARM view exposes `ArmConsumeInput`, which acquire-loads the FPGA
producer, copies complete records in sequence order, and release-publishes the
ARM consumer cursor. A cursor gap larger than capacity returns
`AttachError::InputOverflow` without consuming anything. The caller then writes
the current `InputSnapshot` with `ArmRecoverInput`; that operation records the
snapshot sequence and advances the consumer to the observed producer in one
ordered recovery step.

The transport-aware SDL adapter now calls this consumer from the frame-present
path and converts the records into SDL keyboard, mouse, joystick and focus events.
MiSTer joystick buttons are mapped to DevilutionX's keyboard-controller actions;
mouse position is accumulated and clamped to the native 640x480 surface, while
PS/2 set-2 make/break codes preserve key edges. The fresh-RBF ARM smoke with the
deterministic input injector logged keyboard, mouse and joystick records in the
real engine and kept both endpoints ready without a transport fault. Evidence is
`.mister/evidence/arm-input-sdl-bridge-20260907.json`.

The injector is a validation fixture only. A deliberate 257-record overflow now
reaches the real ARM adapter, which logs `input overflow recovered` and
resynchronizes the consumer cursor to the producer; the receipt is
.mister/evidence/arm-input-overflow-recovery-20260907.json. Physical
peripheral capture, OSD focus, disconnect/reconnect and input-to-visible latency
remain target qualification work.

## ARM runtime mapping and indexed publisher

`support/reference/mister_transport_runtime.hpp` is the target mapping backend.
It accepts either a file-backed `DIABLO_MISTER_SHARED_PATH` fixture for QEMU or an
explicit `DIABLO_MISTER_SHARED_PHYS` physical base for MiSTer. It refuses to map
without one of those inputs, checks the full two-megabyte aperture, attaches the
generated ABI, creates a nonzero session epoch and flushes the control page with
`msync` or the ARM synchronization barrier required by an `O_SYNC` device mapping.
The physical address is therefore deployment configuration backed by the DDR
reservation receipt, not an ABI constant.

`support/reference/mister_transport.hpp` provides `TransportSession`, a bounded
indexed-frame publisher. It strips the SDL source pitch into a 640×480 slot,
copies the 768-byte RGB888 palette, computes a source-side diagnostic checksum and
publishes only a free slot. The default checksum samples one byte in sixteen plus
the complete palette to keep the ARM frame path bounded; set
`DIABLO_MISTER_FULL_CRC=1` when a full-pixel CRC is required for diagnostics. If all
three slots are owned by the FPGA it returns backpressure rather than overwriting a
displayed or in-flight frame. The runtime validates the complete ABI once during
attachment; the indexed hot path then uses epoch/state-only ownership checks to
avoid repeated uncached descriptor reads. The SDL adapter waits once for FPGA
readiness, makes at most two 1 ms retries for an occupied pipeline, then returns to
the engine's SDL pacing authority so a stalled vblank cannot turn into a long CPU
sleep. This preserves ownership safety but can drop a presentation attempt until a
slot is free; the latest 20-second board smoke recorded six rate-limited fallback
notices and no transport fault. A fresh-RBF 90-second timedemo recorded 24 notices,
2,650 frames in 89.08 seconds (29.7 FPS), and no transport fault. The final
display-ack smoke recorded four notices in 15 seconds, no startup wait expiry,
`arm=1`, `fpga=1`, `fault=0`, `display_epoch=0x9e` and
`last_presented_frame_id=159`. The ARM engine build and target receipts are recorded in
`.mister/evidence/arm-engine-transport-build-20260906.json`,
`.mister/evidence/arm-engine-transport-hardware-20260906.json`,
`.mister/evidence/arm-engine-transport-nonblocking-20260906.json` and
`.mister/evidence/arm-engine-transport-timedemo-20260906.json`; the final FPGA
and board receipts are `.mister/evidence/fpga-transport-display-ack-build-20260906.json`
and `.mister/evidence/transport-display-ack-hardware-20260906.json`.

The input-enabled ARM rebuild was remeasured on a fresh RBF for 90 seconds: 2,635
frames in 89.04 seconds (29.6 FPS), 24 bounded fallback notices and no transport
fault. The result is consistent with the earlier nonblocking path and remains below
the real-vblank and approximately 60 FPS targets. Receipt:
`.mister/evidence/arm-engine-transport-input-timedemo-20260907.json`.

The current immediate-retirement image and profile-enabled ARM overlay were then
measured twice on the board. The runs ended with `arm=1`, `fpga=1`, `fault=0`
and published 926/1033 and 908/1001 presents at 29.2 and 28.3 FPS. The profile
records bounded present durations and backpressure; the image retires the old
slot at the activation vblank and accepts the FPGA-owned display epoch. Dummy
SDL and active PCM underruns keep physical HDMI/audio, real-vblank pacing and
the approximately 60 FPS qualification open. Evidence:
`.mister/evidence/fpga-frame-retire-immediate-build-20260907.json` and
`.mister/evidence/arm-engine-transport-present-profile-20260907.json`.

The stage-level profile then separated indexed publish work from the shared
memory barrier. On the same RBF, 1,235 publish attempts averaged 4,882
microseconds, while 1,013 flushes averaged 1 microsecond and peaked at 20
microseconds; the timedemo reached 991 frames in 34.61 seconds (28.6 FPS) and
ended with `arm=1`, `fpga=1`, `fault=0`. This identifies publish/copy work and
bounded backpressure as the present bottleneck; it does not close physical
video/audio/input or the approximately 60 FPS gate. Evidence:
`.mister/evidence/arm-engine-transport-present-profile-breakdown-build-20260907.json`
and `.mister/evidence/arm-engine-transport-present-profile-breakdown-20260907.json`.

The publisher also has an opt-in `DIABLO_MISTER_DIRTY_COPY=1` mode. It keeps a
cached source shadow per slot, writes changed runs and uses a whole-row fallback
when a row is busy. A paired dummy-SDL board run measured 3.432 ms average
publish and 29.3 FPS enabled versus 4.413 ms and 28.3 FPS disabled, with
`arm=1`, `fpga=1`, `fault=0` in both cases. It remains opt-in pending broader
scene and real-vblank measurements. Evidence:
`.mister/evidence/arm-dirty-copy-ab-20260907.json`.

`FrameSlot::flags & FRAME_CHECKSUM_KIND_MASK` identifies what `crc32` means:
`FRAME_CHECKSUM_ABSENT` means no comparison value is supplied,
`FRAME_CHECKSUM_SAMPLED_CRC32` means CRC-32 over the documented one-column-in-16
pixel sample plus the complete RGB888 palette, and
`FRAME_CHECKSUM_FULL_CRC32` means CRC-32 over every indexed pixel plus the complete
palette. A nonzero checksum with the absent kind is invalid, as is an unknown flag
bit. The checksum is diagnostic metadata only; complete equality qualification must
read back and compare every indexed pixel and palette byte. The generated ABI
publisher requires callers to pass the checksum kind explicitly, so command/direct
frame paths can declare absence instead of making a zero checksum look verified.
