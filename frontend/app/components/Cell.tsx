interface CellProps {
  label: string;
  value: string | number;
  amber?: boolean;
  dim?: boolean;
  className?: string;
  valueClassName?: string;
}

export default function Cell({ label, value, amber, dim, className, valueClassName }: CellProps) {
  const valClass = `cell-val${amber ? " amber" : dim ? " dim" : ""}${valueClassName ? ` ${valueClassName}` : ""}`;
  return (
    <div className={`cell${className ? ` ${className}` : ""}`}>
      <span className="cell-label">{label}</span>
      <span className={valClass}>{value}</span>
    </div>
  );
}
