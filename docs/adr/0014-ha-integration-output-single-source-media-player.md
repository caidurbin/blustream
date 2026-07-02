---
applies_to: [ha-integration]
date: 2026-06-07
---

# HA integration: each output is single-source — outputs are media_player + select_source, mixing deferred to buses

The DMP168 is a 16×8 *matrix*, but each output is fed by **exactly one** source at a
time: the hardware permits one input (or bus) to feed many outputs, but routing
*multiple* inputs into a single output is impossible at the matrix stage and requires
summing them through an internal **bus** first (User Manual p.7; the library's
`OutputRouting.source` is correspondingly a single `Optional[OutputSource]`, and
STATUS reports one `FromIn` per output channel). We therefore model each of the 8
outputs as a `media_player` exposing `SELECT_SOURCE`, where `source_list` is `None` +
the 16 inputs + the 8 buses and routing is the standard `media_player.select_source`
action — the universal HA convention for A/V matrices (monoprice, blackbird, et al.).

**Rejected alternatives.** We explicitly rejected two alternatives we initially
favoured: (a) a 128-entity crosspoint **switch grid**, and (b) custom
`route_input_to_output` / `remove_input_from_output` **services plus a per-output
`active_inputs` sensor** — both presuppose many-inputs-to-one-output mixing the matrix
stage does not support, and (b) had already been drafted into CONTEXT.md before the
manual disproved the premise.

**Clearing a route.** Exposed as the device-native `None` source value — not a
`turn_off` overload (which greys the Lovelace card and misuses `OFF`'s "powered down"
semantics), and not a synthetic action in `source_list`, since the device genuinely
reports `None` as a routing target.

**Bus mixing deferred.** A bus may be *selected* as an output source now, but
*defining* what a bus sums is out of scope this round and is configured on the device
web GUI — the only path to "multiple inputs feeding one zone," added additively later.

**Consequence.** Per-channel L/R divergence (set via the web GUI) does not fit the
stereo-pair entity model: volume_level follows L; is_volume_muted is true only when
both channels are muted; writes always target both channels; divergence is surfaced in
`extra_state_attributes` rather than widening the entity surface.
