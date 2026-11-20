import type { ReactNode } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";
import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import { MultipleChoice, NumberField, SegmentedChoice, SettingControl } from "@/components/SettingControls";
import { CONTENT_CATALOGUES, type ContentCatalogueId } from "@/data/contentCatalogue";
import { CONDITION_PARAMETER_BASE_VALUES, conditionParametersOf, type ConditionParameter } from "@/data/conditionParameters";
import { LEGACY_CONDITION_IDS, NETWORK_CONDITIONS, effectiveConditionView } from "@/data/networkConditions";
import {
  ALL_LAYERED_CONDITION_IDS,
  CORE6_CONDITION_IDS,
  PARAMETRIC_PRESET_DEFAULTS,
  STUDY_ZONE_DISTANCES_M,
  VALID_CELL_BANDWIDTHS_MHZ,
  estimateMeanActiveBgUes,
  isCore6Condition,
  isParametricCondition,
  parseLoadSweepValues,
  resolveParametricCellValues,
  type ArrivalModeKind,
  type BgSpatialKind,
  type CellBandwidthMhz,
  type ParametricCellValues,
  type StudyMobilityKind,
  type StudyPositionZone,
} from "@/data/parametricCells";
import { BEHAVIOR_MIXES, BEHAVIOR_PARAMETERS, PLAYER_BEHAVIORS, behaviorOfUe, type BehaviorMixId, type PlayerBehavior } from "@/data/playerBehaviors";
import { SIGNALING_LEVELS } from "@/data/signalingLevels";
import { cn } from "@/lib/utils";
import { effectiveGridAxes, gridCellCount, runDurationSeconds, sessionSeed, usesParametricLoadSweep } from "@/model/experimentConfig";
import {
  VIDEO_UE_COUNT_CHOICES,
  constantRateDownlinkMbps,
  usesConstantRateBackend,
  usesFikoreBackend,
  type ExplorerSettings,
  type GridAxes,
  type SignalingLevel,
} from "@/model/explorerSettings";
import { maxSwipesPerSession, parseSwipeTimes, resolveSwipeTimes } from "@/model/swipeSchedule";

type UpdateSetting = <K extends keyof ExplorerSettings>(key: K, value: ExplorerSettings[K]) => void;

interface SectionProps {
  settings: ExplorerSettings;
  updateSetting: UpdateSetting;
}

const BEHAVIOR_ORDER: PlayerBehavior[] = ["simple", "preload"];
const MIX_OPTIONS = Object.entries(BEHAVIOR_MIXES).map(([id, mix]) => [id, mix.label]) as [BehaviorMixId, string][];

const CONDITION_SELECTOR_GROUPS: { family: "core6" | "layered_extended" | "custom" | "legacy"; label: string }[] = [
  { family: "core6", label: "Core-6 Test Plan (parametric)" },
  { family: "layered_extended", label: "Extended ablation (M02–M11)" },
  { family: "custom", label: "Custom parametric cell" },
  { family: "legacy", label: "Legacy calibration pack (C1–C8b)" },
];

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

