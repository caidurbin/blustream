# Architecture-doc review — July 2026

A review of the repo's architecture documents: `CONTEXT.md`, the 14 numbered ADRs plus
`draft-dmp168-identity-spike.md` under `docs/adr/`, and `docs/control4-driver-plan.md`.
Findings were generated across five lenses — conciseness, doc↔doc consistency, doc↔code
reality, goal alignment, and documentation best practices — and every finding was
adversarially verified against the actual files before inclusion (27 of 34 deduplicated
candidates survived; 7 were refuted with evidence).

**Ground rules applied** (agreed before the review):

1. The house formats are the yardstick: an ADR is a title + 1–3 sentences with optional
   sections only when they earn their place; `CONTEXT.md` is a tight glossary
   (`## Language`, `**Term**:` entries of 1–2 sentences, `_Avoid_:` lines, zero
   implementation detail). Long ADRs get restructuring suggestions that preserve
   rationale — not deletion, and not a blessing of the drift.
2. `docs/control4-driver-plan.md` is explicitly historical; stale planned-state content
   under its banner is *not* a finding. Only failures of the historical framing itself
   are flagged.
3. All fixes are doc-side. Where docs and code disagree, the finding names the
   authoritative side; two findings flag conflicts where the *code* is plausibly the
   wrong side (R5, R23).

**Status:** all 27 findings were walked through one-by-one on 2026-07-01 and each
carries a **Resolution** paragraph recording the agreed disposition. Execution of the
agreed edits is follow-up work; R23 is already tracked as issue
[#83](https://github.com/caidurbin/blustream/issues/83).

## Priorities at a glance

| #  | Sev | Doc | Finding |
|----|-----|-----|---------|
| R1 | High | draft spike | Draft in `docs/adr/` contradicts ADR 0010 and shipped code, no supersession marker |
| R2 | High | CONTEXT.md | "HA integration POC" section duplicates ADR 0009 and is stale vs `hacs-v0.2.0` |
| R3 | High | ADR 0008 | Still says HA integration ships "eventually"; the `hacs-v*` release lane is recorded in no ADR |
| R4 | High | CONTEXT.md | "Device identity" is a third copy of the identity story, not a glossary term |
| R5–R17 | Med | various | Contradictions, duplication, staleness, one missing ADR |
| R18–R27 | Low | various | Polish: structure, wording drift, dead citations |

---

## CONTEXT.md

### R2 (high) — Delete the "HA integration POC" section

The section is a project-phase decision, not a glossary term (the file's own preamble
says "Implementation details belong in ADRs, not here"), duplicates ADR 0009
near-verbatim, and is stale against shipped code: it says the integration "exposes a
single entity (the uptime sensor)" and frames volume/mute/routing as future work, but
`hacs-v0.2.0` loads button, media_player, sensor, and switch platforms. The two copies
have already drifted (ADR 0009's surface list additionally includes runtime data and
stale-device handling). It even contradicts this same file's "Routing" section, which
describes the media_player entities.

**Fix:** Delete the section; ADR 0009 is the sole home for the decision. If "gold-tier
POC" is genuinely project vocabulary, keep one tight `## Language` entry:
"**Gold-tier POC**: The v0.1 HA integration shape — full Gold-standard scaffolding,
deliberately narrow entity count; now historical (entity expansion landed in
`hacs-v0.2.0` per ADR 0014). See ADR 0009."

**Resolution (2026-07-01):** Delete the section entirely — no replacement glossary
term. ADR 0009 is the sole home for the decision and rationale.

### R4 (high) — Shrink "Device identity" to a glossary entry

The section is a smuggled spike report: firmware versions, the 52-command probe result,
`DhcpServiceInfo` mechanics, the MA-M prefix analysis, HTTP-scrape review-smell
commentary. It is the *third* copy of the identity story (alongside ADR 0010 and the
spike doc), and it states "DHCP discovery … is the canonical programmatic identity
path" without ADR 0010's crucial qualifiers (manual identity outranks discovered;
entry-id last resort; no silent rewrites). Neither doc links the other.

