import { toReactStyle } from './style';

const OPTIONS = [
  ['manual_review', '수동 검토'],
  ['auto_create_pr', 'PR 자동 생성'],
  ['auto_merge_pr', 'PR 자동 병합'],
];

export const DEFAULT_POLICY_MATRIX = {
  High: ['manual_review', 'auto_create_pr', 'auto_create_pr', 'auto_merge_pr'],
  Medium: ['manual_review', 'auto_create_pr', 'auto_merge_pr', 'auto_merge_pr'],
  Low: ['auto_create_pr', 'auto_create_pr', 'auto_merge_pr', 'auto_merge_pr'],
};

const SEVERITY_COLORS = {
  Critical: '#C13D2A',
  High: '#B76A12',
  Medium: '#1876A8',
  Low: '#2F8F5B',
};

export function PolicyMatrix({ rows, matrix = DEFAULT_POLICY_MATRIX, onChange = null }) {
  return <div style={toReactStyle('box-sizing:border-box;background:#FFFFFF;border:1px solid #DDE1DB;border-radius:10px;overflow:hidden')}>
    <table style={toReactStyle('width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px')}>
      <thead><tr style={toReactStyle('height:32px;background:#F3F5F2')}>
        <th style={toReactStyle('width:22%;box-sizing:border-box;text-align:left;padding:0 16px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7;color:#687066;font-size:11px;font-weight:700')}><span style={toReactStyle('display:flex;align-items:center;gap:8px;white-space:nowrap')}><span>저장소 중요도</span><span aria-hidden="true" style={toReactStyle('display:block;width:1px;height:17px;background:#B8BEB6;transform:rotate(-35deg)')} /><span>취약점 심각도</span></span></th>
        {['Critical', 'High', 'Medium', 'Low'].map((severity) => <th key={severity} style={toReactStyle(`box-sizing:border-box;text-align:center;padding:0 10px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7;color:${SEVERITY_COLORS[severity]};font-size:11px;font-weight:700;letter-spacing:.01em`)}>{severity}</th>)}
      </tr></thead>
      <tbody>{rows.filter((row) => matrix[row.importanceLabel]).map((row) => <tr key={row.importanceLabel} style={toReactStyle('height:50px')}>
        <th style={toReactStyle(`box-sizing:border-box;text-align:left;padding:0 16px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7;font-size:12px;font-weight:700;color:${SEVERITY_COLORS[row.importanceLabel]}`)}>{row.importanceLabel}</th>
        {matrix[row.importanceLabel].map((value, index) => <td key={`${row.importanceLabel}-${index}`} style={toReactStyle('box-sizing:border-box;padding:8px 10px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7')}><select aria-label={`${row.importanceLabel} 저장소 ${['Critical', 'High', 'Medium', 'Low'][index]} 취약점 정책`} value={value} onChange={(event) => onChange?.(row.importanceLabel, index, event.target.value)} style={toReactStyle('width:100%;height:34px;box-sizing:border-box;padding:0 32px 0 10px;border:1px solid #D5DAD3;border-radius:7px;background-color:#FFFFFF;background-image:url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'8\' height=\'5\' viewBox=\'0 0 8 5\'%3E%3Cpath d=\'m1 1 3 3 3-3\' fill=\'none\' stroke=\'%238B9086\' stroke-width=\'1.2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;background-size:8px 5px;color:#1B1E1A;font-family:inherit;font-size:12px;font-weight:600;appearance:none;cursor:pointer')}>{OPTIONS.map(([optionValue, label]) => <option key={optionValue} value={optionValue}>{label}</option>)}</select></td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}
