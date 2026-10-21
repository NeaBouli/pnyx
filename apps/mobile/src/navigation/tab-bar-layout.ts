export const TAB_BAR_MAX_FONT_SIZE_MULTIPLIER = 1.4;

export function getTabBarMetrics(fontScale: number, bottomInset: number) {
  const scale = Math.min(Math.max(fontScale, 1), TAB_BAR_MAX_FONT_SIZE_MULTIPLIER);

  return {
    // 56dp leaves room for the icon, one label line and button padding.
    // A custom navigator height includes the bottom inset; its padding stays native.
    height: Math.ceil(56 * scale) + bottomInset,
    iconWidth: Math.ceil(31 * scale),
    iconHeight: Math.ceil(28 * scale),
  };
}