**Fix:** Shrink to: "**Device identity**: The MAC address is the unit's only stable
identifier; it is unreachable over the TCP command protocol and arrives via DHCP
discovery or manual entry, else the config-entry id. See
[ADR 0010](adr/0010-ha-integration-device-identity.md)." Before deleting, move the one
detail not already in ADR 0010 into it: the concrete mDNS collision consequence (two
out-of-the-box units on one LAN collide on `dmp168.local` until renamed). The
HELP-matches-published-API note can live in the spike doc, which 0010 already cites.

**Resolution (2026-07-01):** Agreed as proposed: shrink to the one-sentence glossary
entry linking ADR 0010; relocate the mDNS two-unit-collision consequence into ADR
0010's zeroconf paragraph (composing with R21's wording fix there); the HELP-verbatim
note stays in the spike doc (canonical for empirical findings per R1). Keep the term —
device identity is genuine recurring project vocabulary.

### R8 (medium) — Adopt the CONTEXT-FORMAT structure

The file follows none of the house glossary structure: no `## Language` section, terms
are `## Heading` essays instead of `**Term**:` entries of 1–2 sentences, and no entry
has an `_Avoid_:` line — even where the text explicitly legislates vocabulary (the
Uptime section's "prefer boot time … reserve uptime" guidance).

**Fix:** Restructure to the template: a 1–2 sentence context description, then
`## Language` with `**Term**:` entries (Uptime duration, Boot time, Source, Routing,
Bus, Device identity, Gold-tier POC if kept), each 1–2 sentences with `_Avoid_:` lines.

**Resolution (2026-07-01):** Adopt the template. Rebuild CONTEXT.md to the house
format: context description, then `## Language` with `**Term**:` entries — Uptime
duration, Boot time, Source, Routing, Bus, Device identity (no Gold-tier POC term, per
R2) — each 1–2 sentences with `_Avoid_:` lines where synonyms exist. This is the
umbrella restructure that R2/R4/R9/R10's per-entry resolutions compose into; execute as
one rewrite of the file.

### R9 (medium) — Tighten "Source" and "Routing"; stop duplicating ADR 0014

Both entries exceed the 1–2 sentence rule and duplicate ADR 0014's rationale and HA
entity mechanics (media_player, `SELECT_SOURCE`, `source_list` contents, area/label
targeting, the single-select argument with the User Manual p.7 citation). "Source" has
already diverged from 0014: it asserts sources are "expressed as a stereo pair (L and R
move together)" while ADR 0014's consequence records that per-channel L/R divergence
exists and the integration treats L as authoritative.

