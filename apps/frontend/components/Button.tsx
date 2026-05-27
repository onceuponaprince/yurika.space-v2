import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "destructive";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({
  variant = "primary",
  className = "",
  ...rest
}: Props) {
  const base =
    variant === "primary"
      ? "btn-primary"
      : variant === "destructive"
        ? "btn-destructive"
        : "btn-ghost";
  return <button {...rest} className={`${base} ${className}`} />;
}
