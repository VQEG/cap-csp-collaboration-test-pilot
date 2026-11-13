import { useEffect, useState } from "react";
import { IMPLEMENTATION_STATES } from "@/data/implementationStates";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { BEHAVIOR_MIXES } from "@/data/playerBehaviors";
import { DEFAULT_EXPLORER_SETTINGS, NETWORK_BACKEND_KINDS, type ExplorerSettings } from "@/model/explorerSettings";

/** An object or array setting from its JSON form; the default when it does not parse or has another shape. */
function parseJsonSetting(raw: string, defaultValue: object): unknown {
  try {
    const value: unknown = JSON.parse(raw);
    if (Array.isArray(defaultValue) ? Array.isArray(value) : value !== null && typeof value === "object" && !Array.isArray(value)) {
      return Array.isArray(defaultValue) ? value : { ...defaultValue, ...(value as object) };
    }
  } catch {
    // Keep the default
  }
  return defaultValue;
}

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
    else if (typeof defaultValue === "object") writable[key] = parseJsonSetting(raw, defaultValue);
    else writable[key] = raw;
  }
  // A link may hold only some behaviour parameters; fill in the others (without changing the defaults)
  const defaultParameters = DEFAULT_EXPLORER_SETTINGS.behaviorParameters;
  settings.behaviorParameters = {
    simple: { ...defaultParameters.simple, ...settings.behaviorParameters.simple },
    preload: { ...defaultParameters.preload, ...settings.behaviorParameters.preload },
  };
  if (!BEHAVIOR_MIXES[settings.behaviorMix]) settings.behaviorMix = DEFAULT_EXPLORER_SETTINGS.behaviorMix;
  if (!NETWORK_CONDITIONS[settings.conditionId]) settings.conditionId = DEFAULT_EXPLORER_SETTINGS.conditionId;
  if (!NETWORK_BACKEND_KINDS.includes(settings.networkBackend)) settings.networkBackend = DEFAULT_EXPLORER_SETTINGS.networkBackend;
  if (!IMPLEMENTATION_STATES[settings.implementationState]) settings.implementationState = DEFAULT_EXPLORER_SETTINGS.implementationState;
  return settings;
}

/** Explorer settings, kept in sync with the URL hash so a link reproduces a view. */
export function useHashBackedSettings() {
  const [settings, setSettings] = useState<ExplorerSettings>(readSettingsFromHash);

  useEffect(() => {
    const hash = new URLSearchParams(
      Object.entries(settings).map(([key, value]) => [key, typeof value === "object" ? JSON.stringify(value) : String(value)]),
    ).toString();
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