**Fix:** Tighten to definitions such as: "**Source**: The one signal feeding an output —
an input, a bus, or None (the device's own selectable no-route value)." and
"**Routing**: Selecting which source feeds an output; single-select per output. See
ADR 0014." Soften "L and R move together" to "normally a stereo pair; per-channel
divergence is possible via the web GUI (ADR 0014)". Leave the hardware-constraint
argument and entity mapping solely in ADR 0014.

**Resolution (2026-07-01):** Accepted as proposed. Source and Routing become the tight
`## Language` entries above (with the softened stereo-pair sentence and `_Avoid_`
lines); the hardware-constraint argument and HA entity mapping live solely in ADR 0014.
The Bus entry is kept, tightened to the same shape.

### R10 (medium) — Split "Uptime" into two terms; drop the implementation paragraphs

The entry opens with a correct one-line definition, then spends two paragraphs on
library method names (`get_uptime_raw()`, `get_uptime()`), the derivation formula, and
`SensorDeviceClass.UPTIME`. Its vocabulary ruling is buried in prose instead of the
`_Avoid_` mechanism. Most of the implementation detail is already in ADR 0011.

**Fix:** Split into "**Uptime duration**: The elapsed time since the device last
booted, as reported by the device (raw `DDDD:HH:MM:SS`)." and "**Boot time**: The
instant the device last booted, derived from uptime duration; the value HA's uptime
sensor reports. _Avoid_: uptime (for the derived datetime)." Delete the implementation
paragraphs — ADR 0011 already records the typed-method boundary and the
`timedelta → datetime` derivation.

**Resolution (2026-07-01):** Accepted. Split into the two `## Language` entries above
and delete the implementation paragraphs outright — no new home for the
`get_uptime_raw()` / `SensorDeviceClass.UPTIME` mapping (ADR 0011 records the boundary
and derivation; the specific names are visible in the code and sensor docstring).

---

## ADRs

### R3 (high) — ADR 0008: record the `hacs-v*` release lane; drop "eventually"

The ADR still describes the HA integration as "(eventually) … via HACS" and names tag
prefixes for only two of the three release lanes (`v*`, `c4-v*`). The integration has
shipped (`hacs-v0.1.0`, `hacs-v0.2.0`, live `release-hacs.yml`) on a third disjoint
`hacs-v*` lane documented only in the README's versioning table. The
three-disjoint-prefix taxonomy is hard to reverse (published tags are immutable) and
genuinely surprising (the integration's 0.1.0 shipped as `hacs-v0.1.0`, not `v0.1.0`;
HACS installs from the tree, not an attached artifact) — yet no ADR records it.

**Fix:** Amend the first sentence: replace "(eventually) a Home Assistant integration
via HACS" with "the Home Assistant integration installed by HACS from the repository
tree (tags `hacs-v*`)", and add one sentence recording that the three tag prefixes are
deliberately disjoint so a tag for one artifact cannot trigger another artifact's
release workflow.

**Resolution (2026-07-01):** Amend ADR 0008 in place, as proposed. The underlying
decision (public OSS, three artifacts, independent releases) is unchanged — this
completes the record rather than reversing it, so no supersession machinery; a separate
release-lane ADR was considered and rejected as splitting one distribution story across
two ADRs.

### R11 (medium) — ADR 0009 contradicts ADR 0012 on stale-device handling

ADR 0009 lists "stale-device handling" among the surfaces built to Gold standard from
day one, but ADR 0012 and the shipped `quality_scale.yaml` declare the `stale-devices`
rule `exempt` (1:1 entry-to-device). ADR 0012 + `quality_scale.yaml` are authoritative.

**Fix:** In ADR 0009, drop "stale-device handling" from the surface list, or change it
to "stale-device handling (later declared exempt — ADR 0012)".

**Resolution (2026-07-01):** Drop "stale-device handling" from ADR 0009's surface list.
The item was aspirational when written and turned out to be N/A (1:1 entry-to-device);
removing it makes the list simply true, and ADR 0012 + `quality_scale.yaml` remain the
record of the exemption.

### R5 (medium) — ADR 0005: make the port split explicit; reconcile the spec comment

Doc-vs-code conflict on which port non-Control4 clients canonically use. ADR 0005 says
port 23 "stays available for the Python CLI, future HA integration, and ad-hoc telnet
tools", and the code agrees (`device.py` `port: int = 23`, `const.py`
`DEFAULT_PORT = 23`) — but `spec/protocol.yaml`, the declared source of truth,
annotates 8000 as "the canonical port for automation clients" and 23 as "intentionally
left free for ad-hoc use", and codegen exports `DEFAULT_PORT = 8000`, which the Python
library ignores. A reader following the spec would conclude the Python/HA defaults are
wrong.

**Fix:** Add one sentence to ADR 0005: "Consequently, port 8000 is canonical only for
the Lua driver (and is what `spec/protocol.yaml`'s `default_port` / generated
`DEFAULT_PORT` means); the Python library, CLI, and HA integration deliberately default
to 23 via telnetlib3, which handles the IAC negotiation." Then reconcile the
`spec/protocol.yaml` transport comment (code-side follow-up) to stop calling 8000 "the
canonical port for automation clients".

**Resolution (2026-07-01):** Option 1 — clarify the split on both sides: the ADR 0005
sentence as proposed, plus the `spec/protocol.yaml` transport-comment fix (spec/codegen
side) so the spec stops calling 8000 "the canonical port for automation clients". The
alternative of making 8000 canonical for the Python side too (code behavior change) was
considered and rejected — it contradicts ADR 0005's recorded decision with no driver
beyond comment consistency.

### R7 (medium) — ADR 0012 bundles seven sub-decisions and duplicates in-repo rationale

ADR 0012 packs test location, coverage thresholds, CI tooling, manifest fields,
`py.typed`, the quality-scale registry, and a reserved-for-future note into one
grab-bag, against the house norm of one short decision per ADR. Several passages
duplicate rationale already living in its native home and are guaranteed to drift: the
daily-cron rationale is near-verbatim in `lint-ha.yml`'s header comment, the per-rule
reasoning is already in `quality_scale.yaml` `comment:` fields (which even repeat the
py.typed/Platinum argument), and the `rm -rf tests` folklore sentence is trivia, not a
decision. Bundled ADRs also can't be individually superseded.

