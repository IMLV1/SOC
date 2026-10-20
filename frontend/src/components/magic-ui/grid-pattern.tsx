type GridPatternProps = {
  // The optional label is styling metadata; the decorative element stays hidden from assistive tech.
  className?: string;
  label?: string;
};

export function GridPattern({ className = "", label }: GridPatternProps) {
  // The pattern is decorative; callers must provide meaningful text separately.
  return (
    <div
      className={`magic-grid-pattern ${className}`.trim()}
      aria-hidden="true"
      data-label={label}
    />
  );
}
