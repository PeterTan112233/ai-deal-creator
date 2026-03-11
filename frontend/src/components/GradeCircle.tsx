import { cn } from "../lib/utils";

interface GradeCircleProps {
  grade: string;
  size?: "sm" | "md" | "lg";
}

const gradeColors: Record<string, string> = {
  A: "bg-green-100 text-green-700 ring-green-300",
  B: "bg-blue-100 text-blue-700 ring-blue-300",
  C: "bg-yellow-100 text-yellow-700 ring-yellow-300",
  D: "bg-orange-100 text-orange-700 ring-orange-300",
  F: "bg-red-100 text-red-700 ring-red-300",
};

export function GradeCircle({ grade, size = "md" }: GradeCircleProps) {
  const letter = grade?.[0]?.toUpperCase() ?? "?";
  const colorClass = gradeColors[letter] ?? "bg-gray-100 text-gray-700 ring-gray-300";
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-full font-bold ring-2",
        colorClass,
        size === "sm" && "h-10 w-10 text-lg",
        size === "md" && "h-14 w-14 text-2xl",
        size === "lg" && "h-20 w-20 text-3xl"
      )}
    >
      {grade}
    </div>
  );
}
