type SceneVariant = "create" | "library" | "profiles" | "publishing" | "scheduling";

export function PremiumScene({ variant, compact = false }: { variant: SceneVariant; compact?: boolean }) {
  return (
    <div className={`premium-scene premium-scene--${variant}${compact ? " premium-scene--compact" : ""}`} aria-hidden="true">
      <div className="premium-scene__halo" />
      <div className="premium-scene__grid" />
      <div className="premium-scene__object">
        <span className="premium-scene__core" />
        <span className="premium-scene__ring premium-scene__ring--one" />
        <span className="premium-scene__ring premium-scene__ring--two" />
        <span className="premium-scene__satellite premium-scene__satellite--one" />
        <span className="premium-scene__satellite premium-scene__satellite--two" />
        <span className="premium-scene__satellite premium-scene__satellite--three" />
      </div>
    </div>
  );
}
