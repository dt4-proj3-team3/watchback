import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Settings({ values }) {
  return (
    <>
    {values.isSettingsView && (
      <>
        <div style={toReactStyle("max-width:960px;margin:0 auto;padding:40px 32px 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:22px;font-weight:700;margin:0 0 6px;letter-spacing:-0.01em")}>
              {"자동조치 정책"}
            </h1>
            <p style={toReactStyle("font-size:14px;color:#5B6058;margin:0;line-height:1.6")}>
              {"저장소 중요도와 취약점 심각도 조합에 따라 조직 전체에 적용되는 자동조치 방식을 관리합니다."}
            </p>
            <p style={toReactStyle("font-size:12.5px;color:#8B9086;margin:6px 0 0;line-height:1.6")}>
              {"현재 모든 위험도 조합은 자동 병합 없이 업데이트 PR 생성까지만 허용합니다."}
            </p>
          </div>
          <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:18px 22px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;gap:16px")}>
            <div>
              <div style={toReactStyle("font-size:14px;font-weight:700;margin-bottom:4px")}>
                {"데이터 소스"}
              </div>
              <div style={toReactStyle("font-size:12.5px;color:#8B9086;line-height:1.5")}>
                {"현재는 데모 데이터로 화면을 확인할 수 있습니다."}
              </div>
            </div>
            <div style={toReactStyle("display:flex;align-items:center;gap:8px")}>
              <button type="button" style={toReactStyle("font-size:12.5px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:1px solid #2F8F5B;border-radius:7px;padding:7px 12px")}>
                {"Demo"}
              </button>
              <button type="button" disabled title="DB 연동 전입니다." style={toReactStyle("font-size:12.5px;font-weight:600;font-family:inherit;color:#A3A79F;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:7px;padding:7px 12px;cursor:not-allowed")}>
                {"DB · 연동 전"}
              </button>
            </div>
          </div>
          <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px 22px;overflow-x:auto")}>
            <table style={toReactStyle("border-collapse:collapse;width:100%;font-size:13px")}>
              <thead>
                <tr>
                  <th style={toReactStyle("text-align:left;padding:8px 12px;color:#8B9086;font-size:11px;font-weight:600;letter-spacing:.02em;border-bottom:1px solid #E4E6E1")}>
                    {"저장소 중요도 ＼ 취약점 심각도"}
                  </th>
                  {values.importanceLevelOptions.map((opt, _index0) => (
                    <Fragment key={_index0}>
                      <th style={toReactStyle("text-align:left;padding:8px 12px;color:#8B9086;font-size:11px;font-weight:600;letter-spacing:.02em;border-bottom:1px solid #E4E6E1")}>
                        {`${opt.label}`}
                      </th>
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {values.policyMatrixRows.map((row, _index0) => (
                  <Fragment key={_index0}>
                    <tr>
                      <td style={toReactStyle("padding:10px 12px;font-weight:600;border-bottom:1px solid #F0F1EE")}>
                        {`${row.importanceLabel}`}
                      </td>
                      {row.cells.map((cell, _index1) => (
                        <Fragment key={_index1}>
                          <td style={toReactStyle("padding:8px 10px;border-bottom:1px solid #F0F1EE")}>
                            <select style={toReactStyle("font-size:12.5px;font-family:inherit;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:7px;padding:6px 8px;cursor:pointer;width:100%")} value={cell.value} onChange={cell.onChange}>
                              {values.modeSelectOptions.map((opt, _index2) => (
                                <Fragment key={_index2}>
                                  <option value={opt.value}>
                                    {`${opt.label}`}
                                  </option>
                                </Fragment>
                              ))}
                            </select>
                          </td>
                        </Fragment>
                      ))}
                    </tr>
                  </Fragment>
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
