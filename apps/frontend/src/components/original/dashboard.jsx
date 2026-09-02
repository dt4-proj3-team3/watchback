import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Dashboard({ values }) {
  if (!values.isDashboardView) return null;
  const isVulnerabilityQueue = values.topCases.some((item) => item.isVulnerabilityGroup);

  return (
    <div className="watchback-page watchback-dashboard-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px")}>
      <h1 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0 0 24px")}>Review Summary</h1>
      <div className="watchback-summary-grid" style={toReactStyle("display:grid;grid-template-columns:364px repeat(3,1fr);gap:14px;margin-bottom:42px")}>
        <div style={toReactStyle("height:110px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:9px;padding:23px")}>
          <div style={toReactStyle("display:flex;gap:2px;height:11px;border-radius:6px;overflow:hidden;margin-bottom:16px")}>
            {values.severitySummary.map((item) => <span key={item.value} style={toReactStyle(`width:${item.count ? `calc(${item.ratio}% - 1.5px)` : '0px'};min-width:0;background:${item.color}`)} />)}
          </div>
          <div style={toReactStyle("display:flex;align-items:center;gap:6px")}>
            <strong style={toReactStyle("font:500 30px/38px Inter,Arial,sans-serif;color:#0F172A")}>{values.issueCount}</strong>
            <span style={toReactStyle("font:400 18px/24px Inter,Arial,sans-serif;color:#0F172A;margin-right:auto")}>Issues</span>
            {values.severitySummary.map((item) => <Fragment key={item.value}><span style={toReactStyle(`width:8px;height:8px;border-radius:1px;background:${item.color}`)} /><span style={toReactStyle("font:500 12px/18px Inter,Arial,sans-serif;color:#0F172A")}>{item.count}</span></Fragment>)}
          </div>
        </div>
        {values.flowStages.map((stage) => <button key={stage.label} type="button" onClick={stage.onClick} style={toReactStyle("height:110px;text-align:left;font-family:inherit;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:19px 21px;cursor:pointer")}><span style={toReactStyle("display:block;font-size:12px;line-height:17px;font-weight:500;color:#7C8379;margin-bottom:10px")}>{stage.label}</span><strong style={toReactStyle("display:block;font:500 30px/38px Inter,Arial,sans-serif;color:#0F172A")}>{stage.count}</strong></button>)}
      </div>
      <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;margin-bottom:23px")}>
        <h2 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0")}>Priority Queue</h2>
        <button type="button" onClick={values.goToAllList} style={toReactStyle("font-size:13px;line-height:19px;font-weight:700;color:#6B7280;background:none;border:0;padding:0;cursor:pointer")}>All List →</button>
      </div>
      {isVulnerabilityQueue
        ? <div className="watchback-queue-head" style={toReactStyle("display:grid;grid-template-columns:105px 180px 190px minmax(240px,1fr) 140px;gap:23px;padding:0 22px 12px;font:700 13px/19px Inter,Arial,sans-serif;color:#6B7280;border-bottom:1px solid #E3E7E1")}><span>Priority</span><span>Vulnerability</span><span>Package</span><span>Impact</span><span>Change</span></div>
        : <div className="watchback-queue-head" style={toReactStyle("display:grid;grid-template-columns:105px 189px 194px minmax(233px,1fr) 131px;gap:23px;padding:0 22px 12px;font:700 13px/19px Inter,Arial,sans-serif;color:#6B7280;border-bottom:1px solid #E3E7E1")}><span>Priority</span><span>Name</span><span>Repository</span><span>Reason</span><span>Status</span></div>}
      <div data-testid="priority-queue" style={toReactStyle("display:flex;flex-direction:column;gap:12px;margin-top:16px")}>
        {!values.hasDashboardCases && <div style={toReactStyle("background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:28px;text-align:center;font-size:13px;color:#8B9086")}>현재 재검토 항목이 없습니다.</div>}
        {values.topCases.slice(0, 5).map((c) => c.isVulnerabilityGroup ? <button key={c.id} type="button" onClick={c.onOpen} className="watchback-queue-row" style={toReactStyle(`display:grid;grid-template-columns:105px 180px 190px minmax(240px,1fr) 140px 16px;align-items:center;gap:23px;min-height:68px;text-align:left;font-family:inherit;color:#1B1E1A;background:linear-gradient(90deg,${c.priorityDot} 0 3px,#FFFFFF 3px);border:1px solid #E3E7E1;border-radius:9px;padding:7px 14px 7px 22px;box-shadow:0 1px 2px rgba(27,30,26,.04);cursor:pointer`)}>
          <strong style={toReactStyle(`font-size:13px;color:${c.priorityDot}`)}>{c.priorityLabel}</strong>
          <span style={toReactStyle("font:600 13px/19px Inter,Arial,sans-serif;white-space:nowrap")}>{c.advisory.cve_id}</span>
          <span style={toReactStyle("font:500 13px/19px Inter,Arial,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>{c.packageSummaryLabel}</span>
          <span style={toReactStyle("font-size:13px;line-height:19px;color:#515250")}>{c.affectedRepositoryLabel} · Open Alert {c.openAlertCount}건</span>
          <span style={toReactStyle("display:flex;justify-content:flex-end;gap:4px")}>{c.evidenceTags.slice(0, 1).map((tag) => <span key={tag.label} style={toReactStyle(`${tag.style};font-size:9px;border:1px solid ${tag.label === 'KEV' ? '#FFCABD' : '#BFEBD7'};border-radius:12px;padding:3px 8px`)}>{tag.label === 'KEV' ? 'NEW KEV' : tag.label}</span>)}</span>
          <span style={toReactStyle("color:#CBD5E1;font-size:18px")}>›</span>
        </button> : <button key={c.id} type="button" onClick={c.onOpen} className="watchback-queue-row" style={toReactStyle(`display:grid;grid-template-columns:105px 189px 194px minmax(233px,1fr) 131px 16px;align-items:center;gap:23px;min-height:68px;text-align:left;font-family:inherit;color:#1B1E1A;background:linear-gradient(90deg,${c.priorityDot} 0 3px,#FFFFFF 3px);border:1px solid #E3E7E1;border-radius:9px;padding:7px 14px 7px 22px;box-shadow:0 1px 2px rgba(27,30,26,.04);cursor:pointer`)}>
          <strong style={toReactStyle(`font-size:13px;color:${c.priorityDot}`)}>{c.priorityLabel}</strong>
          <span style={toReactStyle("font:500 13px/19px Inter,Arial,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>{c.alert.package_name}</span>
          <span style={toReactStyle("font:500 13px/19px Inter,Arial,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>{c.repoName.split('/').at(-1)}</span>
          <span style={toReactStyle("font-size:13px;line-height:19px;color:#515250;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;word-break:keep-all")}>{c.reviewReasonLabel}</span>
          <span style={toReactStyle("display:flex;justify-content:flex-end;gap:4px")}>{c.evidenceTags.slice(0, 1).map((tag) => <span key={tag.label} style={toReactStyle(`${tag.style};font-size:9px;border:1px solid ${tag.label === 'KEV' ? '#FFCABD' : '#BFEBD7'};border-radius:12px;padding:3px 8px`)}>{tag.label === 'KEV' ? 'NEW KEV' : tag.label}</span>)}</span>
          <span style={toReactStyle("color:#CBD5E1;font-size:18px")}>›</span>
        </button>)}
      </div>
    </div>
  );
}