**Fix:** Keep a tight decision core recording only the surprising, hard-to-reverse
choices: tests at `tests/components/blustream/` because hassfest trips on test packages
nested inside the integration directory; the 100 % config-flow / ≥95 % elsewhere
coverage split; single pinned HA version + daily cron (one sentence, pointing at
`lint-ha.yml`); `py.typed` shipping from library v0.1.0 to keep Platinum reachable; and
the `"loggers"` manifest rationale — which must stay in the ADR (or move to the
component README) because `manifest.json` is JSON and cannot carry comments. Relocate
the rest: per-rule reasoning stays solely in `quality_scale.yaml`, CI-tooling rationale
stays in the workflow headers, and the `VERSION`/`MINOR_VERSION` rationale becomes a
comment next to those attributes in `config_flow.py`.

**Resolution (2026-07-01):** Option 1 — trim to a tight core ADR keeping the five
surprising, hard-to-reverse choices as short bold-lead items (test location, coverage
split, pinned-HA + daily cron, `py.typed` from v0.1.0, `"loggers"` rationale — the last
stays in the ADR because JSON manifests can't carry comments). Relocations as proposed:
per-rule reasoning lives solely in `quality_scale.yaml`, CI detail in workflow headers,
`VERSION`/`MINOR_VERSION` rationale as a `config_flow.py` comment; drop the `rm -rf`
folklore sentence. Splitting into multiple ADRs was considered and rejected as
ceremony.

### R13 (medium) — ADR 0013: drop the brittle test count and the dangling deferral

"All 309 tests pass on each" no longer matches CI (the library lane alone collects 413
tests, the CLI lane 50 more), and the plan for a follow-up `style:` commit is
work-tracking content that dates the record.

**Fix:** Keep the decision paragraph and the why-3.12 paragraph; add a one-sentence
`## Consequences` (breaking floor bump; acceptable pre-1.0 with EOL versions;
vulnerable dep was dev-only). Replace the count with "the full test suite passes on
each matrix leg" and delete the "Deferred to a dedicated `style:` commit" sentence
(see also R23).

**Resolution (2026-07-01):** Agreed as proposed: keep the decision and why-3.12
paragraphs; count becomes "the full test suite passes on each matrix leg"; scope
paragraph compresses to a one-sentence `## Consequences`; the deferred-`style:`-commit
sentence is deleted, with the underlying ruff `target-version` loose end handed to
R23's resolution (tracking issue or the bump itself).

### R14 (medium) — ADR 0012: dead "Q12 grilling transcript" citation

"see Q12 grilling transcript / future ADR if revisited" points at a conversation
transcript that is not in the repository and is unrecoverable.

**Fix:** Delete the transcript pointer and cite the in-repo home: "(1:1
entry-to-device — full rationale in `quality_scale.yaml`'s rule comment)". Adopt as a
house rule: never cite conversation transcripts from ADRs; distill the rationale inline
or into a committed file.

**Resolution (2026-07-01):** Fix the citation as proposed (folds into R7's rewrite of
ADR 0012 — the trimmed ADR must not carry the dead pointer forward). The formal
house-rule codification was considered and skipped — no rule text gets added to the
skill or docs/agents/; the practice is applied here without being legislated.

### R15 (medium) — Add `date:` frontmatter to ADRs anchored to external timelines

No numbered ADR carries a date, yet several reason from moving targets that only parse
relative to a writing date: ADR 0013 from Python EOL dates and "as of HA 2026.3",
ADR 0010 from firmware versions and HA core PRs, ADR 0012 from a survey of HACS
integrations. Present-tense claims like "3.10 is itself near EOL" decay invisibly.

**Fix:** Add a `date: YYYY-MM-DD` line to the existing YAML frontmatter (which already
carries `applies_to`, so this composes with the house format at zero structural cost) —
at minimum on 0010/0012/0013, ideally all, backfilled from `git log`. Do not add full
Status headers wholesale; the house format reserves those for revisited decisions.

**Resolution (2026-07-01):** All 14 numbered ADRs get `date:` frontmatter, backfilled
from each file's first-commit date in `git log`; new ADRs get a date at creation.
Status frontmatter is still not added wholesale — reserved for revisited decisions per
the house format.

### R16 (medium) — Missing ADR: the identifier-hygiene harness

The secret-scanning decision — betterleaks with custom IPv4/IPv6/MAC rules, the policy
that committed example identifiers must use IETF documentation ranges, the deliberate
exception keeping the real Blustream OUI prefix in synthetic MACs, and the resolution
norm "move the value into a documentation range, don't widen the allowlist" — is
recorded only in the README and `docs/secret-scanning-allowlist.md`, not in any ADR. It
clears the house bar: hard to reverse (history was rewritten to enforce it — issue
#41), surprising without context, and a real trade-off.

**Fix:** Add ADR 0015, 2–3 sentences per the house format, pointing at
`docs/secret-scanning-allowlist.md` for the operational mechanics.

**Resolution (2026-07-01):** Add ADR 0015 as proposed: committed identifiers must use
IETF documentation ranges; betterleaks pre-commit + CI gate with custom IP/MAC rules;
the Blustream OUI prefix as the one allowed real value; violations resolved by moving
the value into a documentation range, not widening the allowlist; pointer to
`docs/secret-scanning-allowlist.md` for mechanics. Frontmatter uses
`applies_to: [repo]` — the taxonomy's first repo-wide value, adopted deliberately for
cross-artifact decisions.

### R18 (low) — ADR 0010: trim pinned call signatures into optional sections

The core decision (three identity sources, chosen at entry creation, never silently
rewritten) is buried in a 503-word body pinning exact signatures —
`_abort_if_unique_id_configured(updates={CONF_HOST: ip})`, `format_mac`,
`connections={(CONNECTION_NETWORK_MAC, mac)}`, `async_create_issue(is_fixable=True)`.
The mechanics are already documented at the call sites (`config_flow.py` docstrings,
`repairs.py`, `quality_scale.yaml`), which mitigates but doesn't remove the staleness
risk.

**Fix:** Trim in place — no code changes needed. Keep the 2-sentence decision plus one
short what-and-why paragraph per identity source, preserving the non-obvious
constraints that are the real rationale (7-hex-digit prefix because the parent 24-bit
OUI is a shared MA-M block; `registered_devices: true` because HA needs it to dispatch
DHCP callbacks to configured entries). Retitle the last two paragraphs as
`## Consequences` and `## Considered Options` (keep the PR citations). Point to the
spike doc for the MA-M analysis.

**Resolution (2026-07-01):** Accepted as proposed — trim in place, no code changes;
keep the two non-obvious constraints (7-hex-digit prefix, `registered_devices: true`);
`## Consequences` + `## Considered Options` with PR citations; signatures dropped;
MA-M analysis delegated to the spike doc. Execute as a single ADR 0010 rewrite
composing R4 (collision consequence moves in), R20 (supersession wording), and R21
(hostname wording).

### R20 (low) — ADR 0010: plan supersession, not in-place revision

The rejected-alternatives paragraph anticipates being edited in place ("a future
revision of this ADR") if Blustream ships a `NET MAC?` getter. The house lifecycle
mechanism for revisited decisions is `status: superseded by ADR-NNNN` plus a new ADR —
in-place revision would obscure why the discovered/manual/entry-id chain existed.

**Fix:** Reword the final clause: "…supersedes the discovered/manual fallback chain;
record that decision in a new ADR and mark this one `status: superseded by ADR-NNNN`."

**Resolution (2026-07-01):** Accepted — reword as proposed; no status frontmatter added
now. Part of the single ADR 0010 rewrite (with R4, R18, R21).

### R21 (low) — ADR 0010 vs CONTEXT.md: "fixed" vs "user-configurable" mDNS hostname

ADR 0010 (echoing the spike) calls the mDNS hostname "fixed", but CONTEXT.md says it is
a "user-configurable mDNS domain name (default: `dmp168.local`)" that units collide on
"until renamed". If users can rename it, the hostname is default-constant, not fixed —
which matters because a renamed unit stops matching the manifest's `name: dmp168*`
zeroconf matcher, a caveat the ADR's wording hides. The conclusion (zeroconf can't
carry stable identity) is unchanged.

**Fix:** Reword ADR 0010: "The DMP168's factory-default mDNS hostname is the constant
`DMP168.local` (user-renameable via the web GUI, never MAC-derived), and TXT records
carry no identity, so zeroconf cannot supply a stable identifier."

**Resolution (2026-07-01):** Accepted — reword as proposed; the same paragraph absorbs
R4's relocated two-unit-collision consequence (including the renamed-unit
zeroconf-matcher caveat). Part of the single ADR 0010 rewrite.

### R22 (low) — ADR 0013: wrong citation for the wheel-contents claim

The wheel-contents claim is code-accurate, but its "(ADR 0008)" citation points at an
ADR that says nothing about wheel contents or runtime dependencies. The dependency
actually traces to `pyproject.toml` and, decision-wise, to ADR 0005 (port-23 telnet
stays available for the Python CLI).

**Fix:** Drop the citation or replace it: "(see `pyproject.toml`; port-23 telnet
support per ADR 0005)".

