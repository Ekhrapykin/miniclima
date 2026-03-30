import Cell from "./Cell";
import type { Sernum, Vals } from "../types";

interface ReadingsGridProps {
  vals: Vals;
  sernum: Sernum;
  ophours: number | null;
}

export default function ReadingsGrid({ vals, sernum, ophours }: ReadingsGridProps) {
  const sign = (n: number) => (n > 0 ? "+" : "");

  return (
    <div className="readings-panel">
      <Cell label="T1 cold side" value={vals.t1 != null ? `${vals.t1}°C` : "--"} />
      <Cell label="T2 hot side"  value={vals.t2 != null ? `${vals.t2}°C` : "--"} />
      <Cell label="Setpoint"     value={sernum.sp != null ? `${sernum.sp}%` : "--"} amber />
      <Cell label="Hysteresis"   value={sernum.hy != null ? `×${sernum.hy}` : "--"} amber />
      <Cell label="Alarm Lo"     value={sernum.lo != null ? `${sernum.lo}%` : "--"} dim />
      <Cell label="Alarm Hi"     value={sernum.hi != null ? `${sernum.hi}%` : "--"} dim />
      <Cell label="Log interval" value={sernum.lt != null ? `${sernum.lt} min` : "--"} dim />
      <Cell label="Temp offset"  value={sernum.to != null ? `${sign(sernum.to)}${sernum.to}°C` : "--"} dim />
      <div className="cell cell-full">
        <span className="cell-label">Operating hours</span>
        <span className="cell-val dim ophours-val">
          {ophours != null ? String(ophours).padStart(6, "0") : "------"}
        </span>
      </div>
    </div>
  );
}
