import { Fragment } from 'react';
import { toReactStyle } from './style';

export function ReviewCaseList({ values }) {
  return (
    <>
    {values.isListView && (
      <>
        <div className="watchback-page" style={toReactStyle("max-width:960px;margin:0 auto;padding:40px 32px 96px")}>
          <div style={toReactStyle("margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:22px;font-weight:700;margin:0 0 6px;letter-spacing:-0.01em")}>
              {"재검토 목록"}
            </h1>
          </div>
          <div style={toReactStyle("display:flex;flex-direction:column;gap:14px;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:16px 18px;margin-bottom:20px;box-shadow:0 1px 2px rgba(0,0,0,.03)")}>
            <div style={toReactStyle("display:flex;align-items:center;gap:14px;flex-wrap:wrap")}>
              <div style={toReactStyle("display:flex;background:#EEF0EE;border-radius:8px;padding:3px;gap:2px")}>
                {values.statusOptions.map((opt, _index0) => (
                  <Fragment key={_index0}>
                    <button type="button" style={toReactStyle(`${opt.pillStyle};border:none;font-family:inherit`)} onClick={opt.onClick}>
                      {`${opt.label}`}
                    </button>
                  </Fragment>
                ))}
              </div>
              <div style={toReactStyle("position:relative;margin-left:auto")}>
                <select style={toReactStyle("appearance:none;font-size:12.5px;font-weight:600;font-family:inherit;color:#1B1E1A;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:20px;padding:8px 30px 8px 14px;cursor:pointer")} value={values.filters.sort} onChange={values.onSortChange}>
                  <option value="priority">
                    {"우선순위 순"}
                  </option>
                  <option value="updated_at">
                    {"최근 업데이트 순"}
                  </option>
                  <option value="opened_at">
                    {"생성일 순"}
                  </option>
                </select>
                <span style={toReactStyle("position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:9px;color:#8B9086;pointer-events:none")}>
                  {"▾"}
                </span>
              </div>
            </div>
            <div style={toReactStyle("display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-top:12px;border-top:1px solid #F0F1EE")}>
              <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;letter-spacing:.02em;margin-right:2px")}>
                {"우선순위"}
              </span>
              {values.priorityChipOptions.map((opt, _index0) => (
                <Fragment key={_index0}>
                  <button type="button" style={toReactStyle(`${opt.pillStyle};font-family:inherit`)} onClick={opt.onClick}>
                    <span style={toReactStyle(`width:7px;height:7px;border-radius:50%;background:${opt.dot};display:inline-block`)}></span>
                    {opt.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <div style={toReactStyle("display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-top:12px;border-top:1px solid #F0F1EE")}>
              <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;letter-spacing:.02em;margin-right:2px")}>
                {"변화 유형"}
              </span>
              {values.changeTypeChipOptions.map((opt, _index0) => (
                <Fragment key={_index0}>
                  <button type="button" style={toReactStyle(`${opt.pillStyle};font-family:inherit`)} onClick={opt.onClick}>
                    {`${opt.label}`}
                  </button>
                </Fragment>
              ))}
            </div>
            <div style={toReactStyle("display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-top:12px;border-top:1px solid #F0F1EE")}>
              <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;letter-spacing:.02em;margin-right:2px")}>
                {"저장소 중요도"}
              </span>
              {values.importanceChipOptions.map((opt, _index0) => (
                <Fragment key={_index0}>
                  <button type="button" style={toReactStyle(`${opt.pillStyle};font-family:inherit`)} onClick={opt.onClick}>
                    <span style={toReactStyle(`width:7px;height:7px;border-radius:50%;background:${opt.dot};display:inline-block`)}></span>
                    {opt.label}
                  </button>
                </Fragment>
              ))}
              <button type="button" style={toReactStyle(`${values.staleToggle.pillStyle};font-family:inherit`)} onClick={values.staleToggle.onClick}>
                {"3일 이상 미처리만"}
              </button>
            </div>
          </div>
          {values.activeRepoFilterLabel && (
            <>
              <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-bottom:14px")}>
                <span style={toReactStyle("font-size:12px;font-weight:600;color:#2F8F5B;background:#E7F3EC;border-radius:20px;padding:4px 10px;display:flex;align-items:center;gap:6px")}>
                  {`저장소: ${values.activeRepoFilterLabel} `}
                  <span style={toReactStyle("cursor:pointer")} onClick={values.clearRepoFilter}>
                    {"✕"}
                  </span>
                </span>
              </div>
            </>
          )}
          <div style={toReactStyle("font-size:12px;color:#8B9086;margin-bottom:14px")}>
            {`${values.resultCountLabel}`}
          </div>
          {values.isEmpty && (
            <>
              <div style={toReactStyle("display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 24px;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;text-align:center")}>
                <div style={toReactStyle("width:56px;height:56px;border-radius:12px;background:repeating-linear-gradient(135deg,#EEF0EE,#EEF0EE 4px,#F5F6F3 4px,#F5F6F3 8px);border:1px solid #D2D5CD;margin-bottom:18px")}></div>
                <div style={toReactStyle("font-size:15px;font-weight:600;margin-bottom:6px")}>
                  {"현재 조건에 맞는 재검토 후보가 없습니다"}
                </div>
                <div style={toReactStyle("font-size:13px;color:#5B6058;max-width:360px;line-height:1.6")}>
                  {"필터를 조정하거나, 다음 Gold 위험 후보 배치가 도착하면 새로운 재검토 대상이 나타납니다."}
                </div>
              </div>
            </>
          )}
          {values.hasResults && (
            <>
              <div style={toReactStyle("display:flex;flex-direction:column;gap:12px")}>
                {values.filteredCases.map((c, _index0) => (
                  <Fragment key={_index0}>
                    <div role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') c.onOpen(); }} style={toReactStyle("display:flex;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;overflow:hidden;cursor:pointer;transition:border-color .15s")} onClick={c.onOpen}>
                      <div style={toReactStyle(`width:4px;flex:none;background:${c.priorityDot}`)}></div>
                      <div style={toReactStyle("flex:1;min-width:0;padding:18px 22px")}>
                        <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px")}>
                          <div style={toReactStyle("display:flex;align-items:center;gap:8px;min-width:0")}>
                            <span style={toReactStyle("font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis")}>
                              {`${c.repoName}`}
                            </span>
                          </div>
                          <div style={toReactStyle("display:flex;align-items:center;gap:6px;flex:none")}>
                            {c.isResolved && (
                              <>
                                <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;padding:3px 9px;border-radius:20px;background:#EEF0EE")}>
                                  {"해결됨"}
                                </span>
                              </>
                            )}
                            {c.isReopened && (
                              <>
                                <span style={toReactStyle("font-size:11px;font-weight:600;color:#9A5A16;padding:3px 9px;border-radius:20px;background:#FCEFE1")}>
                                  {`재오픈 ${c.reopened_count}회`}
                                </span>
                              </>
                            )}
                            <span style={toReactStyle(`${c.priorityBadgeStyle}`)}>
                              {`${c.priorityLabel}`}
                            </span>
                          </div>
                        </div>
                        <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap")}>
                          <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#1B1E1A;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:6px;padding:3px 8px")}>
                            {`${c.alert.package_name}`}
                          </span>
                          <span style={toReactStyle("font-size:11px;color:#8B9086")}>
                            {`${c.alert.ecosystem}`}
                          </span>
                          <span style={toReactStyle("width:3px;height:3px;border-radius:50%;background:#D2D5CD")}></span>
                          <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#5B6058")}>
                            {`${c.advisory.cve_id || c.advisory.ghsa_id}`}
                          </span>
                          <span style={toReactStyle("font-size:11px;color:#8B9086")}>
                            {`CVSS ${c.advisory.cvss_score}`}
                          </span>
                        </div>
                        <div style={toReactStyle("font-size:14px;line-height:1.6;color:#1B1E1A;margin-bottom:6px")}>
                          {`${c.review_reason}`}
                        </div>
                        <div style={toReactStyle("display:flex;align-items:center;gap:6px")}>
                          {c.evidenceTags.map((tag, _index1) => (
                            <span key={_index1} style={toReactStyle(`${tag.style}`)}>
                              {`${tag.label}`}
                            </span>
                          ))}
                        </div>
                        <div style={toReactStyle("display:flex;align-items:center;gap:14px;margin-top:12px;padding-top:12px;border-top:1px solid #F0F1EE;font-size:11px;color:#8B9086")}>
                          <span>
                            {`생성 ${c.openedLabel}`}
                          </span>
                          <span>
                            {`업데이트 ${c.updatedLabel}`}
                          </span>
                        </div>
                      </div>
                      <div style={toReactStyle("display:flex;align-items:center;padding:0 18px;color:#D2D5CD;font-size:18px")}>
                        {"›"}
                      </div>
                    </div>
                  </Fragment>
                ))}
              </div>
            </>
          )}
        </div>
      </>
    )}
    </>
  );
}