**Resolution (2026-07-01):** Replace the citation with "(see `pyproject.toml`; port-23
telnet support per ADR 0005)" — the corrected pointer does real work now that R5 makes
ADR 0005 explicitly own the port-split story.

### R23 (low) — ADR 0013: the deferred ruff bump never landed and has no tracking pointer

Doc-vs-code conflict: the ADR defers the ruff `target-version` bump "to a dedicated
`style:` commit", but `pyproject.toml` still has `target-version = "py39"` (with the
now-contradictory comment "# Assume Python 3.9+") while `requires-python = ">=3.12"`.
A reader cannot tell whether the deferral is pending or forgotten; the code side is
plausibly the wrong side.

**Fix:** File the tracking issue and add its pointer to the ADR's deferral sentence, or
land the bump and append "(done in `<commit>`)". Either way the deferral note
self-resolves.

**Resolution (2026-07-01):** Tracked as issue
[#83](https://github.com/caidurbin/blustream/issues/83) (filed during this review after
confirming no existing issue covered it — searched all 81 open+closed). The ADR gets no
pointer since R13 deletes the deferral sentence; the issue is the tracking. Landing the
bump inside this docs pass was rejected — ADR 0013's keep-the-style-diff-separate logic
still holds.

### R24 (low) — ADRs 0001/0002/0004/0005: "future HA integration" is no longer future

