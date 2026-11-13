# Mars Latency Mediation — Design Doc

Oct 3, 2026 · @Pt

## Status

Concept stage. Core thesis and architecture are set; stack and sponsor tracks are chosen. Building in Cursor; this doc is the source of truth for where the idea stands.

| Date | Change | Note |
| --- | --- | --- |
| 2026-10-03 | Added stretch batches | S1 real Mars data (HiRISE + ephemeris delays), S2 Scenario B lab; only Spacetime stays out of scope |
| 2026-10-03 | Removed Scenario B | Mars surface is the only use case; space biology may be added back if time allows |
| 2026-10-03 | Batch plan written | 9 batches for a 10-hour solo build; Scenario B moved to roadmap |
| 2026-10-03 | Locked build decisions | Compressed sim time, honest baseline, plan schema, React + TS + Node |
| 2026-10-03 | Chose stack and sponsors | Cursor + Grok (LLM + Imagine scene reconstruction) + ElevenLabs; Spacetime parked |
| 2026-10-03 | Defined interaction contract | Intent → preview → validate → execute → rare one-reply escalations; 8 robot rules |
| 2026-10-03 | Reframed the claim | We cut round trips and time-to-outcome, not signal latency |
| 2026-10-03 | Chose architecture | Big model on the ground compiles intent; small executor on the robot |
| 2026-10-03 | Picked use cases | Mars surface first; space biology moved off the ISS to a far-from-Earth setting |
| 2026-10-03 | Doc started | SpaceX-sponsored track, AI-in-space direction |

## Problem and thesis

**Thesis: we can't beat the speed of light, so we cut how often you have to wait for it.**

Earth–Mars signal delay is about 3 to 22 minutes each way, set by planetary distance. No software lowers it. Never claim "lower latency" in the physical sense; SpaceX judges will catch it.

The real bottleneck is the operating loop. Today a rover acts, sends data home, waits for humans to decide, receives new commands, and repeats. Each step costs a full round trip, often a whole sol.

We reduce **effective latency**: time from human intent to completed outcome, measured in round trips. If the robot resolves most decisions locally and calls home only on real uncertainty, a task needing 6 round trips can need 1.

What we claim, in order:

1. Fewer round trips per task, so faster missions
2. Less uplink bandwidth, so cheaper operations
3. Every plan safety-checked before it leaves Earth, so safer autonomy

## System architecture

The big model stays on Earth and compiles intent into a verified contingency plan; a lightweight executor on the robot runs it. Flight computers are weak radiation-hardened chips, so a frontier LLM can't run onboard anyway.

&#91;embedded content: ground compiler + onboard executor · one uplink, rare escalations\]

One compact plan crosses the delay; the robot branches on local sensing and calls home only when no branch fits.

The plan is a strict schema (steps, branch conditions, escalation threshold) shared by the compiler, validator and executor.

## Interaction contract

The operator never drives the robot; the operator states intent and answers well-formed questions. Everything below is non-negotiable: if the demo breaks one, the pitch breaks.

### The loop

1. **Intent:** operator states a goal in plain language, with constraints ("sample the outcrop NE, avoid sand, keep battery above 30%").
2. **Preview:** the ground compiler shows the plan before it is sent: steps, branches, and what triggers an escalation. Operator approves or edits.
3. **Validate and uplink:** the safety validator checks the plan; only a passing plan is sent.
4. **Acknowledge:** the robot confirms receipt and plan version (arrives one delay later).
5. **Execute:** the robot runs the plan, picks branches from local sensing, and sends short periodic status summaries.
6. **Escalate (rare):** when no branch fits, the robot enters a safe hold and sends one escalation packet.
7. **Decide:** operator picks an option; the decision is uplinked as a plan amendment, and execution resumes.

### Robot non-negotiables

