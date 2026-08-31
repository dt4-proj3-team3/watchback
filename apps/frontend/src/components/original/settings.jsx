import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Settings({ values }) {
  return (
    <>
    {values.isSettingsView && (
      <>
        <div className="watchback-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0 0 6px;letter-spacing:-0.01em")}>
              {"자동조치 정책"}
            </h1>
            <p style={toReactStyle("font-size:14px;color:#5B6058;margin:0;line-height:1.6")}>
              {"저장소 중요도와 취약점 심각도 조합에 따라 조직 전체에 적용되는 자동조치 방식을 관리합니다."}
            </p>
            <p style={toReactStyle("font-size:12.5px;color:#8B9086;margin:6px 0 0;line-height:1.6")}>
              {values.isDemo
                ? "현재 모든 위험도 조합은 자동 병합 없이 업데이트 PR 생성까지만 허용합니다."
                : "실제 자동조치 정책은 아직 DB와 연동되지 않았습니다."}
            </p>
          </div>
          <div style={toReactStyle("height:80px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:14px 18px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;gap:16px")}>
            <div>
              <div style={toReactStyle("font-size:14px;font-weight:700;margin-bottom:4px")}>
                {"데이터 소스"}
              </div>
              <div style={toReactStyle("font-size:12.5px;color:#8B9086;line-height:1.5")}>
                {"대시보드, 재검토 목록·상세와 저장소에서 사용할 데이터 소스를 선택합니다. DB 오류 시 Demo로 자동 전환하지 않습니다."}
              </div>
            </div>
            <div style={toReactStyle("display:flex;align-items:center;gap:8px")}>
              <button type="button" onClick={() => values.onDataSourceChange('demo')} aria-pressed={values.dataSource === 'demo'} style={toReactStyle(`font-size:12.5px;font-weight:600;font-family:inherit;color:${values.dataSource === 'demo' ? '#FFFFFF' : '#5B6058'};background:${values.dataSource === 'demo' ? '#2F8F5B' : '#FFFFFF'};border:1px solid ${values.dataSource === 'demo' ? '#2F8F5B' : '#D2D5CD'};border-radius:7px;padding:7px 12px;cursor:pointer`)}>
                {"Demo"}
              </button>
              <button type="button" onClick={() => values.onDataSourceChange('db')} aria-pressed={values.dataSource === 'db'} style={toReactStyle(`font-size:12.5px;font-weight:600;font-family:inherit;color:${values.dataSource === 'db' ? '#FFFFFF' : '#5B6058'};background:${values.dataSource === 'db' ? '#2F8F5B' : '#FFFFFF'};border:1px solid ${values.dataSource === 'db' ? '#2F8F5B' : '#D2D5CD'};border-radius:7px;padding:7px 12px;cursor:pointer`)}>
                {"DB"}
              </button>
            </div>
          </div>
          {values.isDemo ? (
            <div style={toReactStyle("height:273px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:20px 22px;overflow-x:auto")}>
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
                            <select disabled title="UI Preview · 후속 구현" style={toReactStyle("font-size:12.5px;font-family:inherit;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:7px;padding:6px 8px;cursor:not-allowed;width:100%;color:#8B9086")} value={cell.value} onChange={cell.onChange}>
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
          ) : (
            <div style={toReactStyle("height:273px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:91px 22px;text-align:center")}>
              <div style={toReactStyle("font-size:14px;font-weight:600;margin-bottom:6px")}>
                {"자동조치 정책 DB 연동은 아직 구현되지 않았습니다."}
              </div>
              <div style={toReactStyle("font-size:12.5px;color:#8B9086;line-height:1.6")}>
                {"DB 모드에서는 합성 정책을 표시하지 않습니다."}
              </div>
            </div>
          )}
          <div style={toReactStyle("font-size:12px;color:#8B9086;margin-top:12px")}>
            {values.isDemo
              ? "자동조치 정책은 UI Preview이며 이 화면에서 변경되지 않습니다."
              : "실제 정책 조회·변경은 후속 구현 범위입니다."}
          </div>
        </div>
      </>
    )}
    </>
  );
}