All four still say "future HA integration" ("future HA" in 0004), but the integration
shipped with its own ADR series (0009–0014) and does expose routing. The decisions are
unchanged; the framing makes these ADRs read as older than the shipped state.

**Fix:** One-word sweep: "the future HA integration" → "the HA integration" (in 0001,
optionally "…exposes more than routing — see ADR 0014"). No status frontmatter needed.

**Resolution (2026-07-01):** Accepted — sweep all four ADRs (0001/0002/0004/0005); in
ADR 0001 the closing clause becomes "the HA integration exposes more than routing — see
ADR 0014" since the *may* has resolved. No status frontmatter.

### R25 (low) — ADR 0006: `DEBUG_MODE` is not the shipped property name

The ADR names the property `DEBUG_MODE`, but the shipped Composer property is
"Debug Mode" (LIST, Off/On) in `driver.xml`, and `driver.lua` reads
`read_property("Debug Mode", …)`. A dealer grepping by the ADR's name finds nothing.

**Fix:** Change the ADR text to "A `Debug Mode` Property gates verbose `print()`
output…".

**Resolution (2026-07-01):** Accepted — rename to `Debug Mode` in ADR 0006, matching
the shipped Composer property surface the dealer actually sees.

### R26 (low) — ADR 0014: consequence sentence is narrower than shipped behavior

"Treats L as authoritative" is blanket, but `media_player.py` follows L for
`volume_level` while reporting `is_volume_muted` only when *both* channels are muted —
an AND-collapse the module docstring documents while citing ADR 0014. Code is
authoritative; the sentence should match so nobody "fixes" the mute logic back to
L-only.

**Fix:** Sharpen to: "volume_level follows L; is_volume_muted is true only when both
channels are muted; writes always target both channels; divergence is surfaced in
`extra_state_attributes` rather than widening the entity surface."