| # | Rule | Why it matters | How the demo shows it |
| --- | --- | --- | --- |
| 1 | Bounded autonomy: every action traces to a plan step or branch; nothing improvised | Operators trust it because it can't surprise them | Decision log ties each action to a plan line |
| 2 | Knows when it doesn't know: escalates whenever conditions fall outside the plan | Autonomy without this is reckless | One staged unexpected obstacle triggers an escalation |
| 3 | Every escalation is answerable in one reply: what happened, what it sees, 2–3 options, its recommendation | A vague question costs another full round trip | Operator answers with one click |
| 4 | Safe hold while waiting: stops risky actions but continues independent safe tasks | Idle wait time is the real cost of latency | Robot keeps imaging while awaiting a reply |
| 5 | Hard limits enforced onboard too, not only on the ground (battery floor, no-go zones, irreversible actions need explicit approval) | Defense in depth; sensing may reveal what the ground missed | Robot refuses a step that would breach the battery floor |
| 6 | Explains its choices: logs why each branch was taken, in one line | Auditability; judges and operators can follow along | Decision log visible in the UI |
| 7 | Bandwidth discipline: sends summaries, not raw streams, unless asked | Deep-space bandwidth is scarce and expensive | Bytes-downlinked counter stays low |
| 8 | Survives link loss: finishes the current plan, then holds safely | Blackouts happen (e.g. solar conjunction) | Toggle the link off mid-mission |

### Mission-control non-negotiables

- **Show staleness honestly:** every view of the robot is labeled "as of N minutes ago," never presented as live.
- **Abort is defined in advance:** an abort arrives late, so the plan states what "abort" means (e.g. stop and return to the last safe waypoint).
- **No command without a preview:** the operator always sees the compiled plan before it is sent.

## Tech stack and sponsors

Stack: Cursor + Grok (ground compiler LLM + Imagine) + ElevenLabs. Each one does a job in the product; nothing is added just for a prize.

| Tech | Role in product | Prize it qualifies for |
| --- | --- | --- |
| Cursor | Entire build | SpaceX track (required; more use scores higher) |
| Grok LLM | Ground compiler: intent → structured contingency plan | SpaceX track |
| Grok Imagine | Ground-side scene reconstruction from compact robot descriptions | SpaceX track (satisfies Imagine-or-Voice requirement) |
| ElevenLabs | Speech-to-text for operator intent; two text-to-speech voices | ElevenLabs sponsor prize, MLH ElevenLabs |
| Grok Bot (process only) | Project planning | SpaceX bonus points |

Also entered with no extra tech: Actually Intelligent (AI) track and Grand Prize. Parked for later: Spacetime as the real-time backend for the shared sim and delay link.

### Grok Imagine: scene reconstruction

Reconstruction strengthens the "cheaper" claim by replacing image downlinks with text.

1. On escalation, the robot downlinks a compact structured scene description (a few hundred bytes), not a raw image (megabytes). Example: "boulder \~1.2 m, 3 m ahead, slope 18° left, loose regolith right."
2. On the ground, Grok Imagine renders that description as a visual for situational awareness.
3. The bytes-downlinked counter shows image size vs. description size.

Hallucination safeguards (non-negotiable; prepared answer for judges):

- Every generated image is labeled "AI reconstruction: illustrative only."
- Decisions run on the structured data, never the picture; the options packet stands on its own.
- Operator can request the real image; the request visibly costs bandwidth and a round trip.
- Generation runs on the ground during the existing wait, so it adds no mission time.

### ElevenLabs: two voices

- **Speech-to-text:** operator speaks intent to mission control.
- **Ground assistant voice:** reads back the compiled plan before uplink.
- **Robot voice:** reads escalations aloud. It plays only after the injected delay, so the audience hears the latency.
- **Fallback:** typed commands always work, in case venue wifi fails.

## Build decisions

These are settled; Cursor should treat them as fixed constraints.

### 1. Compressed sim time

- One shared sim clock drives both panes: **1 real second = 1 simulated minute** (configurable).
- All delays, counters and voice timing read from that clock, in simulated minutes. Nothing uses wall-clock time directly.
- Pitch line: "Time is compressed; the ratios are real."

### 2. Honest baseline

The baseline mirrors real rover operations, not joystick teleop:

- Mission control uplinks a full command sequence with **no contingencies**.
- The rover runs it; any surprise (blocked path, hard rock, low battery) means stop and wait for Earth.
- Each stop costs a full round trip before a new sequence arrives.

Both panes run the same seed, map, mission and surprises, so the only difference is the system.

### 3. Plan schema (the contract)

One schema, shared by compiler, validator, executor and UI. Actions and conditions are fixed enums per scenario, loaded from a scenario config, so the executor stays deterministic; the LLM may only use these. Values below are for the Mars scenario.

