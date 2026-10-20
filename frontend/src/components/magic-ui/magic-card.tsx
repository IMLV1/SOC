"use client";

import type { CSSProperties, HTMLAttributes, PointerEvent } from "react";

type MagicCardProps = HTMLAttributes<HTMLDivElement> & {
  // Allow page-level color variants without coupling the card to page-specific CSS.
  glowColor?: string;
};

export function MagicCard({
  children,
  className = "",
  glowColor = "rgba(63, 231, 184, 0.16)",
  onPointerMove,
  onPointerLeave,
  ...props
}: MagicCardProps) {
  function updateSpotlight(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    // Store normalized coordinates so the CSS spotlight follows the pointer
    // regardless of the card's rendered size or position in the viewport.
    const x = ((event.clientX - bounds.left) / bounds.width) * 100;
    const y = ((event.clientY - bounds.top) / bounds.height) * 100;
    event.currentTarget.style.setProperty("--magic-x", `${x}%`);
    event.currentTarget.style.setProperty("--magic-y", `${y}%`);
    onPointerMove?.(event);
  }

  function clearSpotlight(event: PointerEvent<HTMLDivElement>) {
    // Removing the custom properties lets CSS return to its neutral fallback.
    event.currentTarget.style.removeProperty("--magic-x");
    event.currentTarget.style.removeProperty("--magic-y");
    onPointerLeave?.(event);
  }

  return (
    <div
      className={`magic-card ${className}`.trim()}
      style={{ "--magic-glow": glowColor } as CSSProperties}
      onPointerMove={updateSpotlight}
      onPointerLeave={clearSpotlight}
      {...props}
    >
      <div className="magic-card__content">{children}</div>
    </div>
  );
}