**Resolution (2026-07-01):** Agreed — sharpen as proposed; lands inside R19's
**Consequence.** paragraph in the single ADR 0014 rewrite.

### R19 (low) — ADR 0014: break up the 23-line single paragraph

The body is one unbroken paragraph fusing six concerns — decision, hardware constraint,
two rejected alternatives (including the noteworthy CONTEXT.md-reversal), the
None-source rationale, the bus-mixing deferral, and the L/R consequence. This is
anomalous within the repo's own set: 0010 and 0012 break comparable material into
bold-lead paragraphs.

**Fix:** Split following the house pattern (bold-lead paragraphs, not `##` headers): a
2–4 sentence lead stating constraint + decision, then **Rejected alternatives.**,
**Clearing a route.**, **Bus mixing deferred.**, and **Consequence.**

**Resolution (2026-07-01):** Accepted — split into the bold-lead paragraphs as
proposed, keeping the CONTEXT.md-reversal note visible under **Rejected
alternatives.**; the **Consequence.** paragraph absorbs R26's sharpened wording in the
same rewrite.

---

## draft-dmp168-identity-spike.md

### R1 (high) — Move out of `docs/adr/`, mark the Recommendation superseded

A draft-status spike report sits in `docs/adr/` (breaking the 1–3-sentence format and
the sequential-numbering convention — `draft` isn't even in the house status
vocabulary), and its Recommendation section contradicts accepted ADR 0010 and shipped
code on three concrete points with no superseded marker: (1) it recommends ARP/getmac
MAC lookups, which ADR 0010 records as "explicitly disallowed by HA (PR #97837)" and
`config_flow.py` does not do; (2) it says "do not ask the user for the MAC", but
`async_step_user` ships an optional MAC field per ADR 0010; (3) its manifest snippet
uses a dhcp `hostname: dmp168*` matcher, but the shipped manifest declares only
`macaddress: "34D0B82*"` + `registered_devices: true`. `status: draft` reads as "not
yet decided", inviting someone to implement the outdated path.

**Fix:** Move the file to `docs/dmp168-identity-spike.md` (sibling of
`docs/dmp168-known-issues.md`), update the pointer in ADR 0010 (and the "identity-spike
ADR" wording in `docs/secret-scanning-allowlist.md`), change frontmatter to
`status: superseded by ADR-0010`, and add one line under the title: "Empirical findings
(Tasks 1–4) remain the canonical record; the Recommendation section is superseded by
ADR 0010, which rejects ARP lookup, adds an optional manual-MAC field, and drops the
hostname dhcp matcher."

**Resolution (2026-07-01):** Move + supersede, and additionally excise the superseded
"Recommendation for the HA integration" section entirely (including its
config-flow-shape and two-unit-collision subsections) rather than keeping it for
provenance. Concretely: `git mv` to `docs/dmp168-identity-spike.md`, frontmatter
`status: superseded by ADR-0010`, a one-line note under the title that the empirical
findings (Tasks 1–4) remain the canonical record and the removed Recommendation is
superseded by ADR 0010, and both pointers updated (ADR 0010's citation path; the
"identity-spike ADR" wording in `docs/secret-scanning-allowlist.md`). The Summary's
one-sentence Tier-2 recommendation stays, covered by the supersession note.

### R17 (medium) — Replace the `/tmp` artefact trail

The evidence trail points at five `/tmp` paths (probe script, raw captures, mDNS
script) — ephemeral files that are certainly gone — so the Artefacts section is a list
of dead ends in a doc otherwise written as a durable point-in-time record.

**Fix:** Replace the Artefacts section with one sentence: "The probe/mDNS scripts and
raw captures were ephemeral (`/tmp`), not retained; the tables above are the complete
surviving record." If reproducibility against future firmware matters (ADR 0010
anticipates a `NET MAC?` feature request), commit a cleaned-up probe script under
`tests/integration/` or `tools/` and link that instead. Adopt as a house rule: docs
never cite `/tmp`, screenshots, or transcripts — evidence is either distilled into the
doc or committed.

**Resolution (2026-07-01):** One-sentence replacement only (Artefacts section plus the
two inline `/tmp` citations in the Task 1 method line). No probe script gets committed
or tracked — re-probe reproducibility deemed not worth the code work. House-rule
codification skipped, consistent with R14.

