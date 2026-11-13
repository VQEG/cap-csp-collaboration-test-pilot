import type { ReactNode } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import { MultipleChoice, NumberField, SegmentedChoice, SettingControl } from "@/components/SettingControls";
import {
  CONTENT_AUDIO_REPRESENTATION,
  CONTENT_FILE_PATH,
  CONTENT_FRAME_RATE_FPS,
  CONTENT_SEGMENT_DURATION_S,
  CONTENT_VIDEO_CODEC,
  CONTENT_VIDEO_COUNT,
  CONTENT_VIDEO_DURATION_S,
  CONTENT_VIDEO_IDS,
  CONTENT_VIDEO_REPRESENTATIONS,
} from "@/data/contentCatalogue";
import { CONDITION_PARAMETER_BASE_VALUES, conditionParametersOf, type ConditionParameter } from "@/data/conditionParameters";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { BEHAVIOR_MIXES, BEHAVIOR_PARAMETERS, PLAYER_BEHAVIORS, behaviorOfUe, type BehaviorMixId, type PlayerBehavior } from "@/data/playerBehaviors";
import { SIGNALING_LEVELS } from "@/data/signalingLevels";
import { cn } from "@/lib/utils";
import { effectiveGridAxes, gridCellCount, runDurationSeconds, sessionSeed } from "@/model/experimentConfig";
import {
  VIDEO_UE_COUNT_CHOICES,
  constantRateDownlinkMbps,
  usesConstantRateBackend,
  usesFikoreBackend,
  type ExplorerSettings,
  type GridAxes,
  type SignalingLevel,
} from "@/model/explorerSettings";
import { MAX_SWIPES_PER_SESSION, parseSwipeTimes, resolveSwipeTimes } from "@/model/swipeSchedule";

type UpdateSetting = <K extends keyof ExplorerSettings>(key: K, value: ExplorerSettings[K]) => void;

interface SectionProps {
  settings: ExplorerSettings;
  updateSetting: UpdateSetting;
}

const BEHAVIOR_ORDER: PlayerBehavior[] = ["simple", "preload"];
const MIX_OPTIONS = Object.entries(BEHAVIOR_MIXES).map(([id, mix]) => [id, mix.label]) as [BehaviorMixId, string][];

