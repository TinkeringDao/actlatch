# Adapter contracts and next implementation slices

The scaffold contains no live adapter. Importing any core module must remain
free of network, SDK construction, model loading, and hardware effects.

| Adapter | Required contract | Evidence before enabling |
|---|---|---|
| Robot edge | Pinned identity; one owner; independent stop; generation-tagged output | Actual Wireless control/media reconnection, mute, and buffered-audio tests |
| ASR | Local German transcription; uncertainty returned separately from text | Actual microphone/room/child speech evaluation with minimal retention |
| TTS | Local reviewed German voice; bounded chunks; cancel by generation | Audible tail and phoneme/letter/number clarity measurements |
| Local model | Explicit model alias, bounded context/output, no hosted fallback | German quality, tool-format, and non-thinking-template checks under normal load |
| Dialog gateway | Isolated profile; authenticated bridge; exact owned session | Effective tool/credential scope, cancellation, and duplicate-dispatch tests |
| Learner store | Opaque IDs; narrow approved observations; expiry/correction | Authorization, deletion, logs, and backup-retention checks |
| Memory broker | Isolated authorization and local processing for every operation | Retain completion/recall plus server-worker egress and operation-payload lifecycle |

The proposed `reachy-companion/0.1` envelope is not an upstream robot or voice
protocol. The current parser supports only activity selection and session stop.
It validates shapes/lifetimes; it does not authenticate, maintain a replay cache,
or dispatch commands. Those belong in the future bridge with explicit tests.

SDK command WebSocket, WebRTC media, Hugging Face realtime, Seeed Realtime V2, and
custom JSON-RPC bridges are distinct protocols. Replacing a URL does not translate
them. Negotiate sample rates/channels/frame sizes, expiry, and bounded backpressure.

Implement one cached German bench interaction first. Then connect local speech,
one isolated dialog session, and narrow learner continuity in separate reviewed
slices. Hold camera/motion until the media and stop paths are measured. Physical
or privacy faults must stop commissioning rather than trigger firmware resets.
