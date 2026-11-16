import { lastDays } from "@/lib/api";

const LABEL = new Intl.DateTimeFormat("id-ID", {
  weekday: "short",
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

type Props = {
  latest?: string;
  value?: string;
  onChange: (day: string) => void;
};

export default function TimeSlider({ latest, value, onChange }: Props) {
  if (!latest) return null;
  const days = lastDays(latest, 7);
  const index = Math.max(0, days.indexOf(value ?? latest));
  return (
    <div>
      <label
        htmlFor="day"
        className="flex justify-between text-xs text-neutral-400"
      >
        <span>Tanggal</span>
        <span className="text-neutral-100">
          {LABEL.format(new Date(`${days[index]}T00:00:00Z`))}
        </span>
      </label>
      <input
        id="day"
        type="range"
        min={0}
        max={days.length - 1}
        value={index}
        onChange={(e) => onChange(days[Number(e.target.value)])}
        aria-valuetext={days[index]}
        className="w-full accent-orange-600"
      />
    </div>
  );
}