- **Actions:** `drive_to`, `image`, `collect_sample`, `drill`, `hold`
- **Conditions:** `path_blocked`, `rock_too_hard`, `battery_below_floor`, `hazard_detected`, `target_not_found`, `confidence_below`
- **Branch outcomes:** `goto:<stepId>`, `skip`, `escalate`, `abort`

```json
{
  "planId": "p-001",
  "version": 1,
  "intent": "Sample the layered outcrop NE; avoid sand; keep battery above 30%",
  "limits": {
    "batteryFloorPct": 30,
    "noGoZones": ["sand-1"],
    "irreversibleNeedsApproval": true
  },
  "steps": [
    {
      "id": "s1", "action": "drive_to", "args": { "target": "wp-A" },
      "branches": [
        { "if": "path_blocked", "then": "goto:s1b" },
        { "if": "battery_below_floor", "then": "abort" }
      ]
    },
    { "id": "s1b", "action": "drive_to", "args": { "target": "wp-A-alt" } },
    {
      "id": "s2", "action": "drill", "args": { "site": "outcrop-1" },
      "irreversible": true, "approved": true,
      "branches": [ { "if": "rock_too_hard", "then": "escalate" } ]
    }
  ],
  "escalateWhen": ["no_branch_matches", "confidence_below:0.6"],
  "abort": { "behavior": "stop_and_return", "to": "last_safe_waypoint" },
  "whileWaiting": ["image_surroundings"]
}
```

Escalation packet (robot → ground), designed to be answerable in one reply:

```json
{
  "planId": "p-001",
  "stepId": "s2",
  "simTime": 412,
  "whatHappened": "Drill stalled at 4 cm; rock harder than expected",
  "scene": { "objects": ["boulder 1.2 m, 3 m ahead"], "slopeDeg": 18, "terrain": "loose regolith right" },
  "options": [
    { "id": "o1", "label": "Drill alternate site outcrop-2", "risk": "low", "costMin": 40 },
    { "id": "o2", "label": "Collect loose surface sample instead", "risk": "low", "costMin": 15 },
    { "id": "o3", "label": "Retry with higher drill force", "risk": "medium", "costMin": 20 }
  ],
  "recommendation": "o1"
}
```

The `scene` field is what Grok Imagine renders on the ground.

### 4. Stack and demo determinism

- **Stack:** React + TypeScript (Vite) frontend; small Node/Express backend that holds the Grok and ElevenLabs API keys. Keys never reach the client.
- **Validation:** plans and packets are validated against the schema (e.g. zod) at every boundary.
- **Deterministic demo:** fixed map seed and one scripted mission with one staged surprise and one unsafe command.
- **LLM fallback:** if Grok's plan fails validation after one retry, load a cached known-good plan for that mission.

## Use cases

Mars surface is the core scenario and must work end to end. Scenario B is a stretch goal (Stretch S2): a second config of the same engine, not a second build.

| Scenario | Setting | What it stresses | Example intent |
| --- | --- | --- | --- |
| A. Mars surface (core) | Rover on Mars, real terrain and real delay | Navigation and sampling with branching contingencies | "Sample the layered outcrop to the northeast; avoid sand" |
| B. Biology lab (stretch) | Autonomous life-detection lab on a Mars lander | Delicate, irreversible actions where knowing *when* to escalate matters most | "Run the growth assay; abort if contamination is detected" |

Scenario B must not be set on the ISS: ISS latency is under a second and crew are on board, so the core problem doesn't exist there.

## Demo and metrics

The demo runs the same mission twice, side by side, with a real Earth–Mars delay injected. I play mission control.

- **Left pane, baseline:** conventional sequence with no contingencies. Any surprise means stop and wait a full round trip (Build decisions §2).
- **Right pane, our system:** I state intent once. The ground model compiles a contingency plan, the robot executes and branches locally, and escalates only when unsure.

Live counters on both panes:

| Metric | Unit | Backs which claim |
| --- | --- | --- |
| Mission time | simulated minutes | Faster |
| Round trips | count | Faster |
| Bytes uplinked and downlinked | KB | Cheaper |
| Unsafe commands blocked before uplink | count | Safer |
| Escalations to human | count | Knows when to ask |

The delay slider should be adjustable (3 to 22 minutes) so judges see the gap widen as Mars moves farther away.