function LegacyConditionParameterRow({ settings, updateSetting, parameter }: SectionProps & { parameter: ConditionParameter }) {
  const conditionId = settings.conditionId;
  const baseValue = CONDITION_PARAMETER_BASE_VALUES[conditionId][parameter.id];
  const changedValues = settings.conditionOverrides[conditionId] ?? {};
  const value = changedValues[parameter.id] ?? baseValue;
  const changed = value !== baseValue;
  const iniKey =
    parameter.target.kind === "experiment"
      ? "duration_s"
      : parameter.target.kind === "section"
        ? `${parameter.target.section}.${parameter.target.key}`
        : `${parameter.target.group}.${parameter.target.key}`;

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

function ParametricCellEditor({ settings, updateSetting }: SectionProps) {
  const conditionId = settings.conditionId;
  const defaults = PARAMETRIC_PRESET_DEFAULTS[conditionId];
  const currentOverrides = settings.parametricOverrides[conditionId] ?? {};
  const values = resolveParametricCellValues(conditionId, currentOverrides);
  const loadSweep = usesParametricLoadSweep(settings);
  const sweepParsed = parseLoadSweepValues(settings.loadSweepValues);
  const lambdaBg = estimateMeanActiveBgUes(values);

  function setChanges(changes: Partial<ParametricCellValues>) {
    const merged: Partial<ParametricCellValues> = { ...currentOverrides, ...changes };
    // Prune keys equal to the preset defaults so JSON stays minimal
    for (const key of Object.keys(merged) as (keyof ParametricCellValues)[]) {
      if (merged[key] === defaults[key]) delete merged[key];
    }
    const nextOverrides = { ...settings.parametricOverrides, [conditionId]: merged };
    if (!Object.keys(merged).length) delete nextOverrides[conditionId];
    updateSetting("parametricOverrides", nextOverrides);
  }

  function setStudyZone(zone: StudyPositionZone) {
    if (zone === "custom") setChanges({ study_position: "custom" });
    else setChanges({ study_position: zone, study_distance_m: STUDY_ZONE_DISTANCES_M[zone] });
  }

  function setMobility(mobility: StudyMobilityKind) {
    const defaultSpeed = mobility === "static" ? 0 : mobility === "pedestrian" ? 3.6 : 73.26;
    setChanges({ study_mobility: mobility, study_speed_kmh: defaultSpeed });
  }

  return (
    <div className="space-y-2.5 rounded-md border border-border/70 bg-muted/20 p-2.5">
      <div className="grid gap-2.5 sm:grid-cols-2">
        <SettingControl title="Run length (s)" hint={<C>duration_s</C>}>
          <NumberField
            ariaLabel="Parametric run length"
            value={values.duration_s}
            min={5}
            step={5}
            integer
            changed={values.duration_s !== defaults.duration_s}
            onChange={(duration_s) => setChanges({ duration_s })}
          />
        </SettingControl>
        <SettingControl title="Cell bandwidth (MHz)" hint={<C>parametric_cell.bandwidth_mhz</C>}>
          <SegmentedChoice
            value={String(values.bandwidth_mhz)}
            options={VALID_CELL_BANDWIDTHS_MHZ.map((bw) => [String(bw), String(bw)])}
            onChange={(bw) => setChanges({ bandwidth_mhz: Number(bw) as CellBandwidthMhz })}
          />
        </SettingControl>
      </div>

      <div className="grid gap-2.5 sm:grid-cols-[1.5fr_1fr]">
        <SettingControl title="Study UE zone" hint={<C>study_position</C>}>
          <SegmentedChoice
            value={values.study_position}
            options={[
              ["good", "good (151m)"],
              ["mid", "mid (350m)"],
              ["edge", "edge (650m)"],
              ["custom", "custom"],
            ]}
            onChange={setStudyZone}
          />
        </SettingControl>
        <SettingControl title="Distance x (m)" hint={<C>study_distance_m</C>}>
          <NumberField
            ariaLabel="Study UE distance in meters"
            value={values.study_distance_m}
            min={10}
            step={10}
            changed={values.study_distance_m !== defaults.study_distance_m}
            onChange={(study_distance_m) => setChanges({ study_position: "custom", study_distance_m })}
          />
        </SettingControl>
      </div>

      <div className="grid gap-2.5 sm:grid-cols-[1.5fr_1fr]">
        <SettingControl title="Study UE mobility" hint={<C>study_mobility</C>}>
          <SegmentedChoice
            value={values.study_mobility}
            options={[
              ["static", "static"],
              ["pedestrian", "pedestrian"],
              ["vehicular_traverse", "vehicular"],
            ]}
            onChange={setMobility}
          />
        </SettingControl>
        <SettingControl title="Speed (km/h)" hint={<C>study_speed_kmh</C>}>
          <NumberField
            ariaLabel="Study UE speed in km/h"
            value={values.study_speed_kmh}
            min={0}
            step={5}
            changed={values.study_speed_kmh !== defaults.study_speed_kmh}
            onChange={(study_speed_kmh) => setChanges({ study_speed_kmh })}
          />
        </SettingControl>
      </div>

      {values.study_mobility === "vehicular_traverse" && (
        <div className="grid gap-2.5 sm:grid-cols-2">
          <SettingControl title="Traverse min x (m)" hint={<C>traverse_min_distance_m</C>}>
            <NumberField
              ariaLabel="Traverse minimum distance"
              value={values.traverse_min_distance_m}
              min={10}
              step={25}
              changed={values.traverse_min_distance_m !== defaults.traverse_min_distance_m}
              onChange={(traverse_min_distance_m) => setChanges({ traverse_min_distance_m })}
            />
          </SettingControl>
          <SettingControl title="Traverse max x (m)" hint={<C>traverse_max_distance_m</C>}>
            <NumberField
              ariaLabel="Traverse maximum distance"
              value={values.traverse_max_distance_m}
              min={50}
              step={25}
              changed={values.traverse_max_distance_m !== defaults.traverse_max_distance_m}
              onChange={(traverse_max_distance_m) => setChanges({ traverse_max_distance_m })}
            />
          </SettingControl>
        </div>
      )}

      {loadSweep ? (
        <SettingControl
          title="Sweep cell load (load_rho)"
          hint={
            typeof sweepParsed === "string" ? (
              <span className="text-destructive">{sweepParsed}</span>
            ) : (
              <>
                Generates {sweepParsed.length} conditions (<C>rho-000</C>…) while keeping spatial distribution, BG bitrate, arrivals and mobility fixed in{" "}
                <C>base</C>.
              </>
            )
          }
        >
          <Input
            aria-label="Comma-separated load_rho sweep values"
            value={settings.loadSweepValues}
            className="h-8 font-mono text-xs"
            onChange={(event) => updateSetting("loadSweepValues", event.target.value)}
          />
        </SettingControl>
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2">
          <SettingControl
            title="Normalized cell load (ρ)"
            hint={
              <>
                <C>load_rho</C> · ~{lambdaBg} active TCP BG UEs
              </>
            }
          >
            <NumberField
              ariaLabel="Normalized cell load rho"
              value={values.load_rho}
              min={0}
              step={0.1}
              changed={values.load_rho !== defaults.load_rho}
              onChange={(load_rho) =>
                setChanges({
                  load_rho: Math.min(2, load_rho),
                  ...(load_rho > 0 && values.bg_spatial === "none" ? { bg_spatial: "cell_disk" } : {}),
                })
              }
            />
          </SettingControl>
          <SettingControl title="BG rate per UE (Mbps)" hint={<C>bg_bitrate_mbps</C>}>
            <NumberField
              ariaLabel="Background bitrate per UE in Mbps"
              value={values.bg_bitrate_mbps}
              min={0.1}
              step={0.5}
              changed={values.bg_bitrate_mbps !== defaults.bg_bitrate_mbps}
              onChange={(bg_bitrate_mbps) => setChanges({ bg_bitrate_mbps })}
            />
          </SettingControl>
        </div>
      )}

      {(loadSweep || values.load_rho > 0) && (
        <>
          {loadSweep && (
            <SettingControl title="BG rate per UE (Mbps)" hint={<C>bg_bitrate_mbps</C>}>
              <NumberField
                ariaLabel="Background bitrate per UE in Mbps"
                value={values.bg_bitrate_mbps}
                min={0.1}
                step={0.5}
                changed={values.bg_bitrate_mbps !== defaults.bg_bitrate_mbps}
                onChange={(bg_bitrate_mbps) => setChanges({ bg_bitrate_mbps })}
              />
            </SettingControl>
          )}
          <div className="grid gap-2.5 sm:grid-cols-[1.5fr_1fr]">
            <SettingControl title="BG spatial distribution" hint={<C>bg_spatial</C>}>
              <SegmentedChoice
                value={values.bg_spatial === "none" ? "cell_disk" : values.bg_spatial}
                options={[
                  ["cell_disk", "cell disk"],
                  ["homogeneous_ring", "good-SINR ring"],
                ]}
                onChange={(bg_spatial: Exclude<BgSpatialKind, "none">) => setChanges({ bg_spatial })}
              />
            </SettingControl>
            <SettingControl title="Max disk radius (m)" hint={<C>bg_max_distance_m</C>}>
              <NumberField
                ariaLabel="Maximum background disk radius"
                value={values.bg_max_distance_m}
                min={120}
                step={30}
                changed={values.bg_max_distance_m !== defaults.bg_max_distance_m}
                onChange={(bg_max_distance_m) => setChanges({ bg_max_distance_m: Math.min(700, bg_max_distance_m) })}
              />
            </SettingControl>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-[1.4fr_1fr]">
            <SettingControl title="UE arrivals / departures" hint={<C>arrival_mode</C>}>
              <SegmentedChoice
                value={values.arrival_mode}
                options={[
                  ["poisson", "stationary M/M/∞"],
                  ["mmpp", "MMPP bursts"],
                ]}
                onChange={(arrival_mode: ArrivalModeKind) => setChanges({ arrival_mode })}
              />
            </SettingControl>
            <SettingControl title="Mean hold τ (s)" hint={<C>mean_hold_s</C>}>
              <NumberField
                ariaLabel="Mean session hold duration in seconds"
                value={values.mean_hold_s}
                min={0.5}
                step={1}
                changed={values.mean_hold_s !== defaults.mean_hold_s}
                onChange={(mean_hold_s) => setChanges({ mean_hold_s })}
              />
            </SettingControl>
          </div>

          {values.arrival_mode === "mmpp" && (
            <div className="grid gap-2.5 sm:grid-cols-2">
              <SettingControl title="Burst modulation (±)" hint={<C>burst_amplitude</C>}>
                <NumberField
                  ariaLabel="MMPP burst modulation amplitude"
                  value={values.burst_amplitude}
                  min={0}
                  step={0.05}
                  changed={values.burst_amplitude !== defaults.burst_amplitude}
                  onChange={(burst_amplitude) => setChanges({ burst_amplitude: Math.min(0.95, burst_amplitude) })}
                />
              </SettingControl>
              <SettingControl title="Burst regime mean (s)" hint={<C>burst_regime_s</C>}>
                <NumberField
                  ariaLabel="MMPP burst regime mean duration"
                  value={values.burst_regime_s}
                  min={1}
                  step={2}
                  changed={values.burst_regime_s !== defaults.burst_regime_s}
                  onChange={(burst_regime_s) => setChanges({ burst_regime_s })}
                />
              </SettingControl>
            </div>
          )}
        </>
      )}

      <div className="grid gap-2.5 sm:grid-cols-2">
        <SettingControl title="Backhaul delay (ms)" hint={<C>backhaul_delay_ms</C>}>
          <NumberField
            ariaLabel="One-way backhaul delay in ms"
            value={values.backhaul_delay_ms}
            min={0}
            step={2}
            changed={values.backhaul_delay_ms !== defaults.backhaul_delay_ms}
            onChange={(backhaul_delay_ms) => setChanges({ backhaul_delay_ms })}
          />
        </SettingControl>
        <SettingControl title="Backhaul jitter (ms)" hint={<C>backhaul_jitter_ms</C>}>
          <NumberField
            ariaLabel="One-way backhaul jitter in ms"
            value={values.backhaul_jitter_ms}
            min={0}
            step={0.5}
            changed={values.backhaul_jitter_ms !== defaults.backhaul_jitter_ms}
            onChange={(backhaul_jitter_ms) => setChanges({ backhaul_jitter_ms })}
          />
        </SettingControl>
      </div>
    </div>
  );
}

function ConditionSection({ settings, updateSetting }: SectionProps) {
  const grid = settings.configOutputKind === "grid";
  if (usesConstantRateBackend(settings)) {
    return (
      <Section title="Conditions (C)" description="The constant_rate backend has no radio conditions.">
        <p className="text-xs text-muted-foreground">
          Every UE gets its own <T id="downlink_rate_mbps">{constantRateDownlinkMbps(settings)} Mbps</T>; set the rate in the panel above. Pick FikoRE to configure
          radio conditions.
        </p>
      </Section>
    );
  }
  if (!usesFikoreBackend(settings)) {
    return (
      <Section title="Conditions (C)" description="The mock backend has no conditions.">
        <p className="text-xs text-muted-foreground">It shares a fixed byte budget per step. Pick FikoRE to configure radio conditions.</p>
      </Section>
    );
  }

  const parametric = isParametricCondition(settings.conditionId);
  const condition = effectiveConditionView(settings.conditionId, settings.parametricOverrides[settings.conditionId]);
  const changedParametricIds = Object.keys(settings.parametricOverrides);
  const changedLegacyIds = Object.keys(settings.conditionOverrides);
  const allChangedIds = [...changedParametricIds, ...changedLegacyIds];

  function selectGridPreset(ids: readonly string[]) {
    updateSetting("gridSweepMode", "conditions");
    updateGridAxes(settings, updateSetting, { conditionIds: [...ids] });
  }

  return (
    <Section
      title="Conditions (C)"
      badge={isCore6Condition(settings.conditionId) ? "Core-6" : settings.conditionId === "CUSTOM" ? "parametric" : undefined}
      description={
        parametric ? (
          <>
            Parametric 5G cell (<T id="parametric_cell" asCode>network.parametric_cell</T>): synthesizes FikoRE INI, Poisson/MMPP session arrivals, spatial
            positions and trajectories from <C>Global.seed</C>.
          </>
        ) : (
          <>
            Legacy FikoRE scenario (INI and timeline). Changed values become <C>fikore_section_overrides</C> or <C>fikore_ue_overrides</C>.
          </>
        )
      }
    >
      {grid && (
        <div className="space-y-2">
          {parametric && (
            <SettingControl title="Grid condition mode">
              <SegmentedChoice
                value={settings.gridSweepMode}
                options={[
                  ["conditions", "selected conditions"],
                  ["load_sweep", "sweep load_rho"],
                ]}
                onChange={(mode) => updateSetting("gridSweepMode", mode)}
              />
            </SettingControl>
          )}
          {!usesParametricLoadSweep(settings) && (
            <SettingControl
              title="Conditions in the grid"
              hint={
                <span className="flex flex-wrap gap-1.5 pt-0.5">
                  <Button variant="outline" size="xs" onClick={() => selectGridPreset(CORE6_CONDITION_IDS)}>
                    Core-6
                  </Button>
                  <Button variant="outline" size="xs" onClick={() => selectGridPreset(ALL_LAYERED_CONDITION_IDS)}>
                    All M01–M11
                  </Button>
                  <Button variant="outline" size="xs" onClick={() => selectGridPreset(LEGACY_CONDITION_IDS)}>
                    Legacy C1–C8b
                  </Button>
                </span>
              }
            >
              <MultipleChoice
                values={effectiveGridAxes(settings).conditionIds}
                options={Object.keys(NETWORK_CONDITIONS).map((id) => [id, id])}
                onChange={(conditionIds) => updateGridAxes(settings, updateSetting, { conditionIds })}
              />
            </SettingControl>
          )}
        </div>
      )}

      <SettingControl
        title={grid ? (usesParametricLoadSweep(settings) ? "Base cell for sweep" : "Parameters of") : "Condition"}
        hint={
          <>
            {condition.dominantCause}
            {condition.timelineFile && (
              <>
                {" "}
                · timeline <C>{condition.timelineFile}</C>
              </>
            )}
          </>
        }
      >
        <Select value={settings.conditionId} onValueChange={(value) => updateSetting("conditionId", value)}>
          <SelectTrigger size="sm" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CONDITION_SELECTOR_GROUPS.map((group, groupIdx) => (
              <SelectGroup key={group.family}>
                {groupIdx > 0 && <SelectSeparator />}
                <SelectLabel>{group.label}</SelectLabel>
                {Object.entries(NETWORK_CONDITIONS)
                  .filter(([, entry]) => entry.family === group.family)
                  .map(([id, entry]) => {
                    const modified = Boolean(settings.conditionOverrides[id] || settings.parametricOverrides[id]);
                    return (
                      <SelectItem key={id} value={id}>
                        {id} · {entry.name}
                        {modified ? " (changed)" : ""}
                      </SelectItem>
                    );
                  })}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      </SettingControl>

      {parametric ? (
        <ParametricCellEditor settings={settings} updateSetting={updateSetting} />
      ) : (
        <table className="w-full">
          <tbody>
            {conditionParametersOf(settings.conditionId).map((parameter) => (
              <LegacyConditionParameterRow key={`${settings.conditionId}-${parameter.id}`} settings={settings} updateSetting={updateSetting} parameter={parameter} />
            ))}
          </tbody>
        </table>
      )}

      {allChangedIds.length > 0 && (
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>Changed: {allChangedIds.join(", ")}</span>
          <Button
            variant="outline"
            size="xs"
            onClick={() => {
              updateSetting("conditionOverrides", {});
              updateSetting("parametricOverrides", {});
            }}
          >
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
  const catalogue = CONTENT_CATALOGUES[settings.contentId];
  const maxSwipes = maxSwipesPerSession(settings);
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
          The SFV <C>userModel</C> of every session. SFV resolves all swipe times before the session starts. The selected content has {catalogue.videoCount}{" "}
          videos, so a session swipes at most {maxSwipes} times.
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

function ContentSection({ settings, updateSetting }: SectionProps) {
  const catalogue = CONTENT_CATALOGUES[settings.contentId];
  return (
    <Section
      title="Content"
      description={
        <>
          Select the content catalogue written to <C>content</C>: the 18-video Full HD ladder (<C>sfv-portrait-hd-90s.json</C>) or the 3-video smoke-test
          fixture.
        </>
      }
    >
      <SettingControl title="Catalogue" hint={<C>{catalogue.filePath}</C>}>
        <SegmentedChoice
          value={settings.contentId}
          options={(Object.keys(CONTENT_CATALOGUES) as ContentCatalogueId[]).map((id) => [id, id === "portrait_hd_90s" ? "18×8s Full HD" : "3×6s fixture"])}
          onChange={(contentId) => updateSetting("contentId", contentId)}
        />
      </SettingControl>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Videos</dt>
        <dd>
          {catalogue.videoIdsSummary} ({catalogue.videoCount} clips), played in order
        </dd>
        <dt className="text-muted-foreground">Length</dt>
        <dd>
          {catalogue.videoDurationS} s each, in {catalogue.segmentDurationS} s segments ({catalogue.videoDurationS / catalogue.segmentDurationS} per video)
        </dd>
        <dt className="text-muted-foreground">Video</dt>
        <dd>
          {catalogue.videoCodec}, {catalogue.frameRateFps} fps, portrait
        </dd>
        <dt className="text-muted-foreground">Audio</dt>
        <dd>
          {catalogue.audioRepresentation.codec}, {catalogue.audioRepresentation.bitrateKbps} kbps
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
          {catalogue.representations.map((representation) => (
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

/** The independent variables of an experiment: conditions, behaviours, swipes, content and, for a grid, the axes. */
export function ExperimentDesignCard({ settings, updateSetting }: SectionProps) {
  const grid = settings.configOutputKind === "grid";
  return (
    <Card className="gap-3">
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>Experiment design</CardTitle>
          <CardDescription>Change the parameters of the conditions, behaviours, swipes and content. The diagram and the config follow.</CardDescription>
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
        <ContentSection settings={settings} updateSetting={updateSetting} />
        {grid && <GridAxesSection settings={settings} updateSetting={updateSetting} />}
      </CardContent>
    </Card>
  );
}
