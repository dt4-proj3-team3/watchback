import { toReactStyle } from './style';

export function EvidenceCard({
  signalLabel,
  previousValueLabel,
  currentValueLabel,
  observedLabel,
  reasonSummary,
}) {
  return <div style={toReactStyle('padding:11px 14px;background:#F5F6F3;border-radius:8px')}>
    <div style={toReactStyle('display:flex;align-items:center;gap:12px;flex-wrap:wrap')}>
      <span style={toReactStyle('font-size:12px;font-weight:600;color:#1B1E1A;width:170px;flex:none;white-space:nowrap')}>
        {signalLabel}
      </span>
      <span className="watchback-evidence-values" style={toReactStyle('display:flex;align-items:center;gap:12px;margin-left:auto;white-space:nowrap')}>
        <span style={toReactStyle('font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#8B9086')}>
          {previousValueLabel}
        </span>
        <span style={toReactStyle('color:#D2D5CD')}>→</span>
        <span style={toReactStyle('font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#1B1E1A;font-weight:600')}>
          {currentValueLabel}
        </span>
      </span>
    </div>
    {observedLabel && <div style={toReactStyle('font-size:11px;color:#8B9086;margin-top:3px')}>
      {`관찰일 ${observedLabel}`}
    </div>}
    <div style={toReactStyle(`font-size:12.5px;color:#5B6058;line-height:1.5;margin-top:${observedLabel ? '5px' : '6px'}`)}>
      {reasonSummary}
    </div>
  </div>;
}