## Data sources

Candidates from memory, not yet verified for the hackathon; confirm access and formats before building on them.

| Source | Use in project | Batch |
| --- | --- | --- |
| HiRISE terrain models (DTMs), e.g. Jezero crater | Real Mars terrain, slopes and hazards for the sim map | Stretch S1 |
| Planetary ephemerides (astronomy-engine npm, or JPL Horizons) | Real Earth–Mars distance → one-way delay for a given date | Stretch S1 |
| NASA Planetary Data System, rover imagery | Realistic scenes and science targets | Stretch S1 (optional) |
| NASA GeneLab / Open Science Data Repository | Realistic parameters for the biology lab | Stretch S2 |
| Sponsor resources | Grok (LLM + Imagine), ElevenLabs; see Tech stack | Core |

## Build plan

Solo build, about 10 hours. Core: 9 batches (9h15m). Stretch: S1 and S2 (3h15m). Core plus stretch is about 12h30m, more than the time available, so stretch work only happens if the core runs ahead of schedule. Work strictly in order; finish each batch's "done when" check and commit before starting the next.

**Instructions for Cursor:** read this whole doc first. Treat Build decisions and the plan schema as fixed. Do one batch per session, and don't build ahead.

### Batch 0 — Project setup (0:30)

- Vite + React + TypeScript frontend; Node/Express backend in the same repo
- `.env` for Grok and ElevenLabs keys, loaded server-side only
- Copy this doc into `docs/design.md`
- **Done when:** app runs locally, `/api/health` responds, keys load on the server

### Batch 1 — Sim core, clock and delay link (1:15)

- Seeded 2D grid map: rover, obstacles, no-go zone (sand), science targets, waypoints
- Shared sim clock (1 real second = 1 sim minute) with pause and speed control
- Delay link: a message queue that delivers each message after the one-way delay, in sim minutes, in both directions
- **Done when:** a command sent from mission control moves the rover only after the delay, and the rover's state reaches mission control one delay later

### Batch 2 — Plan schema and onboard executor (1:30)

- TypeScript types and zod validation for the plan and escalation packet (Build decisions §3)
- Deterministic executor: runs steps, evaluates branch conditions from sim sensing, logs one line per decision
- Escalation: enters safe hold, runs `whileWaiting` tasks, sends the packet
- Onboard hard limits: battery floor, no-go zones, irreversible-action approval
- Use a hand-written plan JSON; no LLM yet. Load action and condition enums from a per-scenario config, not hard-coded, so Scenario B (Stretch S2) reuses the engine
- **Done when:** the scripted mission runs, takes a branch on the staged obstacle, and escalates on the hard-rock surprise

### Batch 3 — Baseline and side-by-side view (1:00)

- Baseline mode per Build decisions §2: a sequence with no contingencies; any surprise means stop and wait a round trip
- Two panes on the same clock, seed and mission
- Live counters: mission time, round trips, bytes up/down, escalations, unsafe commands blocked
- Staleness label on every robot view ("as of N min ago")
- **Done when:** one run shows our system finishing with clearly fewer round trips and less mission time than the baseline

**Checkpoint (about 4h15m in):** the core thesis is demoable with no AI. Commit, tag it, and record a backup screen capture.

### Batch 4 — Grok ground compiler and plan preview (1:15)

- Text intent box → backend → Grok returns plan JSON constrained to the schema
- Validate; on failure retry once, then fall back to the cached known-good plan
- Plan preview UI: steps, branches, escalation triggers; Approve button sends it over the delay link
- **Done when:** typing the demo intent produces a valid plan that runs end to end

### Batch 5 — Safety validator and one-reply escalations (1:00)

- Pre-uplink validator: rejects plans that breach limits, with a reason shown in the UI
- Escalation panel: what happened, options with risk and cost, recommendation highlighted; one click sends a plan amendment
- **Done when:** the staged unsafe command is blocked before uplink, and the hard-rock escalation resolves with a single click

### Batch 6 — Grok Imagine scene reconstruction (0:45)

- On escalation, the backend sends the packet's `scene` to Grok Imagine and shows the image in the escalation panel
- Label: "AI reconstruction: illustrative only"
- "Request real image" button that costs bandwidth and a round trip in the counters
- Bytes counter compares description size with real image size
- **Done when:** every escalation shows a labeled reconstruction, and requesting the real image visibly costs a round trip

