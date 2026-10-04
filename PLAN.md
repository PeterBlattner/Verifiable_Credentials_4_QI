# Working plan

The change set being worked on now, with its checklist and progress log. When one is
finished it moves to `docs/history/`, so this file stays short enough to read.

- `docs/history/PLAN-2026.md`: change sets 1 to 35, from the first demonstrator to the
  browsable harmonisation chapter, each with its context, decisions and progress log.
- `docs/history/firstPrompt.md`: the question the project started from.

# Change set 36 - the recognition model's gaps, in words

## Context

Preparing a briefing for Global ACI, Peter passed on a second review of the recognition
model. It found three gaps in W3C Recognized Entities for the quality infrastructure, and
noted that the W3C and UNTP recognition models are both drafts being aligned. Checked
against the code:
1. **No registered identifier.** No recognition states the accreditation number as an
   identifier of the body. It reaches a credential only as `capabilityReference.identifier`,
   and the UNTP projection records `registeredId` as missing.
2. **No member for scope.** What a body is recognised *for* travels in `mainScope`, which
   this project invented, inside each recognised action. The `arrangement-scope` check is
   scope-based and ignores the actions of intermediate links. Nothing said so.
3. **No assurance of the DID binding.** Control of a DID is checked only when the
   accreditation is handed over (`actors/exchange.py`), never before a recognition is
   issued.

## Decisions

Taken with Peter:
- **Text only.** The credentials, the verifier and the UNTP pin stay as they are. A
  registered identifier in the credentials, an `evidence` entry for the DID check, and
  the unpublished DIA are left out.
- **The UNTP pin waits** for the next published release, and is then bumped the way
  change set 28 did it.

## Checklist

- [x] 1. `harmonisation.py`: `registered-id` (floor, partial) and `recognition-scope`
  (floor, open). Steps 4 and 6 unblock them.
- [x] 2. `deployment.py`: the identifier check in the Global ACI and SAS profiles
- [x] 3. `cautions.md` and its README mirror: UNTP's DIA is a draft too, being aligned
- [x] 4. `ARCHITECTURE.md`: the check is about scope, and `mainScope` is a placeholder
- [x] 5. Verification

## Progress log

- 2026-10-04: plan approved. Branch `feature/recognition-model-gaps`.
- 2026-10-04: items 1 to 5 done.
  - `/api/harmonisation` serves 26 items, 11 of them open, so the open share stays below
    half. `/api/infrastructure` serves both new `must_add` lines.
  - Deliberate break: `recognition-scope` taken out of every step failed exactly
    `test_every_minimum_item_is_reached_by_some_step`. Restored.
  - Full suite: 878 pass, 46 skipped. `ui-clicks.mjs`: every control responds, 68 on the
    harmonisation chapter where there were 64. `chapter-snapshot.mjs` shows the two items
    and the new cautions sentence.

## Git

`feature/recognition-model-gaps` into `develop`.

# Left for later

Change set 35 was released in #107. Two issues are left for later by decision, not by
oversight:

- #74, a claims ledger: what long-term validation and a failed resolution would need,
  and which of it belongs in the demonstration.
- #75, the machine-readable CMC and scope encoding tried against real KCDB entries and
  accreditation scopes, with practitioners.

One extension is designed and not built:

- The IECEE CB Scheme as a fourth arrangement, in `docs/extensions/iecee-cb-scheme.md`.
  Its IECEE facts come from secondary sources and need confirming before a build.
