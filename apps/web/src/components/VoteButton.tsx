import { clsx } from "clsx";

interface VoteButtonProps {
  label: string;
  value: number;
  selected: boolean;
  onClick: (v: number) => void;
  color?: string;
}

export default function VoteButton({
  label, value, selected, onClick
}: VoteButtonProps) {
  return (
    <button
      onClick={() => onClick(value)}
      className={clsx(
        "w-full py-4 px-6 rounded-xl font-semibold text-lg transition-all duration-200 border-2",
        selected
          ? "bg-blue-600 border-blue-400 text-white scale-105 shadow-lg shadow-blue-900/50"
          : "bg-gray-100 border-gray-200 text-gray-600 hover:border-gray-400 hover:text-gray-900"
      )}
    >
      {label}
    </button>
  );
}
