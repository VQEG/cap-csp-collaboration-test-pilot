# CAP–CSP simulator explorer

An interactive page that shows which harness components take part in a run, what flows between them in one 10 ms `NetworkStep`, and what the player and the network can see, for a chosen signaling level (L0–L4), backend, FikoRE condition, player behavior and transport. It compares two implementation states: the design in `docs/signaling.md` and `docs/architecture.md`, and the code on master.

Diagram boxes are colored by the repository that holds the code. Every dotted-underlined term, and every arrow label, shows an explanation on hover.

The page is hand-maintained. Nothing is generated from the code, so it goes stale when the code changes. Update it together with the changes listed below.

## Running it

Requires Node.js 20 or later.

```bash
npm install
npm run dev      # development server with hot reload
npm run build    # type-check and write dist/index.html
```

The build inlines all scripts, styles and fonts into `dist/index.html`, which opens directly from disk without a server. The selected settings are stored in the URL hash, so a link reproduces a view. `dist/` is not versioned.

The stack is Vite, React, TypeScript, Tailwind CSS and shadcn/ui components (in `src/components/ui/`, added with `npx shadcn@latest add <component>`).

## Code layout

Data, in `src/data/`:

- `signalingLevels.ts`: name and one-line description of L0–L4, from `docs/signaling.md`
- `networkConditions.ts`: C1–C8b calibration bands, dominant cause, background UEs, INI, timeline and duration, from `configs/fikore/README.md`; `defaultPlanDownlinkMbps` presets the plan rate
- `implementationStates.ts`: the states in the Implementation selector
- `repositories.ts`: the three repositories and their names in the legend
- `glossary.ts`: every hover text, keyed by term id

Logic, in `src/model/` (each function takes the `ExplorerSettings`):

- `explorerSettings.ts`: settings type and defaults
- `componentTopology.ts`: which diagram arrows and boxes are active
- `implementationStatus.ts`: banner text, is this level implemented in this state
- `networkStepWalkthrough.tsx`: ordered steps of one `NetworkStep`, with the arrows and boxes to highlight
- `playerVisibleFields.ts`: `CspFields` rows, their source and whether they are visible, filtered or null; values are midpoints of the calibration bands, not run data
- `experimentConfig.ts`: the experiment JSON; keep its keys in sync with `configs/experiments/` and `capcsp/runner/run.py`
- `runOutputFiles.ts`: files written to the output directory

View, in `src/components/`:

- `diagram/diagramLayout.ts`: positions of boxes, group frames and arrows in a 1480 × 900 SVG viewBox; arrow and box ids must match `componentTopology.ts`
- `diagram/ArchitectureDiagram.tsx`: the content of every box, including which repository colors it
- `GlossaryTerm.tsx`: `<GlossaryTerm id="…">` for hoverable terms; `InlineCodeText` turns `` `backtick` `` spans into code and links them to glossary entries with the same id
- the remaining files are the cards and panels of the page

Colors are CSS variables in `src/index.css`: `--flow-*` for arrow colors (direction of information) and `--repo-*` for box colors (repository), each with a dark variant under `.dark`.

## Updating it

To show an open PR next to master, add a state to `implementationStates.ts`, branch on it in the files under `src/model/` and the diagram boxes, and set `availability` on the glossary terms that only exist on that branch.

When a real L3 controller lands:

- Set `controllerSetsUeControl` in `componentTopology.ts` for that state, change the controller box in `ArchitectureDiagram.tsx`, and the controller step in `networkStepWalkthrough.tsx` and the `UeControl` row in `VisibilityTablesCard.tsx` from "proposed, not applied" to "applied".

When L4 is implemented:

- Enable `capacityTrace` for that state in `componentTopology.ts` and describe the trace source (exogenous or demand-coupled) in `implementationStatus.ts`.

When B1/B2 or a new policy reads CSP fields:

- Remove the "rules do not use them yet" texts in `implementationStatus.ts`, the rule box and `SetupNotesCard.tsx`, and add the policy to the Player behavior control.

When conditions are recalibrated or added:

- Update `networkConditions.ts` from `configs/fikore/README.md`. New conditions appear in the selector automatically.

When the config schema, output files, `CspFields`, `CapReport`, the telemetry mapping or the telemetry interval change:

- Update `experimentConfig.ts`, `runOutputFiles.ts`, `playerVisibleFields.ts` and the matching entries in `glossary.ts`.

When a component moves to another repository:

- Change the `repository` prop of its box in `ArchitectureDiagram.tsx` and its glossary entry.

After any change, run `npm run build`, open the page and click through each implementation state at L0–L4 on both backends to check that the banner, diagram and step list agree.
