"use client";

import {
  ButtonHTMLAttributes,
  forwardRef,
  InputHTMLAttributes,
  ReactNode,
} from "react";
import { CaretDown, Check, Warning } from "@phosphor-icons/react";

import { cx } from "@/lib/cx";

/* ------------------------------------------------------------------
   Every control below takes its hover, press, focus, and disabled
   behaviour from components.css. Do not add state styling here.
   ------------------------------------------------------------------ */

export type ButtonVariant = "primary" | "ghost" | "soft" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", className, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        "btn",
        variant !== "primary" && variant,
        size === "sm" && "sm",
        className,
      )}
      {...rest}
    />
  );
});

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, className, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cx("input", invalid && "err", className)}
      {...rest}
    />
  );
});

export interface FieldProps {
  label?: string;
  /** Names the fix, not only the fault. */
  error?: string;
  children: ReactNode;
  className?: string;
}

export function Field({ label, error, children, className }: FieldProps) {
  return (
    <label className={cx("field", className)}>
      {label ? <span className="lab">{label}</span> : null}
      {children}
      {error ? (
        <span className="err-msg" role="alert">
          <Warning aria-hidden />
          {error}
        </span>
      ) : null}
    </label>
  );
}

export interface SelectProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Renders muted, for a value that is inherited rather than set. */
  inherited?: boolean;
}

/** A trigger, not a native select: the menu itself is the caller's business. */
export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select(
  { inherited, className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx("select", inherited && "inherit", className)}
      {...rest}
    >
      <span>{children}</span>
      <CaretDown aria-hidden />
    </button>
  );
});

export interface MenuOption {
  value: string;
  label: string;
  /** Rendered but not selectable, for a provider this machine cannot use. */
  disabled?: boolean;
}

export interface MenuProps {
  value: string;
  onChange: (value: string) => void;
  options: MenuOption[];
  label: string;
  /** Renders muted, for a value that is following something else. */
  inherited?: boolean;
  disabled?: boolean;
  className?: string;
}

/** A real menu. Native, so keyboard, typeahead, and phones come for free. */
export function Menu({
  value,
  onChange,
  options,
  label,
  inherited,
  disabled,
  className,
}: MenuProps) {
  return (
    <span className={cx("selectwrap", inherited && "inherit", className)}>
      <select
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
      <CaretDown aria-hidden />
    </span>
  );
}

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: SegmentedProps<T>) {
  return (
    <div className={cx("seg", className)} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          className={cx(option.value === value && "on")}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export interface StepperProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  format?: (value: number) => string;
  label: string;
  className?: string;
}

export function Stepper({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  format = String,
  label,
  className,
}: StepperProps) {
  return (
    <div className={cx("stepper", className)} role="group" aria-label={label}>
      <button
        type="button"
        aria-label={`Decrease ${label}`}
        disabled={value <= min}
        onClick={() => onChange(Math.max(min, value - step))}
      >
        &minus;
      </button>
      <span className="val" aria-live="polite">
        {format(value)}
      </span>
      <button
        type="button"
        aria-label={`Increase ${label}`}
        disabled={value >= max}
        onClick={() => onChange(Math.min(max, value + step))}
      >
        +
      </button>
    </div>
  );
}

export interface CheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}

export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
  className,
}: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={cx("check", checked && "on", className)}
      onClick={() => onChange(!checked)}
    >
      <Check weight="bold" aria-hidden />
    </button>
  );
}

export interface DropzoneProps {
  /** True while a file is dragged over the target. */
  armed?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  icon?: ReactNode;
  title: string;
  hint?: string;
  className?: string;
}

export function Dropzone({
  armed,
  disabled,
  onClick,
  icon,
  title,
  hint,
  className,
}: DropzoneProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cx("drop", armed && "armed", className)}
    >
      {icon}
      <b>{title}</b>
      {hint ? <span>{hint}</span> : null}
    </button>
  );
}

export interface TabItem<T extends string> {
  value: T;
  label: string;
  /** Optional trailing element, e.g. a status pill. */
  end?: ReactNode;
}

export interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  className,
}: TabsProps<T>) {
  return (
    <div className={cx("tabs", className)} role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={item.value === value}
          className={cx("tab", item.value === value && "on")}
          onClick={() => onChange(item.value)}
        >
          {item.label}
          {item.end}
        </button>
      ))}
    </div>
  );
}
