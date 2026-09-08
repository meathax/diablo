# SDL transport ownership

The adapter owns the transport runtime, one input reconciler, and one PCM
resampler. Component extraction is in progress under C34; it does not establish
physical qualification or release acceptance.

| Owner | State and operations | Calling context |
| --- | --- | --- |
| `Adapter` | Atomic shared runtime, callback admission, transition generation, reset requests, DDR polling/publication and flush | Main thread; audio publication also takes callback admission and a shared runtime reference |
| `InputReconciler` | Desired/delivered keys and buttons, modifiers/text, focus, failed-event reconciliation and mouse position | Main thread only |
| `PcmResampler` | Fixed input/output buffers, fractional position, previous stereo sample and observed reset generation | One serialized SDL audio callback only |
| `CommandFrameState` | Pixel shadows/validity, next slot/fence, pending submission and fault state | Main thread; command owner borrows runtime per operation |
| `TransportProfiler` | Outcome and command counters, timing distributions, bounded trace storage and trace publication | Main thread; no runtime or DDR access |

The lifecycle thread requests audio reset by advancing an atomic generation. It
does not mutate the resampler. After callback admission, the callback reads the
generation and resets interpolation history when it changes. The returned PCM
span borrows the resampler's fixed buffer until the next conversion. The adapter
publishes it before returning from the callback. Ring backpressure still drops
the converted chunk and records that drop; it does not rewind interpolation.

Input polling and runtime flush remain in the adapter. The reconciler neither
maps DDR nor owns a runtime. Focus loss and transport discontinuity use event
reconciliation; initialization/shutdown use the existing state-reset operation.
Independent component instances do not share desired/delivered state. SDL's
event queue remains a process-wide external resource.

The host regression verifies existing input behavior, independent input owners,
64 input reset cycles, PCM chunk-boundary byte equality, 64 generation resets,
and malformed callback rejection. These checks do not prove concurrent SDL
callback safety, physical audio quality or target endurance.

CommandFrameState cannot be copied, so pending ownership and pixel buffers cannot
accidentally be duplicated into another owner. Reset clears shadow validity,
slot/fence selection, pending submission and fault state together. It is valid
only after lifecycle quiescence or epoch rebind; it is not timeout recovery.
The existing timeout path still faults the live slot and retains pending
ownership until reconciliation. Command publication, fence reconciliation, timeout faulting and shadow updates
now live in CommandFrameState. Runtime is passed by shared-reference argument
for each synchronous call; the owner does not retain a runtime between calls. TransportProfiler now owns
metrics and trace output; Adapter retains runtime flush and reports its timing.
Trace capacity, outcome names, no-overwrite publication and failure reporting are
unchanged. Target profiling overhead still requires measurement.