function Section({ title, badge, description, children }: { title: string; badge?: string; description: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-3 rounded-lg border p-3">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          {title}
          {badge && (
            <Badge variant="secondary" className="text-[11px] font-normal">
              {badge}
            </Badge>
          )}
        </h3>
        <p className="text-xs leading-snug text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  );
}

function updateGridAxes(settings: ExplorerSettings, updateSetting: UpdateSetting, changes: Partial<GridAxes>) {
  updateSetting("gridAxes", { ...settings.gridAxes, ...changes });
}

function ConditionParameterRow({ settings, updateSetting, parameter }: SectionProps & { parameter: ConditionParameter }) {
  const conditionId = settings.conditionId;
  const baseValue = CONDITION_PARAMETER_BASE_VALUES[conditionId][parameter.id];
  const changedValues = settings.conditionOverrides[conditionId] ?? {};
  const value = changedValues[parameter.id] ?? baseValue;
  const changed = value !== baseValue;
  const iniKey = parameter.target.kind === "experiment" ? "duration_s" : parameter.target.kind === "section" ? `${parameter.target.section}.${parameter.target.key}` : `${parameter.target.group}.${parameter.target.key}`;

  function setValue(next: number | undefined) {
    const nextValues = { ...changedValues };
    if (next === undefined || next === baseValue) delete nextValues[parameter.id];
    else nextValues[parameter.id] = next;
    const overrides = { ...settings.conditionOverrides, [conditionId]: nextValues };
    if (!Object.keys(nextValues).length) delete overrides[conditionId];
    updateSetting("conditionOverrides", overrides);
  }

  return (
    <tr className="border-t border-border/60 align-middle">
      <td className="py-1 pr-2">
        <div className="text-xs" title={parameter.hint}>
          {parameter.label}
          {parameter.unit && <span className="text-muted-foreground"> ({parameter.unit})</span>}
        </div>
        <div className="font-mono text-[10px] text-muted-foreground">{iniKey}</div>
      </td>
      <td className="w-[104px] py-1">
        <NumberField
          ariaLabel={`${parameter.label} of ${conditionId}`}
          value={value}
          step={parameter.step}
          min={parameter.id === "studyPositionX" || parameter.id === "txPower" ? undefined : 0}
          integer={parameter.integer}
          changed={changed}
          onChange={setValue}
        />
      </td>
      <td className="w-7 py-1 pl-1">
        {changed && (
          <Button variant="ghost" size="icon-xs" aria-label={`Reset ${parameter.label}`} title={`Reset to ${baseValue}`} onClick={() => setValue(undefined)}>
            <RotateCcw />
          </Button>
        )}
      </td>
    </tr>
  );
}

function ConditionSection({ settings, updateSetting }: SectionProps) {
  const grid = settings.configOutputKind === "grid";
  if (usesConstantRateBackend(settings)) {
    return (
      <Section title="Conditions (C)" description="The constant_rate backend has no radio conditions.">
        <p className="text-xs text-muted-foreground">
          Every UE gets its own <T id="downlink_rate_mbps">{constantRateDownlinkMbps(settings)} Mbps</T>; set the rate in the panel above. Pick FikoRE to configure C1–C8b.
        </p>
      </Section>
    );
  }
  if (!usesFikoreBackend(settings)) {
    return (
      <Section title="Conditions (C)" description="The mock backend has no conditions.">
        <p className="text-xs text-muted-foreground">It shares a fixed byte budget per step. Pick FikoRE to configure C1–C8b.</p>
      </Section>
    );
  }
  const condition = NETWORK_CONDITIONS[settings.conditionId];
  const changedCount = Object.keys(settings.conditionOverrides).length;
  return (
    <Section
      title="Conditions (C)"
      description={<>Each condition is a FikoRE scenario (INI and timeline). Changed values become <C>fikore_section_overrides</C> or <C>fikore_ue_overrides</C>.</>}
    >
      {grid && (
        <SettingControl title="Conditions in the grid">
          <MultipleChoice
            values={effectiveGridAxes(settings).conditionIds}
            options={Object.keys(NETWORK_CONDITIONS).map((id) => [id, id])}
            onChange={(conditionIds) => updateGridAxes(settings, updateSetting, { conditionIds })}
          />
        </SettingControl>
      )}
      <SettingControl
        title={grid ? "Parameters of" : "Condition"}
        hint={
          <>
            {condition.dominantCause}
            {condition.timelineFile && <> · timeline <C>{condition.timelineFile}</C></>}
          </>
        }
      >
        <Select value={settings.conditionId} onValueChange={(value) => updateSetting("conditionId", value)}>
          <SelectTrigger size="sm" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(NETWORK_CONDITIONS).map(([id, entry]) => (
              <SelectItem key={id} value={id}>
                {id} · {entry.name}
                {settings.conditionOverrides[id] ? " (changed)" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SettingControl>
      <table className="w-full">
        <tbody>
          {conditionParametersOf(settings.conditionId).map((parameter) => (
            <ConditionParameterRow key={`${settings.conditionId}-${parameter.id}`} settings={settings} updateSetting={updateSetting} parameter={parameter} />
          ))}
        </tbody>
      </table>
      {changedCount > 0 && (
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>Changed: {Object.keys(settings.conditionOverrides).join(", ")}</span>
          <Button variant="outline" size="xs" onClick={() => updateSetting("conditionOverrides", {})}>
            Reset all
          </Button>
        </div>
      )}
    </Section>
  );
}

function BehaviorParameterCell({ settings, updateSetting, behavior, parameterId }: SectionProps & { behavior: PlayerBehavior; parameterId: string }) {
  const definition = PLAYER_BEHAVIORS[behavior];
  const parameter = BEHAVIOR_PARAMETERS.find((entry) => entry.id === parameterId)!;
  if (!(parameterId in definition.defaults)) return <td className="py-1 text-center text-xs text-muted-foreground">–</td>;
  const value = settings.behaviorParameters[behavior][parameterId] ?? definition.defaults[parameterId];
  const changed = value !== definition.defaults[parameterId];
  const setValue = (next: number | boolean) =>
    updateSetting("behaviorParameters", { ...settings.behaviorParameters, [behavior]: { ...settings.behaviorParameters[behavior], [parameterId]: next } });
  return (
    <td className="w-[84px] py-1 pl-1">
      {parameter.kind === "boolean" ? (
        <div className="flex justify-end pr-2">
          <Checkbox aria-label={`${parameter.label}, ${definition.shortLabel}`} checked={value === true} onCheckedChange={(checked) => setValue(checked === true)} />
        </div>
      ) : (
        <NumberField
          ariaLabel={`${parameter.label}, ${definition.shortLabel}`}
          value={Number(value)}
          min={parameter.min}
          step={parameter.step}
          integer={parameter.kind === "integer"}
          changed={changed}
          onChange={setValue}
        />
      )}
    </td>
  );
}

function BehaviorSection({ settings, updateSetting }: SectionProps) {
  const grid = settings.configOutputKind === "grid";
  const axes = effectiveGridAxes(settings);
  const parametersChanged = BEHAVIOR_ORDER.some((behavior) =>
    Object.entries(PLAYER_BEHAVIORS[behavior].defaults).some(([id, value]) => settings.behaviorParameters[behavior][id] !== value),
  );
  const ueAssignment = [...Array(settings.videoUeCount).keys()].map((ueId) => `UE ${ueId}: ${PLAYER_BEHAVIORS[behaviorOfUe(settings.behaviorMix, ueId)].shortLabel}`).join(" · ");
  return (
    <Section
      title="Behaviours (B)"
      description={<>A mix repeats over the UEs of a cell, so UEs of one cell can behave differently. Values go to <C>rule_config</C> and <C>config.scheduling</C> of each session.</>}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <SettingControl title={grid ? "Mixes in the grid" : "Mix"}>
          {grid ? (
            <MultipleChoice values={axes.behaviorMixes} options={MIX_OPTIONS} onChange={(behaviorMixes) => updateGridAxes(settings, updateSetting, { behaviorMixes })} />
          ) : (
            <SegmentedChoice value={settings.behaviorMix} options={MIX_OPTIONS} onChange={(value) => updateSetting("behaviorMix", value)} />
          )}
        </SettingControl>
        <SettingControl title={grid ? "UEs per cell in the grid" : "Video UEs"}>
          {grid ? (
            <MultipleChoice
              values={axes.ueCounts.map(String)}
              options={VIDEO_UE_COUNT_CHOICES.map((count) => [String(count), String(count)])}
              onChange={(values) => updateGridAxes(settings, updateSetting, { ueCounts: values.map(Number) })}
            />
          ) : (
            <SegmentedChoice
              value={String(settings.videoUeCount)}
              options={VIDEO_UE_COUNT_CHOICES.map((count) => [String(count), String(count)])}
              onChange={(value) => updateSetting("videoUeCount", Number(value))}
            />
          )}
        </SettingControl>
      </div>
      <table className="w-full">
        <thead>
          <tr className="text-[11px] text-muted-foreground">
            <th className="pb-1 text-left font-medium">Parameter</th>
            {BEHAVIOR_ORDER.map((behavior) => (
              <th key={behavior} className="pb-1 text-right font-medium">
                <T id={PLAYER_BEHAVIORS[behavior].ruleName}>{PLAYER_BEHAVIORS[behavior].label}</T>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {BEHAVIOR_PARAMETERS.map((parameter) => (
            <tr key={parameter.id} className="border-t border-border/60 align-middle">
              <td className="py-1 pr-2">
                <div className="text-xs" title={parameter.hint}>
                  {parameter.label}
                </div>
                <div className="font-mono text-[10px] text-muted-foreground">
                  {parameter.location === "scheduling" ? "scheduling." : parameter.location === "throughput" ? "rule_config.throughput." : "rule_config."}
                  {parameter.key}
                </div>
              </td>
              {BEHAVIOR_ORDER.map((behavior) => (
                <BehaviorParameterCell key={behavior} settings={settings} updateSetting={updateSetting} behavior={behavior} parameterId={parameter.id} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{grid ? `Shown cell: ${ueAssignment}` : ueAssignment}</span>
        {parametersChanged && (
          <Button
            variant="outline"
            size="xs"
            onClick={() =>
              updateSetting("behaviorParameters", { simple: { ...PLAYER_BEHAVIORS.simple.defaults }, preload: { ...PLAYER_BEHAVIORS.preload.defaults } })
            }
          >
            Reset
          </Button>
        )}
      </div>
    </Section>
  );
}

function formatSeconds(value: number): string {
  return `${value.toFixed(1)} s`;
}

function SwipeSection({ settings, updateSetting }: SectionProps) {
  const grid = settings.configOutputKind === "grid";
  const durationS = runDurationSeconds(settings);
  const sequence = parseSwipeTimes(settings.swipeTimesS);
  const [low, high] = settings.watchDurationRangeS;
  if (settings.networkBackend === "mock") {
    return (
      <Section title="Swipes" description="The 0.2 s mock smoke test swipes once, at 0.1 s.">
        <p className="text-xs text-muted-foreground">Pick FikoRE or constant rate to configure the user model.</p>
      </Section>
    );
  }
  return (
    <Section
      title="Swipes"
      description={
        <>
          The SFV <C>userModel</C> of every session. SFV resolves all swipe times before the session starts. The content has {CONTENT_VIDEO_COUNT} videos, so a session
          swipes at most {MAX_SWIPES_PER_SESSION} times.
        </>
      }
    >
      <SettingControl title="User model">
        <SegmentedChoice
          value={settings.swipeModel}
          options={[
            ["seeded", "seeded (random)"],
            ["sequence", "fixed times"],
          ]}
          onChange={(value) => updateSetting("swipeModel", value)}
        />
      </SettingControl>
      {settings.swipeModel === "seeded" ? (
        <SettingControl title="Time between swipes (s)" hint="Uniform draw with the session seed. It runs from the previous swipe, so loading and stalls count towards it.">
          <div className="flex items-center gap-2">
            <NumberField ariaLabel="Shortest time between swipes" value={low} min={0} step={1} className="w-20" onChange={(value) => updateSetting("watchDurationRangeS", [value, Math.max(value, high)])} />
            <span className="text-xs text-muted-foreground">to</span>
            <NumberField ariaLabel="Longest time between swipes" value={high} min={0} step={1} className="w-20" onChange={(value) => updateSetting("watchDurationRangeS", [Math.min(low, value), value])} />
          </div>
        </SettingControl>
      ) : (
        <SettingControl title="Swipe times (s, session-relative)" hint={typeof sequence === "string" ? <span className="text-destructive">{sequence}</span> : "The same times for every UE"}>
          <Input value={settings.swipeTimesS} className="h-8 font-mono text-xs" aria-label="Swipe times" onChange={(event) => updateSetting("swipeTimesS", event.target.value)} />
        </SettingControl>
      )}
      <div>
        <div className="mb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
          Resolved swipes{grid ? ", replication 1" : ""} (run ends at {durationS} s)
        </div>
        <ul className="space-y-0.5 text-xs">
          {[...Array(settings.videoUeCount).keys()].map((ueId) => {
            const seed = sessionSeed(settings, ueId);
            const times = resolveSwipeTimes(settings, seed, durationS);
            return (
              <li key={ueId} className="flex flex-wrap gap-x-2">
                <span className="w-[136px] shrink-0 text-muted-foreground">
                  UE {ueId} · {PLAYER_BEHAVIORS[behaviorOfUe(settings.behaviorMix, ueId)].shortLabel} · seed {seed}
                </span>
                <span className="font-mono">{times.length ? times.map(formatSeconds).join(" → ") : "no swipe"}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </Section>
  );
}

function GridAxesSection({ settings, updateSetting }: SectionProps) {
  const axes = effectiveGridAxes(settings);
  return (
    <Section title="Grid" description={<>Every combination of the selected values is one cell. Replication r uses the FikoRE seed {"20260927 + r"} and the session seeds 1000 r + UE ID in every cell.</>}>
      <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
        <SettingControl title="Signaling levels in the grid">
          <MultipleChoice
            values={axes.signalingLevels}
            options={(Object.keys(SIGNALING_LEVELS) as SignalingLevel[]).map((level) => [level, level])}
            onChange={(signalingLevels) => updateGridAxes(settings, updateSetting, { signalingLevels })}
          />
        </SettingControl>
        <SettingControl title="Replications">
          <NumberField ariaLabel="Replications" value={axes.replications} min={1} integer onChange={(replications) => updateGridAxes(settings, updateSetting, { replications })} />
        </SettingControl>
      </div>
      <p className="text-xs text-muted-foreground">
        {gridCellCount(settings)} cells. The diagram shows one cell: the condition, level, UE count and mix chosen for the run.
      </p>
    </Section>
  );
}

/** The content is fixed for now. Shown so that the reader knows what every run plays. */
function ContentSection() {
  return (
    <Section
      title="Content"
      badge="fixed"
      description={
        <>
          Every run plays the same {CONTENT_VIDEO_COUNT} short videos from <C>{CONTENT_FILE_PATH}</C>. The explorer cannot change them yet. The harness can read
          another file from the <C>content</C> config key.
        </>
      }
    >
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Videos</dt>
        <dd>
          {CONTENT_VIDEO_IDS.join(", ")}, played in this order
        </dd>
        <dt className="text-muted-foreground">Length</dt>
        <dd>
          {CONTENT_VIDEO_DURATION_S} s each, in {CONTENT_SEGMENT_DURATION_S} s segments ({CONTENT_VIDEO_DURATION_S / CONTENT_SEGMENT_DURATION_S} per video)
        </dd>
        <dt className="text-muted-foreground">Video</dt>
        <dd>
          {CONTENT_VIDEO_CODEC}, {CONTENT_FRAME_RATE_FPS} fps, portrait
        </dd>
        <dt className="text-muted-foreground">Audio</dt>
        <dd>
          {CONTENT_AUDIO_REPRESENTATION.codec}, {CONTENT_AUDIO_REPRESENTATION.bitrateKbps} kbps
        </dd>
      </dl>
      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr className="border-b">
            <th className="py-1 text-left font-normal">Representation</th>
            <th className="py-1 text-right font-normal">Resolution</th>
            <th className="py-1 text-right font-normal">Declared</th>
            <th className="py-1 text-right font-normal">Measured</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {CONTENT_VIDEO_REPRESENTATIONS.map((representation) => (
            <tr key={representation.id} className="border-b last:border-b-0">
              <td className="py-1">{representation.id}</td>
              <td className="py-1 text-right">
                {representation.width}×{representation.height}
              </td>
              <td className="py-1 text-right">{representation.bitrateKbps} kbps</td>
              <td className="py-1 text-right">{representation.measuredBitrateKbps} kbps</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs leading-snug text-muted-foreground">Measured is the average bitrate over the segment sizes of all videos.</p>
    </Section>
  );
}

/** The independent variables of an experiment: conditions, behaviours, swipes and, for a grid, the axes. */
export function ExperimentDesignCard({ settings, updateSetting }: SectionProps) {
  const grid = settings.configOutputKind === "grid";
  return (
    <Card className="gap-3">
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>Experiment design</CardTitle>
          <CardDescription>Change the parameters of the conditions, behaviours and swipes. The diagram and the config follow.</CardDescription>
        </div>
        <SegmentedChoice
          value={settings.configOutputKind}
          options={[
            ["run", "One run"],
            ["grid", "Grid"],
          ]}
          onChange={(value) => updateSetting("configOutputKind", value)}
        />
      </CardHeader>
      <CardContent className={cn("grid gap-3 md:grid-cols-2")}>
        <ConditionSection settings={settings} updateSetting={updateSetting} />
        <BehaviorSection settings={settings} updateSetting={updateSetting} />
        <SwipeSection settings={settings} updateSetting={updateSetting} />
        <ContentSection />
        {grid && <GridAxesSection settings={settings} updateSetting={updateSetting} />}
      </CardContent>
    </Card>
  );
}
