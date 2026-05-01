// SVG gauge geometry — 240° sweep starting at bottom-left
const R = 80;
const CX = 100;
const CY = 100;
const CIRC = 2 * Math.PI * R;
const SWEEP = 240;
const ARC = CIRC * (SWEEP / 360);
const ROTATE = 150;

function clockRad(deg: number) {
  return (deg - 90) * (Math.PI / 180);
}
function pctToDeg(pct: number) {
  return 240 + (Math.max(0, Math.min(100, pct)) / 100) * 240;
}
function gaugePoint(pct: number, r: number): [number, number] {
  const a = clockRad(pctToDeg(pct));
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}

interface HumidityGaugeProps {
  rh: number;
  sp: number;
  loading: boolean;
  flag?: string;
  t?: number;
}

export default function HumidityGauge({ rh, sp, loading, flag, t }: HumidityGaugeProps) {
  const rhArc = (rh / 100) * ARC;
  const [spX1, spY1] = gaugePoint(sp, 71);
  const [spX2, spY2] = gaugePoint(sp, 93);
  const [spLabelX, spLabelY] = gaugePoint(sp, 60);

  return (
    <div className="gauge-panel">
      <span className="gauge-title">Relative Humidity</span>

      <svg
        viewBox="0 0 200 200"
        className="gauge-svg"
        aria-label={`Humidity: ${rh}%`}
      >
        <defs>
          <filter id="ph-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="amb-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* track */}
        <circle
          cx={CX} cy={CY} r={R}
          fill="none"
          stroke="var(--ph-dim)"
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={`${ARC} ${CIRC - ARC}`}
          transform={`rotate(${ROTATE} ${CX} ${CY})`}
        />
        {/* reading arc */}
        <circle
          cx={CX} cy={CY} r={R}
          fill="none"
          stroke="var(--ph)"
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={`${rhArc} ${CIRC - rhArc}`}
          transform={`rotate(${ROTATE} ${CX} ${CY})`}
          filter="url(#ph-glow)"
          className="gauge-arc"
        />
        {/* setpoint tick */}
        <line
          x1={spX1} y1={spY1} x2={spX2} y2={spY2}
          stroke="var(--amb)"
          strokeWidth={2.5}
          strokeLinecap="round"
          filter="url(#amb-glow)"
        />
        {/* reading value */}
        <text
          x={CX} y={CY - 10}
          textAnchor="middle"
          fill="var(--ph)"
          fontSize={46}
          fontFamily="var(--font-mono)"
          filter="url(#ph-glow)"
        >
          {loading ? "--" : rh}
        </text>
        <text
          x={CX} y={CY + 18}
          textAnchor="middle"
          fill="rgba(0,232,162,0.5)"
          fontSize={12}
          fontFamily="var(--font-sans)"
          letterSpacing="4"
          fontWeight="600"
        >
          % RH
        </text>
        {/* setpoint label */}
        <text
          x={spLabelX} y={spLabelY}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="var(--amb)"
          fontSize={8}
          fontFamily="var(--font-sans)"
          letterSpacing="1"
        >
          SP
        </text>
        {/* status flag */}
        {flag === "p" && (
          <text x={CX} y={CY + 40} textAnchor="middle" fill="rgba(0,232,162,0.5)" fontSize={8} fontFamily="var(--font-sans)" letterSpacing="3">
            PELTIER
          </text>
        )}
        {flag === "*" && (
          <text x={CX} y={CY + 40} textAnchor="middle" fill="var(--err)" fontSize={8} fontFamily="var(--font-sans)" letterSpacing="3">
            SENSOR ERR
          </text>
        )}
      </svg>

      <div className="gauge-legend">
        <span className="gauge-legend-line" />
        <span className="gauge-legend-label">SETPOINT {sp}%</span>
      </div>

      <div className="gauge-temp">
        <span className="gauge-temp-val">{loading ? "--" : (t != null ? `${t}°` : "--")}</span>
        <span className="gauge-temp-label">Ambient</span>
      </div>
    </div>
  );
}
