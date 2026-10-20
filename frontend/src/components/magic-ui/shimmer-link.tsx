import Link from "next/link";
import type { ComponentProps } from "react";

type ShimmerLinkProps = ComponentProps<typeof Link> & {
  // Preserve Next.js Link navigation and accessibility props for every caller.
  className?: string;
};

export function ShimmerLink({
  className = "",
  children,
  ...props
}: ShimmerLinkProps) {
  return (
    <Link className={`magic-shimmer-link ${className}`.trim()} {...props}>
      <span className="magic-shimmer-link__label">{children}</span>
      {/* The glint is an effect, not a second label for assistive technology. */}
      <span className="magic-shimmer-link__glint" aria-hidden="true" />
    </Link>
  );
}
