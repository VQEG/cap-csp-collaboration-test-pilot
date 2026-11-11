import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { GlossaryTerm as T } from "@/components/GlossaryTerm";
import { IMPLEMENTATION_STATES } from "@/data/implementationStates";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { SIGNALING_LEVELS } from "@/data/signalingLevels";
import { usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

interface SettingsPanelProps {
  settings: ExplorerSettings;
  updateSetting: <K extends keyof ExplorerSettings>(key: K, value: ExplorerSettings[K]) => void;
}

function SettingControl({ title, hint, children }: { title: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-w-0 space-y-1.5">
      <div className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{title}</div>
      {children}
      {hint && <div className="text-xs leading-snug text-muted-foreground">{hint}</div>}
    </div>
  );
}

function SegmentedChoice<V extends string>({ value, options, onChange }: { value: V; options: [V, string][]; onChange: (value: V) => void }) {
  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      spacing={1}
      value={value}
      onValueChange={(next) => next && onChange(next as V)}
      className="flex-wrap"
    >
      {options.map(([optionValue, label]) => (
        <ToggleGroupItem
          key={optionValue}
          value={optionValue}
          className="data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
        >
          {label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

export function SettingsPanel({ settings, updateSetting }: SettingsPanelProps) {
  const fikore = usesFikoreBackend(settings);
  const condition = NETWORK_CONDITIONS[settings.conditionId];
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
      <SettingControl title="Network backend" hint={fikore ? "TransportBackend over FikoreLink, Linux only" : "Deterministic byte budget for tests"}>
        <SegmentedChoice
          value={settings.networkBackend}
          options={[
            ["transport_fikore", "FikoRE"],
            ["mock", "mock"],
          ]}
          onChange={(value) => updateSetting("networkBackend", value)}
        />
      </SettingControl>
      <SettingControl
        title="Condition"
        hint={fikore ? `${condition.downlinkMbpsBand[0]}–${condition.downlinkMbpsBand[1]} Mbps · RTT ${condition.rttMsBand[0]}–${condition.rttMsBand[1]} ms` : 'Mock runs use condition "example-only"'}
      >
        <Select value={settings.conditionId} onValueChange={(value) => updateSetting("conditionId", value)} disabled={!fikore}>
          <SelectTrigger size="sm" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(NETWORK_CONDITIONS).map(([id, entry]) => (
              <SelectItem key={id} value={id}>
                {id} · {entry.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SettingControl>
      <SettingControl title="Player behavior" hint="All UEs in a cell use the same policy">
        <SegmentedChoice
          value={settings.playerBehavior}
          options={[
            ["simple", "B1 simple"],
            ["preload", "B2 preload"],
          ]}
          onChange={(value) => updateSetting("playerBehavior", value)}
        />
      </SettingControl>
      <SettingControl title="Video UEs" hint="Milestone 1 assumes four per cell">
        <SegmentedChoice
          value={String(settings.videoUeCount)}
          options={[
            ["1", "1"],
            ["2", "2"],
            ["4", "4"],
          ]}
          onChange={(value) => updateSetting("videoUeCount", Number(value) as ExplorerSettings["videoUeCount"])}
        />
      </SettingControl>
      <SettingControl title={<T id="tcpConnectionMode">Transport</T>}>
        <SegmentedChoice
          value={settings.tcpConnectionMode}
          options={[
            ["persistent", "persistent"],
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
      <SettingControl title={<T id="plan_downlink_mbps">Plan rate (Mbps)</T>}>
        <Input
          type="number"
          min={0}
          step={1}
          value={settings.planDownlinkMbps}
          placeholder="none"
          className="h-8"
          onChange={(event) => updateSetting("planDownlinkMbps", event.target.value)}
        />
        <div className="flex items-center gap-2 pt-1">
          <Checkbox
            id="dummy-controller"
            checked={settings.dummyCspControllerEnabled}
            disabled={settings.implementationState !== "pr8"}
            onCheckedChange={(checked) => updateSetting("dummyCspControllerEnabled", checked === true)}
          />
          <Label htmlFor="dummy-controller" className="text-sm font-normal">
            <T id="csp_controller">csp_controller: "dummy"</T>
          </Label>
        </div>
      </SettingControl>
    </Card>
  );
}
