import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Dashboard({ values }) {
  return (
    <>
    {values.isDashboardView && (
      <>
        <div className="watchback-page" style={toReactStyle("max-width:960px;margin:0 auto;padding:40px 32px 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:22px;font-weight:700;margin:0 0 6px;letter-spacing:-0.01em")}>
              {"오늘의 재검토 현황"}
            </h1>
            <p style={toReactStyle("font-size:14px;color:#5B6058;margin:0 0 4px;line-height:1.6")}>
              {`${values.dashboardDescription}`}
            </p>
            <span style={toReactStyle("font-size:12px;color:#8B9086")}>
              {`${values.weekRangeLabel}`}
            </span>
          </div>
          <div style={toReactStyle("display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:28px;position:relative")}>
            {values.kpiCards.map((kpi, _index0) => (
              <Fragment key={_index0}>
                <div style={toReactStyle(`background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:16px 18px;cursor:${kpi.cursorStyle}`)} onClick={kpi.onClick}>
                  <div style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;letter-spacing:.02em;margin-bottom:8px")}>
                    {`${kpi.label}`}
                  </div>
                  <div style={toReactStyle("font-size:24px;font-weight:700;letter-spacing:-0.01em;margin-bottom:4px")}>
                    {`${kpi.value}`}
                  </div>
                  <div style={toReactStyle("font-size:11.5px;color:#8B9086;line-height:1.4;margin-bottom:6px")}>
                    {`${kpi.hint}`}
                  </div>
                  <div style={toReactStyle("font-size:11.5px;color:#2F8F5B;font-weight:600")}>
                    {`${kpi.trend}`}
                  </div>
                </div>
              </Fragment>
            ))}
            {values.showSuppressedPopover && (
              <>
                <div style={toReactStyle("position:absolute;top:calc(100% + 8px);right:0;width:340px;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.08);padding:16px 18px;z-index:10")}>
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;margin-bottom:10px")}>
                    <span style={toReactStyle("font-size:13px;font-weight:700")}>
                      {"억제된 시스템성 변동 3건 (미구현)"}
                    </span>
                    <span style={toReactStyle("cursor:pointer;color:#8B9086;font-size:13px")} onClick={values.closeSuppressedPopover}>
                      {"✕"}
                    </span>
                  </div>
                  {values.suppressedCases.map((sc, _index0) => (
                    <Fragment key={_index0}>
                      <div style={toReactStyle("padding:8px 0;border-top:1px solid #F0F1EE")}>
                        <div style={toReactStyle("font-size:12.5px;font-weight:600;margin-bottom:2px")}>
                          {`${sc.repoName}`}
                        </div>
                        <div style={toReactStyle("font-size:12px;color:#8B9086;line-height:1.5")}>
                          {`${sc.reason}`}
                        </div>
                      </div>
                    </Fragment>
                  ))}
                </div>
              </>
            )}
          </div>
          <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;margin-bottom:14px")}>
            <div style={toReactStyle("font-size:15px;font-weight:700")}>
              {"지금 봐야 할 항목"}
            </div>
            <span style={toReactStyle("font-size:12.5px;color:#2F8F5B;cursor:pointer;font-weight:600")} onClick={values.goToAllList}>
              {"전체 재검토 목록 보기 →"}
            </span>
          </div>
          <div style={toReactStyle("display:flex;flex-direction:column;gap:10px;margin-bottom:28px")}>
            {!values.hasDashboardCases && (
              <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:28px 20px;text-align:center;font-size:13px;color:#8B9086")}>
                {"현재 재검토 항목이 없습니다."}
              </div>
            )}
            {values.topCases.map((c, _index0) => (
              <Fragment key={_index0}>
                <div style={toReactStyle("display:flex;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;overflow:hidden;cursor:pointer")} onClick={c.onOpen}>
                  <div style={toReactStyle(`width:4px;flex:none;background:${c.priorityDot}`)}></div>
                  <div style={toReactStyle("flex:1;min-width:0;padding:14px 0 14px 18px;display:flex;align-items:center;gap:14px")}>
                    <span style={toReactStyle(`${c.priorityBadgeStyle}`)}>
                      {`${c.priorityLabel}`}
                    </span>
                    <span style={toReactStyle("font-size:13.5px;font-weight:600;flex:none")}>
                      {`${c.repoName}`}
                    </span>
                    <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#8B9086;flex:none")}>
                      {`${c.alert.package_name}`}
                    </span>
                    <span style={toReactStyle("font-size:13px;color:#1B1E1A;line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>
                      {`${c.reviewReasonLabel}`}
                    </span>
                    <div style={toReactStyle("display:flex;align-items:center;gap:6px;flex:none;margin-left:auto")}>
                      {c.evidenceTags.map((tag, _index1) => (
                        <span key={_index1} style={toReactStyle(`${tag.style}`)}>
                          {`${tag.label}`}
                        </span>
                      ))}
                      {c.urgencyLabel && (
                        <>
                          <span style={toReactStyle("font-size:11px;font-weight:600;color:#9A5A16;background:#FCEFE1;border-radius:5px;padding:2px 7px")}>
                            {`${c.urgencyLabel}`}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;padding:0 18px;color:#D2D5CD;font-size:18px")}>
                    {"›"}
                  </div>
                </div>
              </Fragment>
            ))}
          </div>
          <div style={toReactStyle("font-size:15px;font-weight:700;margin-bottom:14px")}>
            {`${values.flowTitle}`}
          </div>
          <div style={toReactStyle("display:grid;grid-template-columns:repeat(3,1fr);gap:12px")}>
            {values.flowStages.map((stage, _index0) => (
              <Fragment key={_index0}>
                <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:16px 18px;cursor:pointer")} onClick={stage.onClick}>
                  <div style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;letter-spacing:.02em;margin-bottom:8px")}>
                    {`${stage.label}`}
                  </div>
                  <div style={toReactStyle("font-size:24px;font-weight:700;letter-spacing:-0.01em")}>
                    {`${stage.count}`}
                  </div>
                </div>
              </Fragment>
            ))}
          </div>
        </div>
      </>
    )}
    </>
  );
}
