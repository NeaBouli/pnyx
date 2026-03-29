import { DivergenceResult } from "@/lib/api";

interface DivergenceCardProps {
  divergence: DivergenceResult;
  locale?: string;
}

export default function DivergenceCard({ divergence, locale = "el" }: DivergenceCardProps) {
  const score = Math.round(divergence.score * 100);
  const isHigh = divergence.score > 0.4;
  const isMedium = divergence.score > 0.2;

  const borderColor = isHigh ? "border-red-700" : isMedium ? "border-yellow-700" : "border-green-700";
  const bgColor = isHigh ? "bg-red-950" : isMedium ? "bg-yellow-950" : "bg-green-950";
  const textColor = isHigh ? "text-red-300" : isMedium ? "text-yellow-300" : "text-green-300";

  return (
    <div className={`rounded-2xl p-6 border ${borderColor} ${bgColor}`}>
      <div className="flex justify-between items-start mb-3">
        <h3 className="font-bold text-white">
          {locale === "el" ? "Απόκλιση από Βουλή" : "Divergence from Parliament"}
        </h3>
        <span className={`text-2xl font-bold ${textColor}`}>{score}%</span>
      </div>
      <p className={`font-semibold mb-2 ${textColor}`}>{divergence.label_el}</p>
      <p className="text-gray-300 text-sm leading-relaxed">{divergence.headline_el}</p>
      <div className="flex gap-4 mt-4 text-sm text-gray-400">
        <span>
          {locale === "el" ? "Πολίτες:" : "Citizens:"}{" "}
          <strong className="text-white">{divergence.citizen_majority}</strong>
        </span>
        {divergence.parliament_result && (
          <span>
            {locale === "el" ? "Βουλή:" : "Parliament:"}{" "}
            <strong className="text-white">{divergence.parliament_result}</strong>
          </span>
        )}
      </div>
    </div>
  );
}
