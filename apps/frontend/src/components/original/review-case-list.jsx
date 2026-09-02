import { toReactStyle } from './style';

const FILTER_BUTTON_STYLE = 'font-family:inherit;font-size:13px;line-height:19px;font-weight:600;border-radius:7px;padding:7px 12px;cursor:pointer';

export function ReviewCaseList({ values }) {
  if (!values.isListView) return null;
  return (
    <div className="watchback-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px")}>
      <h1 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0 0 24px")}>재검토 목록</h1>
      <div style={toReactStyle("display:flex;flex-direction:column;gap:26px;margin-bottom:34px")}>
        <div style={toReactStyle("display:flex;gap:10px")}>{values.statusOptions.map((opt) => <button key={opt.value} type="button" style={toReactStyle(`${opt.pillStyle};${FILTER_BUTTON_STYLE}`)} onClick={opt.onClick}>{opt.label}</button>)}</div>
        <div className="watchback-sort-options" style={toReactStyle("display:flex;gap:12px;flex-wrap:wrap")}>
          {values.sortOptions.map(option => <button key={option.value} type="button" aria-pressed={option.active} onClick={option.onClick} style={toReactStyle(`${FILTER_BUTTON_STYLE};color:${option.active ? '#1B1E1A' : '#8B9086'};background:${option.active ? '#EEF0EE' : '#FFFFFF'};border:1px solid ${option.active ? '#D2D5CD' : '#E4E6E1'}`)}>{option.label}</button>)}
        </div>
        <div className="watchback-list-filter-grid" style={toReactStyle("display:grid;grid-template-columns:minmax(380px,0.9fr) minmax(560px,1.4fr);gap:28px 42px;align-items:start")}>
          <FilterGroup label="우선순위" options={values.priorityChipOptions} />
          <FilterGroup label="변화 유형" options={values.changeTypeChipOptions} />
          <div>
            <div style={toReactStyle("font-size:14px;line-height:21px;font-weight:700;color:#737A71;margin-bottom:12px")}>저장소 중요도</div>
            <div style={toReactStyle("display:flex;align-items:center;gap:10px;flex-wrap:wrap")}>{values.importanceChipOptions.map((opt) => <button key={opt.value} type="button" style={toReactStyle(`${opt.pillStyle};font:600 13px/19px inherit;border-radius:7px;padding:7px 12px`)} onClick={opt.onClick}>{opt.label}</button>)}</div>
          </div>
        </div>
      </div>
      {values.activeRepoFilterLabel && <div style={toReactStyle("margin-bottom:12px")}><button type="button" onClick={values.clearRepoFilter} style={toReactStyle("font:600 11px/18px inherit;color:#168456;background:#EAFBF3;border:1px solid #BFEBD7;border-radius:12px;padding:3px 10px")}>저장소: {values.activeRepoFilterLabel} ×</button></div>}
      <div style={toReactStyle("font-size:13px;color:#737A71;margin-bottom:14px")}>{values.resultCountLabel}</div>
      {values.isEmpty && <div style={toReactStyle("background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;padding:64px 24px;text-align:center;color:#8B9086")}>현재 조건에 맞는 재검토 후보가 없습니다.</div>}
      {values.hasResults && <div style={toReactStyle("display:flex;flex-direction:column;gap:9px")}>{values.filteredCases.map((c) => c.isVulnerabilityGroup ? <VulnerabilityGroupRow key={c.id} item={c} /> : <button key={c.id} type="button" role="button" onClick={c.onOpen} className="watchback-list-row" style={toReactStyle(`display:grid;grid-template-columns:240px 150px 135px minmax(210px,1fr) 120px 12px;align-items:center;gap:16px;min-height:86px;text-align:left;font-family:inherit;color:#1B1E1A;background:linear-gradient(90deg,${c.priorityDot} 0 3px,#FFFFFF 3px);border:1px solid #E3E7E1;border-radius:9px;padding:12px 14px 12px 20px;cursor:pointer`)}>
        <span><strong style={toReactStyle("display:block;font-size:13px;margin-bottom:5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>{c.repoName}</strong><b style={toReactStyle(`font-size:12px;color:${c.priorityDot}`)}>{c.priorityLabel}</b></span>
        <span><strong style={toReactStyle("display:block;font:500 13px/19px Inter,Arial,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>{c.alert.package_name}</strong><small style={toReactStyle("font-size:11px;color:#8B9086")}>{c.alert.ecosystem}</small></span>
        <span><span style={toReactStyle("display:block;font:500 12px/19px Inter,Arial,sans-serif")}>{c.advisory.cve_id || c.advisory.ghsa_id}</span>{c.advisory.cvss_score != null && <small style={toReactStyle("font-size:11px;font-weight:700;color:#A66A20")}>CVSS {c.advisory.cvss_score}</small>}</span>
        <span style={toReactStyle("font-size:12px;line-height:19px;color:#515250;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;word-break:keep-all")}>{c.reviewReasonLabel}</span>
        <span style={toReactStyle("text-align:right")}><small style={toReactStyle("display:block;font-size:9px;color:#8B9086;margin-bottom:4px")}>생성 {c.openedLabel}</small>{c.hasSourceAnnotation ? <b style={toReactStyle("font-size:9px;color:#168456")}>소스 변동 주의</b> : c.evidenceTags.slice(0, 1).map((tag) => <b key={tag.label} style={toReactStyle(`${tag.style};font-size:9px;background:transparent;padding:0`)}>{tag.label}</b>)}</span>
        <span style={toReactStyle("color:#CBD5E1;font-size:18px")}>›</span>
      </button>)}</div>}
    </div>
  );
}

function VulnerabilityGroupRow({ item }) {
  return <button type="button" role="button" onClick={item.onOpen} className="watchback-list-row" style={toReactStyle(`display:grid;grid-template-columns:105px 160px minmax(320px,1fr) 220px 140px 12px;align-items:center;gap:18px;min-height:86px;text-align:left;font-family:inherit;color:#1B1E1A;background:linear-gradient(90deg,${item.priorityDot} 0 3px,#FFFFFF 3px);border:1px solid #E3E7E1;border-radius:9px;padding:12px 14px 12px 20px;cursor:pointer`)}>
    <b style={toReactStyle(`font-size:12px;color:${item.priorityDot}`)}>{item.priorityLabel}</b>
    <span>
      <strong style={toReactStyle("display:block;font:600 13px/20px Inter,Arial,sans-serif")}>{item.advisory.cve_id}</strong>
    </span>
    <span style={toReactStyle("min-width:0") }>
      <strong style={toReactStyle("display:block;font-size:13px;line-height:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px")}>{item.advisory.summary}</strong>
      <small style={toReactStyle("font:11px/18px Inter,Arial,sans-serif;color:#8B9086")}>{item.packageSummaryLabel}</small>
    </span>
    <span style={toReactStyle("font-size:12px;line-height:19px;color:#515250")}>{item.affectedRepositoryLabel} · Open Alert {item.openAlertCount}건</span>
    <span style={toReactStyle("text-align:right") }>
      {item.hasSourceAnnotation
        ? <b style={toReactStyle("font-size:9px;font-weight:600;color:#9A5A16;background:#FCEFE1;border-radius:12px;padding:3px 8px;white-space:nowrap")}>소스 변동 주의</b>
        : item.evidenceTags.slice(0, 1).map((tag) => <b key={tag.label} style={toReactStyle(`${tag.style};font-size:9px;border-radius:12px;padding:3px 8px`)}>{tag.label === 'KEV' ? 'NEW KEV' : tag.label}</b>)}
    </span>
    <span style={toReactStyle("color:#CBD5E1;font-size:18px")}>›</span>
  </button>;
}

function FilterGroup({ label, options }) {
  return <div><div style={toReactStyle("font-size:14px;line-height:21px;font-weight:700;color:#737A71;margin-bottom:12px")}>{label}</div><div style={toReactStyle("display:flex;align-items:center;gap:10px;flex-wrap:wrap")}>{options.map((opt) => <button key={opt.value} type="button" style={toReactStyle(`${opt.pillStyle};font:600 13px/19px inherit;border-radius:7px;padding:7px 12px`)} onClick={opt.onClick}>{opt.label}</button>)}</div></div>;
}
