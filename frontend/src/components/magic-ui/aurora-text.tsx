import type { HTMLAttributes } from "react";

type AuroraTextProps = HTMLAttributes<HTMLSpanElement>;

// Callers supply the semantic text; this component adds visual treatment only.
export function AuroraText({ className = "", ...props }: AuroraTextProps) {
  return <span className={`aurora-text ${className}`.trim()} {...props} />;
}