**Checkpoint (about 7h15m in):** full SpaceX-eligible demo. Commit and re-record the backup capture.

### Batch 7 — ElevenLabs voice (1:00)

- Speech-to-text for intent (mic button); the typed box stays as fallback
- Ground assistant voice reads back the compiled plan before approval
- Robot voice reads escalations, played only when the packet arrives after the delay
- **Done when:** a full run works by voice, and the typed path still works with the mic off

### Stretch batches

Run these only if checkpoint 2 lands on time. Each must pass its own "done when" before the next starts. Batch 8 (polish) always runs last, after whatever stretch work got done.

### Stretch S1 — Real Mars data (1:45)

The SpaceX track asks for real space data in, so this is the highest-value stretch.

- **Pre-step, do early (even during Batch 1):** download one HiRISE DTM of a rover site (e.g. Jezero crater). Files are large and venue wifi is slow.
- Offline Python script (rasterio or GDAL): crop and downsample the DTM to a small heightmap (e.g. 128×128 JSON), derive slope, and mark steep cells as hazards and no-go zones
- Load the heightmap into the sim in place of the synthetic map; keep the synthetic map as a fallback toggle
- Real delays: compute Earth–Mars distance for a chosen date (e.g. the astronomy-engine npm package, offline), one-way delay = distance ÷ speed of light. A date picker replaces or drives the delay slider
- **Done when:** the mission runs on real Jezero terrain, and picking a date sets the real delay for that day

### Stretch S2 — Scenario B: autonomous biology lab (1:30)

- Setting: a life-detection lab on a Mars lander (not the ISS)
- New scenario config only: lab actions (e.g. `prepare_sample`, `incubate`, `image_sample`, `seal`) and conditions (e.g. `contamination_detected`, `growth_below_threshold`); same engine, clock, link, validator and UI
- Mark irreversible steps (e.g. `seal`, consuming a sample) so escalation behavior is the focus
- Realistic parameters from NASA GeneLab / OSDR where feasible
- Scenario switcher in the UI
- **Done when:** the same side-by-side demo runs in the lab scenario, with one escalation on an irreversible step

### Batch 8 — Polish and demo hardening (1:00)

- Delay slider (3 to 22 sim minutes)
- "Demo mode" button that resets seed, map and mission in one click
- Deploy (or confirm a reliable local run), final backup capture, Devpost write-up with screenshots
- **Done when:** a cold start to a full demo run takes under 3 minutes and works twice in a row

### Cut order if behind

Cut from the top of this list first:

1. Stretch S2 (Scenario B)
2. HiRISE terrain from Stretch S1 (keep the synthetic map; keep real ephemeris delays, which are cheap)
3. The rest of Stretch S1
4. Voice reduced to the robot's escalation voice only
5. Delay slider (keep one fixed delay)
6. Validator reduced to the battery floor and no-go zone rules

Never cut: the baseline comparison, one-reply escalation, or Grok Imagine (required for the SpaceX track).

**Out of scope for this build:** Spacetime (parked; revisit only if everything else is done).

## Open questions and risks

- [x] Which hackathon tracks and sponsor resources apply? (see Tech stack)
- [x] Sim stack: React + TypeScript + Node (see Build decisions §4)
- [ ] Confirm Grok Imagine API access and credits at the xAI booth

| Risk | Mitigation |
| --- | --- |
| Scope: core + stretch is about 12h30m against 10 solo hours | Stretch only after checkpoint 2 lands on time; cut order drops stretch first; HiRISE download started early |
| Grok Imagine API unavailable at the event | Confirm first thing; fallback is Grok Voice for the track requirement |
| Judges ask about hallucinated reconstructions | Labeled illustrative; decisions run on structured data; real image on request |
| Venue wifi breaks live voice | Typed command fallback always available |
| Crowded "AI in space" theme | Lead with the physics-aware framing and measured side-by-side numbers |
| Judges cite existing autonomy (Perseverance AutoNav, AEGIS) | Differentiate on the intent → verified contingency plan layer, not navigation |
| Onboard compute is weak (radiation-hardened chips) | Big model stays on the ground by design; onboard runs a lightweight executor |
