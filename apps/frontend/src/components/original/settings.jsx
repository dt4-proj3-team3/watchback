import { useEffect } from 'react';
import { toReactStyle } from './style';

const POLICY_OPTIONS = [
  { value: 'manual_review', label: '수동 검토' },
  { value: 'auto_create_pr', label: 'PR 자동 생성' },
  { value: 'auto_merge_pr', label: 'PR 자동 병합' },
];

const DEFAULT_POLICY_MATRIX = {
  High: ['manual_review', 'auto_create_pr', 'auto_create_pr', 'auto_merge_pr'],
  Medium: ['manual_review', 'auto_create_pr', 'auto_merge_pr', 'auto_merge_pr'],
  Low: ['auto_create_pr', 'auto_create_pr', 'auto_merge_pr', 'auto_merge_pr'],
};

export function Settings({ values }) {
  const { dataSource, isSettingsView, onDataSourceChange } = values;

  useEffect(() => {
    if (isSettingsView && dataSource !== 'db') {
      onDataSourceChange('db');
    }
  }, [dataSource, isSettingsView, onDataSourceChange]);

  return (
    <>
    {values.isSettingsView && (
      <>
        <div className="watchback-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0;letter-spacing:-0.01em")}>
              {"자동조치 정책"}
            </h1>
          </div>
          <div style={toReactStyle("box-sizing:border-box;background:#FFFFFF;border:1px solid #DDE1DB;border-radius:10px;overflow:hidden")}>
            <table style={toReactStyle("width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px")}>
              <thead>
                <tr style={toReactStyle("height:32px;background:#F3F5F2")}>
                  <th style={toReactStyle("width:24%;box-sizing:border-box;text-align:left;padding:0 16px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7;color:#687066;font-size:11px;font-weight:700")}>
                    <span style={toReactStyle("display:flex;align-items:center;gap:8px;white-space:nowrap")}>
                      <span>저장소 중요도</span>
                      <span aria-hidden="true" style={toReactStyle("display:block;width:1px;height:17px;background:#B8BEB6;transform:rotate(-35deg)")} />
                      <span>취약점 심각도</span>
                    </span>
                  </th>
                  {['Critical', 'High', 'Medium', 'Low'].map((severity) => (
                    <th key={severity} style={toReactStyle("box-sizing:border-box;text-align:center;padding:0 10px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7;color:#687066;font-size:11px;font-weight:700;letter-spacing:.01em")}>{severity}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {values.policyMatrixRows.filter((row) => ['High', 'Medium', 'Low'].includes(row.importanceLabel)).map((row) => (
                  <tr key={row.importanceLabel} style={toReactStyle("height:50px")}>
                    <th style={toReactStyle(`box-sizing:border-box;text-align:left;padding:0 16px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7;font-size:12px;font-weight:700;color:${row.importanceLabel === 'High' ? '#A76613' : '#666D64'}`)}>{row.importanceLabel}</th>
                    {row.cells.map((cell, index) => (
                      <td key={`${row.importanceLabel}-${index}`} style={toReactStyle("box-sizing:border-box;padding:8px 10px;border-right:1px solid #D9DED7;border-bottom:1px solid #D9DED7")}>
                        <select disabled aria-label={`${row.importanceLabel} 저장소 ${['Critical', 'High', 'Medium', 'Low'][index]} 취약점 정책`} value={DEFAULT_POLICY_MATRIX[row.importanceLabel][index]} onChange={cell.onChange} style={toReactStyle("width:100%;height:34px;box-sizing:border-box;padding:0 30px 0 12px;border:1px solid #D5DAD3;border-radius:7px;background-color:#FFFFFF;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5' viewBox='0 0 8 5'%3E%3Cpath d='m1 1 3 3 3-3' fill='none' stroke='%238B9086' stroke-width='1.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 11px center;background-size:8px 5px;color:#1B1E1A;font-family:inherit;font-size:12px;font-weight:600;opacity:1;appearance:none;-webkit-text-fill-color:#1B1E1A")}>
                          {POLICY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                        </select>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </>
    )}
    </>
  );
}
