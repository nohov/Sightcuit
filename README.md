# Campus scanner: Herdr execution workspace

Scope: identify and outline laptops, desktop computer towers, monitors, printers,
and outdoor light poles. Later catalog and copper work is deferred.

## Roadmap

1. Label definitions — labels agent.
2. Dataset/model source audit — research and baseline agents in parallel.
3. Independent audit — separate audit agent after all three deliver artifacts.
4. Pilot assembly — 150–200 reviewed images after source/sample verification.
5. Baseline execution and targeted fine-tuning — after data validation.
6. Locked campus walkthrough evaluation — requires actual independent footage.
7. Mobile camera/tracking/overlay integration — after recognition evidence.

Only the first research wave and its audit are configured for execution now.
Later phases need accepted inputs, actual images, compute and device testing.

## Commands

Run from this directory:

    python3 control/herdr_control.py launch
    python3 control/herdr_control.py status
    python3 control/herdr_control.py audit

Launch creates a dedicated Herdr workspace and starts three named Codex agents
using the user's default model. Audit checks the completion contracts and creates
a separate auditor. No automatic retraining loop or recurring automation is set.
Herdr manages terminals and session state; this controller enforces this wave's
dependencies. A completed process is not proof its work is correct.

Inspect agent output with `herdr agent read campus-labels --lines 80` (likewise
campus-data, campus-baseline, campus-audit). Attach using `herdr` and select the
scavscrap workspace. Keep unrelated workspaces untouched.

## Verification

completion.json must identify existing artifacts, actual checks, limitations and
sources. The controller validates the shape and artifact containment/existence;
the auditor checks semantic correctness and evidence. Human review of pilot and
test labels and physical phone/walkthrough checks are required in later phases.

Sources: https://herdr.dev/docs/quick-start/ and
https://herdr.dev/docs/cli-reference/. Local CLI help is checked at setup time.

## Setup status

Herdr 0.8.0 is installed and its compatible server is running. Dedicated workspace
`wA` (scavscrap) and three role tabs were created. Task execution has NOT
started successfully. Codex startup first invoked its updater; those startup
processes were interrupted. Launch now suppresses the update check for these
sessions only, without changing global configuration. Codex then exited with:

    account/read failed during TUI bootstrap: account/read failed:
    failed to load workspace requirements (code -32603)

No agent deliverables or recognition experiments have been produced. Once Codex
can start normally with this account, rerun the launch command. The auditor is
configured but cannot be dispatched before valid producer artifacts exist.

Project relocated to /Users/noahhova/Documents/scavscrap. Herdr role tabs now use this directory. No agents relaunched during relocation.
