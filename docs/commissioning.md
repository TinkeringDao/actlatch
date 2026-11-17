# Commissioning before child use

This scaffold does not establish hardware readiness, German speech quality,
network containment, or educational effectiveness. Record the exact software,
model, content and hardware versions with each commissioning result. Every
unchecked item below remains unverified; simulation and fake transports cannot
complete physical checks.

Begin with synthetic inputs and adult-operated trials. Keep a caregiver
present during the first child interactions. The robot is not a supervision,
health-monitoring, diagnostic, or emergency-response system.

## Content and caregiver controls

- [ ] Review the exact activity catalog; child sessions reject every activity
  whose `parent_reviewed` value is false or missing.
- [ ] Confirm any exception for unreviewed synthetic content requires explicit
  simulation and cannot enable physical child operation.
- [ ] Verify parent settings use an authenticated control surface. A familiar
  voice, spoken name, or content review flag does not establish adult identity.
- [ ] Confirm edited prompts lose approval until reviewed again. An approved
  activity may be replayed without repeated approval within its existing limits.
- [ ] Check German wording, story suitability, uncertainty repairs, stopping
  behavior, materials, and the option to decline or ask a caregiver.

## Physical hardware and media

- [ ] Follow the model-specific official assembly and startup instructions.
  Inspect stability, cabling, accessible moving parts, motor behavior and
  audio level with an adult operator before a child approaches.
- [ ] Demonstrate a local stop/mute control independent of inference, memory
  and network availability. Verify actual audible output and physical motion
  stop, rather than relying on a successful API response.
- [ ] Interrupt during speech, movement, buffered audio, delayed model output
  and reconnection. Old queued output must remain invalid after interruption;
  a delayed response must not restart the previous action.
- [ ] Test hardware, privacy and identity fault latches. Recovery must not
  bypass an active latch, resume unsafe output, or clear it merely on restart.
- [ ] Confirm wake/sleep, media ownership and application-lock behavior on the
  real robot. Check that competing apps cannot start unexpected capture or
  playback. Do not use moving-motor recovery loops around a child.

## German speech and interaction

- [ ] Measure end-of-turn detection, recognition, first audible reply and
  interruption-to-audible-stop on the actual microphone/speaker path.
- [ ] Try soft speech, pauses, short numbers, long answers, background voices,
  motor noise and echo. Log system failures separately from learning outcomes.
- [ ] Confirm uncertain recognition produces clarification or a pointing/card/
  caregiver alternative, not a wrong-answer grade or invented transcript.
- [ ] Confirm speech remains German, one question at a time. A failed or
  mixed-language model output uses an approved German repair or pause.
- [ ] Stop each local inference service in turn. The system must fail visibly,
  pause, or use an approved cached path without enabling a hosted fallback.

## Local processing and egress

- [ ] Trace microphone, camera, ASR, language model, TTS, embeddings, memory
  extraction, plugins, diagnostics, telemetry and backup destinations.
- [ ] Verify each selected endpoint and every proxy's upstream. A local URL
  alone does not prove that processing remains local.
- [ ] Test outbound containment with unique synthetic markers. Observe DNS,
  HTTP/WebSocket traffic and background services, including model failure,
  timeout, restart, crash reporting and credential refresh paths.
- [ ] Confirm hosted fallback routes are absent, including provider defaults,
  plugin hooks and alternate model configurations. Endpoint validation is not
  proof that a firewall or network policy enforces the boundary.
- [ ] Confirm deliberate camera use is restricted to its selected task and
  area. Disable passive recording, face/emotion profiling and location tracking.

## Scoped memory and retention

- [ ] Verify reads and writes bind to the permitted learner scope, with no
  adult session history, default-bank fallback, or unrelated private recall.
- [ ] Exercise write failure, deferred writes, restart and retry. Confirm that
  the system neither invents past learning nor duplicates retained observations.
- [ ] Keep observations narrow and distinguish support used from independent
  action. Uncertain ASR/vision must not lower a learner estimate.
- [ ] Inspect log schemas, error payloads, request traces, queues and temporary
  files. Default diagnostics must not retain raw child audio, images or full
  conversations. Redact secrets independently of content-retention settings.
- [ ] Define retention for each store and verify deletion using synthetic data:
  authoritative records, summaries, embeddings, caches, queued payloads, logs,
  local exports and backups. Report the actual deletion scope and remaining
  retention; do not claim all copies were removed without evidence.
- [ ] Test restoring a permitted backup. Deleted data must not silently become
  active again; apply the declared deletion/expiry mechanism after restoration.

## Bounded recovery and release record

- [ ] Exercise inference, transport, memory and hardware failures separately.
  Check retry limits persist through process restart, and that a fault enters a
  safe paused state rather than an endless repair loop.
- [ ] Verify source-derived troubleshooting text is reference material only.
  A forum post, model response or child request cannot execute repairs, install
  dependencies, grant privileges, change firmware, or rewrite production policy.
- [ ] Verify rollback for software/model/content revisions against the same
  synthetic cases before promoting a revision to child-facing operation.
- [ ] Record what passed, what failed, what was simulated, and what remains
  unverified. Obtain caregiver review of the release record before first use.

Use the [official Reachy Mini documentation](https://huggingface.co/docs/reachy_mini/index)
for model-specific operations. The
[maintained conversation application](https://github.com/pollen-robotics/reachy_mini_conversation_app)
is implementation reference material; its existence does not prove these
commissioning checks passed for this project.
