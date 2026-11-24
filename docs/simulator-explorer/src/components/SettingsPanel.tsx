import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";
import { GlossaryTerm as T } from "@/components/GlossaryTerm";
import { SegmentedChoice, SettingControl } from "@/components/SettingControls";
import { IMPLEMENTATION_STATES } from "@/data/implementationStates";
import { NETWORK_CONDITIONS, effectiveConditionView } from "@/data/networkConditions";
import { SIGNALING_LEVELS } from "@/data/signalingLevels";
import { effectiveGridAxes } from "@/model/experimentConfig";
import { signalingLevelNumber, usesConstantRateBackend, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

interface SettingsPanelProps {
  settings: ExplorerSettings;
  updateSetting: <K extends keyof ExplorerSettings>(key: K, value: ExplorerSettings[K]) => void;
}

const CONDITION_GROUPS: { family: "core6" | "layered_extended" | "custom"; label: string }[] = [
  { family: "core6", label: "Core-6 Test Plan (parametric)" },
  { family: "layered_extended", label: "Extended ablation (M02–M11)" },
  { family: "custom", label: "Custom parametric cell" },
];

export function SettingsPanel({ settings, updateSetting }: SettingsPanelProps) {
  const fikore = usesFikoreBackend(settings);
  const constantRate = usesConstantRateBackend(settings);
  const backendHint = fikore
    ? "TransportBackend over FikoreLink, Linux only"
    : constantRate
      ? "Dedicated constant rate per UE, no telemetry"
      : "Deterministic byte budget for tests";
  const condition = effectiveConditionView(settings.conditionId, settings.parametricOverrides[settings.conditionId]);
  // A grid writes the plan rate and the controller when any of its levels uses them
  const levels = settings.configOutputKind === "grid" ? effectiveGridAxes(settings).signalingLevels : [settings.signalingLevel];
  const highestLevel = Math.max(...levels.map(signalingLevelNumber));
  const levelScope = settings.configOutputKind === "grid" ? "a level of the grid" : "the level";
  return (
    <Card className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-x-5 gap-y-4 px-4">
      <SettingControl title="Implementation" hint={IMPLEMENTATION_STATES[settings.implementationState].hint}>
        <SegmentedChoice
          value={settings.implementationState}
          options={Object.entries(IMPLEMENTATION_STATES).map(([key, state]) => [key as ExplorerSettings["implementationState"], state.label])}
          onChange={(value) => updateSetting("implementationState", value)}
        />
      </SettingControl>
      <SettingControl title="Signaling level" hint={`${settings.signalingLevel} · ${SIGNALING_LEVELS[settings.signalingLevel].name}`}>
        <SegmentedChoice
          value={settings.signalingLevel}
          options={(Object.keys(SIGNALING_LEVELS) as ExplorerSettings["signalingLevel"][]).map((level) => [level, level])}
          onChange={(value) => updateSetting("signalingLevel", value)}
        />
      </SettingControl>
      <SettingControl title="Network backend" hint={backendHint}>
        <SegmentedChoice
          value={settings.networkBackend}
          options={[
            ["transport_fikore", "FikoRE"],
            ["constant_rate", "constant rate"],
            ["mock", "mock"],
          ]}
          onChange={(value) => updateSetting("networkBackend", value)}
        />
      </SettingControl>
      {constantRate ? (
        <SettingControl title={<T id="downlink_rate_mbps">Rate per UE (Mbps)</T>} hint='Instead of a FikoRE condition; the run uses condition "example-only"'>
          <Input
            type="number"
            min={0.1}
            step={0.5}
            value={settings.constantRateDownlinkMbps}
            placeholder="1"
            className="h-8"
            onChange={(event) => updateSetting("constantRateDownlinkMbps", event.target.value)}
          />
        </SettingControl>
      ) : (
        <SettingControl
          title="Condition"
          hint={
            fikore
              ? `${condition.downlinkMbpsBand[0]}–${condition.downlinkMbpsBand[1]} Mbps · RTT ${condition.rttMsBand[0]}–${condition.rttMsBand[1]} ms`
              : 'Mock runs use condition "example-only"'
          }
        >
          <Select value={settings.conditionId} onValueChange={(value) => updateSetting("conditionId", value)} disabled={!fikore}>
            <SelectTrigger size="sm" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CONDITION_GROUPS.map((group, groupIdx) => (
                <SelectGroup key={group.family}>
                  {groupIdx > 0 && <SelectSeparator />}
                  <SelectLabel>{group.label}</SelectLabel>
                  {Object.entries(NETWORK_CONDITIONS)
                    .filter(([, entry]) => entry.family === group.family)
                    .map(([id, entry]) => (
                      <SelectItem key={id} value={id}>
                        {id} · {entry.name}
                      </SelectItem>
                    ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </SettingControl>
      )}
      <SettingControl title={<T id="tcpConnectionMode">Transport</T>}>
        <SegmentedChoice
          value={settings.tcpConnectionMode}
          options={[
            ["persistent", "persistent"],
            ["multiplexed", "multiplexed"],
            ["fresh", "fresh"],
          ]}
          onChange={(value) => updateSetting("tcpConnectionMode", value)}
        />
        <div className="flex items-center gap-2 pt-1">
          <Checkbox
            id="acks-over-uplink"
            checked={settings.acksOverFikoreUplink}
            disabled={!fikore}
            onCheckedChange={(checked) => updateSetting("acksOverFikoreUplink", checked === true)}
          />
          <Label htmlFor="acks-over-uplink" className="text-sm font-normal">
            <T id="acksOverUplink">ACKs over FikoRE uplink</T>
          </Label>
        </div>
      </SettingControl>
      <SettingControl
        title={<T id="plan_downlink_mbps">Plan rate (Mbps)</T>}
        hint={highestLevel < 1 ? `Used from L1; pick L1 or higher as ${levelScope}` : highestLevel < 3 ? "The CSP controller is available from L3" : undefined}
      >
        <Input
          disabled={highestLevel < 1}
          type="number"
          min={0}
          step={1}
          value={settings.planDownlinkMbps}
          placeholder="none"
          className="h-8"
          onChange={(event) => updateSetting("planDownlinkMbps", event.target.value)}
        />
        {highestLevel >= 3 && (
          <div className="flex items-center gap-2 pt-1">
            <Checkbox
              id="dummy-controller"
              checked={settings.dummyCspControllerEnabled}
              disabled={settings.implementationState !== "master"}
              onCheckedChange={(checked) => updateSetting("dummyCspControllerEnabled", checked === true)}
            />
            <Label htmlFor="dummy-controller" className="text-sm font-normal">
              <T id="csp_controller">csp_controller: "dummy"</T>
            </Label>
          </div>
        )}
      </SettingControl>
    </Card>
  );
}
