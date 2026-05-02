import Cell from "./Cell";
import FilterTimer from "./FilterTimer";
import type { Sernum, Vals } from "../types";

interface ReadingsGridProps {
  vals: Vals;
  sernum: Sernum;
  ophours: number | null;
}

export default function ReadingsGrid({ vals, sernum, ophours }: ReadingsGridProps) {
  const sign = (n: number) => (n > 0 ? "+" : "");
  const getval = (val: number | null | undefined, uom: string) => val != null ? `${val}${uom}` : "--"
  return (
    <div className="readings-panel">
      <Cell label="Setpoint"      value={getval(sernum.sp, '%')} amber />
      <Cell label="Ambient"       value={getval(vals.t, '°C')} />
      <Cell label="Alarm Min"     value={getval(sernum.lo, '%')} dim />
      <Cell label="Alarm Max"     value={getval(sernum.hi, '%')} dim />
      <Cell label="T1 cold side"  value={getval(vals.t1,'°C')} />
      <Cell label="T2 hot side"   value={getval(vals.t2,'°C')} />
      <Cell label="Hysteresis"    value={getval(sernum.hy, '%')} amber />
      <Cell label="RH Corr"       value={sernum.rhc != null ? `${sign(sernum.rhc)}${sernum.rhc}%` : "--"} dim />
      <Cell label="Log interval"  value={getval(sernum.lt, ' min')} dim />
      <Cell label="Operating hours"  value={ophours != null ? String(ophours).padStart(6, "0") : "------"} dim />
      <FilterTimer />
    </div>
  );
}
