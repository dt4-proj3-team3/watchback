import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Repositories({ values }) {
  return (
    <>
    {values.isReposView && (
      <>
        <div className="watchback-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0 0 6px;letter-spacing:-0.01em")}>
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
                <div style={toReactStyle("position:relative;height:122px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;overflow:hidden")}>
                  <button type="button" onClick={r.onOpen} style={toReactStyle("position:absolute;inset:0;background:transparent;border:0;cursor:pointer")} aria-label={`${r.display_name} 재검토 목록 열기`} />
                  <strong style={toReactStyle("position:absolute;left:20px;top:16px;width:600px;font-size:14px;line-height:20px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;pointer-events:none")}>
                    {r.display_name}
                  </strong>
                  <span style={toReactStyle("position:absolute;left:20px;top:41px;width:600px;font-size:12px;line-height:17px;color:#687066;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;pointer-events:none")}>
                    {r.full_name}
                  </span>
                  <select disabled title="UI Preview · 후속 구현" style={toReactStyle("position:absolute;right:197px;top:19px;width:128px;height:33px;font-size:12px;line-height:17px;font-weight:600;font-family:inherit;color:#1B1E1A;background:#FFFFFF;border:1px solid #DDE3DA;border-radius:7px;padding:0 10px;cursor:not-allowed")} value={r.importance} onChange={r.onImportanceChange}>
                    {values.importanceLevelOptions.map((opt) => <option key={opt.value} value={opt.value}>{`중요도: ${opt.label}`}</option>)}
                  </select>
                  <span style={toReactStyle("position:absolute;right:25px;top:26px;width:155px;text-align:right;font-size:12px;line-height:17px;color:#687066;pointer-events:none")}>
                    {`열린 항목 ${r.openCount}건 · Critical ${r.p0OpenCount}건`}
                  </span>
                  <span style={toReactStyle("position:absolute;right:8px;top:23px;width:16px;font-size:22px;line-height:22px;color:#C7CDC4;pointer-events:none")}>›</span>
                  <span style={toReactStyle("position:absolute;left:20px;top:87px;width:130px;font-size:11px;line-height:16px;color:#7C8379;pointer-events:none")}>
                    적용된 자동조치 정책
                  </span>
                  <strong style={toReactStyle(`position:absolute;left:131px;top:84px;max-width:440px;font-size:13px;line-height:19px;font-weight:700;color:${r.policySummary.color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none`)}>
                    {r.policySummary.label}
                  </strong>
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
