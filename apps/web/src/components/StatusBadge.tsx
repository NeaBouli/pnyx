interface StatusBadgeProps {
  status: string;
  locale?: string;
}

const STATUS_CONFIG: Record<string, { label_el: string; label_en: string; color: string }> = {
  ANNOUNCED:        { label_el: "Ανακοινώθηκε",      label_en: "Announced",        color: "bg-gray-700 text-gray-300" },
  ACTIVE:           { label_el: "Ανοιχτή Ψηφοφορία", label_en: "Voting Open",      color: "bg-green-900 text-green-300 animate-pulse" },
  WINDOW_24H:       { label_el: "24ω πριν Βουλή",    label_en: "24h Window",       color: "bg-yellow-900 text-yellow-300 animate-pulse" },
  PARLIAMENT_VOTED: { label_el: "Βουλή Αποφάσισε",   label_en: "Parliament Voted", color: "bg-blue-900 text-blue-300" },
  OPEN_END:         { label_el: "Αρχείο",             label_en: "Archive",          color: "bg-purple-900 text-purple-300" },
};

export default function StatusBadge({ status, locale = "el" }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG["ANNOUNCED"];
  const label = locale === "el" ? cfg.label_el : cfg.label_en;
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${cfg.color}`}>
      {status === "ACTIVE" || status === "WINDOW_24H" ? "● " : ""}{label}
    </span>
  );
}
