import { useEffect, useState, type ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";

// Small form controls shared by the settings panel and the experiment design card.

const SELECTED_ITEM_CLASSES = "data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground";

export function SettingControl({ title, hint, children }: { title: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-w-0 space-y-1.5">
      <div className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{title}</div>
      {children}
      {hint && <div className="text-xs leading-snug text-muted-foreground">{hint}</div>}
    </div>
  );
}

/** Pick one option. */
export function SegmentedChoice<V extends string>({ value, options, onChange }: { value: V; options: [V, string][]; onChange: (value: V) => void }) {
  return (
    <ToggleGroup type="single" size="sm" variant="outline" spacing={1} value={value} onValueChange={(next) => next && onChange(next as V)} className="flex-wrap">
      {options.map(([optionValue, label]) => (
        <ToggleGroupItem key={optionValue} value={optionValue} className={SELECTED_ITEM_CLASSES}>
          {label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

/** Pick any number of options, in the order of `options`. */
export function MultipleChoice<V extends string>({ values, options, onChange }: { values: V[]; options: [V, string][]; onChange: (values: V[]) => void }) {
  return (
    <ToggleGroup
      type="multiple"
      size="sm"
      variant="outline"
      spacing={1}
      value={values}
      onValueChange={(next) => onChange(options.map(([optionValue]) => optionValue).filter((optionValue) => next.includes(optionValue)))}
      className="flex-wrap"
    >
      {options.map(([optionValue, label]) => (
        <ToggleGroupItem key={optionValue} value={optionValue} className={SELECTED_ITEM_CLASSES}>
          {label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

interface NumberFieldProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  step?: number;
  integer?: boolean;
  /** Marks a value that differs from the default. */
  changed?: boolean;
  className?: string;
  ariaLabel: string;
}

/** A number input that keeps what is typed and reports only valid numbers. */
export function NumberField({ value, onChange, min, step, integer = false, changed = false, className, ariaLabel }: NumberFieldProps) {
  const [text, setText] = useState(String(value));
  useEffect(() => {
    setText((current) => (Number(current) === value ? current : String(value)));
  }, [value]);
  const parsed = Number(text);
  const valid = text.trim() !== "" && Number.isFinite(parsed) && (min === undefined || parsed >= min) && (!integer || Number.isInteger(parsed));
  return (
    <Input
      type="number"
      inputMode="decimal"
      aria-label={ariaLabel}
      aria-invalid={!valid}
      min={min}
      step={step ?? (integer ? 1 : "any")}
      value={text}
      className={cn("h-7 px-2 text-right font-mono text-xs", changed && "border-primary bg-primary/5", className)}
      onChange={(event) => {
        setText(event.target.value);
        const next = Number(event.target.value);
        if (event.target.value.trim() !== "" && Number.isFinite(next) && (min === undefined || next >= min) && (!integer || Number.isInteger(next))) onChange(next);
      }}
    />
  );
}
