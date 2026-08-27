import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Repositories({ values }) {
  return (
    <>
    {values.isReposView && (
      <>
        <div className="watchback-page" style={toReactStyle("max-width:960px;margin:0 auto;padding:40px 32px 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:22px;font-weight:700;margin:0 0 6px;letter-spacing:-0.01em")}>
              {"저장소"}
            </h1>
            <p style={toReactStyle("font-size:14px;color:#5B6058;margin:0;line-height:1.6")}>
              {"저장소 중요도와 자동조치 정책을 확인하고, 저장소별 재검토 항목으로 이동할 수 있습니다."}
            </p>
          </div>
          <div style={toReactStyle("display:flex;flex-direction:column;gap:10px")}>
            {!values.hasRepositories && (
              <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:28px 20px;text-align:center;font-size:13px;color:#8B9086")}>
                {"재검토 Case가 연결된 저장소가 없습니다."}
              </div>
            )}
            {values.repoRows.map((r, _index0) => (
              <Fragment key={_index0}>
                <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:16px 20px")}>
                  <div style={toReactStyle("display:flex;align-items:center;gap:16px")}>
                    <div style={toReactStyle("flex:1;min-width:0;cursor:pointer")} onClick={r.onOpen}>
                      <div style={toReactStyle("font-size:14.5px;font-weight:600;margin-bottom:4px")}>
                        {`${r.display_name}`}
                      </div>
                      <div style={toReactStyle("font-size:12px;color:#8B9086")}>
                        {`${r.full_name}`}
                      </div>
                    </div>
                    <select disabled title="UI Preview · 후속 구현" style={toReactStyle("font-size:12.5px;font-weight:600;font-family:inherit;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:7px;padding:6px 8px;cursor:not-allowed;color:#8B9086")} value={r.importance} onChange={r.onImportanceChange}>
                      {values.importanceLevelOptions.map((opt, _index1) => (
                        <Fragment key={_index1}>
                          <option value={opt.value}>
                            {`중요도: ${opt.label}`}
                          </option>
                        </Fragment>
                      ))}
                    </select>
                    <div style={toReactStyle("text-align:right;flex:none;cursor:pointer")} onClick={r.onOpen}>
                      <div style={toReactStyle("font-size:12px;color:#8B9086")}>
                        {`열린 항목 ${r.openCount}건 · critical ${r.criticalOpenCount}건`}
                      </div>
                    </div>
                    <div style={toReactStyle("color:#D2D5CD;font-size:18px;cursor:pointer")} onClick={r.onOpen}>
                      {"›"}
                    </div>
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #F0F1EE")}>
                    <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;letter-spacing:.02em;margin-right:4px")}>
                      {"적용된 자동조치 정책"}
                    </span>
                    <span style={toReactStyle(`font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:${r.policySummary.bg};color:${r.policySummary.color};white-space:nowrap`)}>
                      {`${r.policySummary.label}`}
                    </span>
                  </div>
                </div>
              </Fragment>
            ))}
          </div>
          <div style={toReactStyle("font-size:12px;color:#8B9086;margin-top:16px")}>
            {values.isDemo
              ? "UI Preview · 저장소 중요도와 자동조치 정책은 이 화면에서 변경되지 않습니다."
              : "저장소 목록과 건수는 DB 기준입니다. 자동조치 정책 변경은 아직 연동되지 않았습니다."}
          </div>
        </div>
      </>
    )}
    </>
  );
}
