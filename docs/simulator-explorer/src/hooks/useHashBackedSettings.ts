import { useEffect, useState } from "react";
import { IMPLEMENTATION_STATES } from "@/data/implementationStates";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { DEFAULT_EXPLORER_SETTINGS, type ExplorerSettings } from "@/model/explorerSettings";

function readSettingsFromHash(): ExplorerSettings {
  const settings: ExplorerSettings = { ...DEFAULT_EXPLORER_SETTINGS };
  let hashParameters: URLSearchParams;
  try {
    hashParameters = new URLSearchParams(window.location.hash.slice(1));
  } catch {
    return settings;
  }
  const writable = settings as unknown as Record<string, unknown>;
  for (const [key, defaultValue] of Object.entries(DEFAULT_EXPLORER_SETTINGS)) {
    const raw = hashParameters.get(key);
    if (raw === null) continue;
    if (typeof defaultValue === "number") writable[key] = Number(raw);
    else if (typeof defaultValue === "boolean") writable[key] = raw === "true";
    else writable[key] = raw;
  }
  if (!NETWORK_CONDITIONS[settings.conditionId]) settings.conditionId = DEFAULT_EXPLORER_SETTINGS.conditionId;
  if (!IMPLEMENTATION_STATES[settings.implementationState]) settings.implementationState = DEFAULT_EXPLORER_SETTINGS.implementationState;
  return settings;
}

/** Explorer settings, kept in sync with the URL hash so a link reproduces a view. */
export function useHashBackedSettings() {
  const [settings, setSettings] = useState<ExplorerSettings>(readSettingsFromHash);

  useEffect(() => {
    const hash = new URLSearchParams(Object.entries(settings).map(([key, value]) => [key, String(value)])).toString();
    try {
      history.replaceState(null, "", `#${hash}`);
    } catch {
      // Some sandboxed previews forbid history changes.
    }
  }, [settings]);

  function updateSetting<K extends keyof ExplorerSettings>(key: K, value: ExplorerSettings[K]) {
    setSettings((previous) => {
      const next = { ...previous, [key]: value };
      if (key === "conditionId") {
        const plan = NETWORK_CONDITIONS[value as string].defaultPlanDownlinkMbps;
        next.planDownlinkMbps = plan ? String(plan) : "";
      }
      return next;
    });
  }

  return { settings, updateSetting };
}