---

## control4-driver-plan.md

### R12 (medium) — The status header itself has gone stale

The header is the one part of this historical doc meant to reflect current reality, and
it pins "shipped as v0.1.0" and points to "ADRs 0009–0012" — but `hacs-v0.2.0` is the
shipped version, and ADR 0014, which actually supersedes the plan's Phase-5 HA sketch
with the shipped entity model, is omitted.

**Fix:** Reword so it doesn't pin a version that keeps going stale: "The Home Assistant
integration described below as deferred/future work has since shipped (first release
`hacs-v0.1.0`; see the README, CHANGELOG, and ADRs 0009–0012 and 0014 for current
state)."

**Resolution (2026-07-01):** Agreed — reword as proposed. The header states only
immutable facts ("first release `hacs-v0.1.0`") and delegates current state to README /
CHANGELOG / ADRs 0009–0012 + 0014, so it cannot go stale again.

### R6 (medium) — Phase 4 contradicts §3 and ADR 0008 on `.c4z` encryption

Phase 4 says the GitHub release ships an "encrypted production `.c4z`", contradicting
the same doc's §3 ("Unencrypted `.c4z` artifact attached to GitHub releases"),
ADR 0008, and shipped reality (`manifest.xml` `squishLua="false"`, no encryption path
in `tools/build_c4z.py`). This is an internal contradiction misstating the recorded
decision — not banner-covered staleness.

**Fix:** Change Phase 4 to "Cut GitHub release with the release (unencrypted,
non-`-ae`) `.c4z` attached on `c4-v*` tag", or append a bracketed erratum: "[erratum:
releases ship unencrypted, per §3 and ADR-0008]".

**Resolution (2026-07-01):** Direct fix — rewrite the Phase 4 line to "Cut GitHub
release with the release (unencrypted, non-`-ae`) `.c4z` attached on `c4-v*` tag".
Ground truth was independently verified before deciding: the build pipeline has no
encryption path (the vendored driverpackager's encryption is gated on
`driver.xml` `encryption="2"`, which this repo does not set; a release-flavor build
with the exact CI command yields plaintext `driver.lua` inside the `.c4z`). §3 and
ADR 0008 are correct; Phase 4 was wrong at time of writing. Side observation from the
verification, no action here: no `c4-v*` GitHub release has been cut yet — the lane
exists but is unexercised.

### R27 (low) — Drop the placeholder author email

The author line pairs the real name with `name@example.com` — a deliberate post-scrub
convention documented in `docs/secret-scanning-allowlist.md`, but a reader here has no
pointer to that convention, so it reads like template junk, and git history already
attributes the doc.

**Fix:** Drop the parenthetical (or use "**Author:** Cai Durbin (@caidurbin)"). Since
this is the only file using the placeholder, also remove or update the
`name@example.com` row in the allowlist doc so it doesn't document an unused
convention.

**Resolution (2026-07-01):** Part 1 only — drop the parenthetical to plain
"**Author:** Cai Durbin". Part 2 skipped: the `name@example.com` row in
`docs/secret-scanning-allowlist.md` stays as-is.

---

## Examined and deliberately not flagged

For transparency, categories that were investigated and refuted in verification:

- **Plan-doc §8.4 CI description and §6/§7 "canonical record" claims** — historical
  staleness fully covered by the doc's banner; the empirical findings the plan claims
  as canonical have in fact been promoted (ADR 0003/0005, `spec/protocol.yaml`,
  CONTEXT.md, `docs/dmp168-known-issues.md`).
- **ADR 0009 needing a status marker after entity expansion** — the ADR's own text
  frames expansion as the predicted additive path; not a contradiction.
- **ADR 0009's Platinum re-evaluation gate "dangling"** — the clause sets a
  precondition, not a deadline; `quality_scale.yaml`'s `strict-typing: todo` is the
  legitimate above-tier state.
- **A `docs/adr/README.md` index** — the set is small, `applies_to` frontmatter plus
  `docs/agents/domain.md`'s read-the-relevant-ADRs convention already serve the
  navigation need.
- **CONTEXT.md's "None is first-class" vs the library's `Optional[OutputSource]`** —
  the glossary makes a domain claim about the device; the code deliberately documents
  the mapping at the boundary. No conflict.
