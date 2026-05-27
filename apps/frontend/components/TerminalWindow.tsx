import type { ReactNode } from "react";

interface Props {
  /** Optional small comment shown at the top, e.g. "// SECTION 03" */
  label?: string;
  /** Optional H2-equivalent shown beneath the label */
  heading?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function TerminalWindow({ label, heading, className = "", children }: Props) {
  return (
    <section className={`terminal-window terminal-body p-6 ${className}`}>
      {label && (
        <p className="mb-4 text-[9px] font-mono tracking-widest text-[#555]">{label}</p>
      )}
      {heading && (
        <h2 className="mb-6 text-[clamp(13px,2.2vw,18px)] font-display leading-relaxed">
          {heading}
        </h2>
      )}
      {children}
    </section>
  );
}
