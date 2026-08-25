import { Fragment } from 'react';
import { toReactStyle } from './style';

export function ReviewCaseDetail({ values }) {
  return (
    <>
    {values.isDetailView && (
      <>
        <div style={toReactStyle("max-width:960px;margin:0 auto;padding:28px 32px 96px")}>
          <div style={toReactStyle("display:flex;align-items:center;gap:6px;font-size:13px;color:#5B6058;cursor:pointer;margin-bottom:20px;width:fit-content")} onClick={values.backToList}>
            <span>
              {"←"}
            </span>
            <span>
              {"목록으로"}
            </span>
          </div>
          <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:24px 26px;margin-bottom:16px")}>
            <div style={toReactStyle("display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap")}>
              <div>
                <div style={toReactStyle("display:flex;align-items:center;gap:9px;margin-bottom:8px;flex-wrap:wrap")}>
                  <span style={toReactStyle("font-size:19px;font-weight:700;letter-spacing:-0.01em")}>
                    {`${values.selected.repoName}`}
                  </span>
                  {values.selected.isResolved && (
                    <>
                      <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;padding:3px 9px;border-radius:20px;background:#EEF0EE")}>
                        {"해결됨"}
                      </span>
                    </>
                  )}
                </div>
                <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap")}>
                  <span style={toReactStyle(`${values.selected.severityBadgeStyle}`)}>
                    {`심각도 ${values.selected.severityLabel}`}
                  </span>
                  <span style={toReactStyle("color:#D2D5CD;font-size:13px")}>
                    {"×"}
                  </span>
                  <span style={toReactStyle("font-size:11px;font-weight:500;color:#8B9086;padding:3px 9px;border-radius:20px;border:1px solid #E4E6E1;white-space:nowrap;flex:none")}>
                    {`중요도 ${values.selected.importanceLabel}`}
                  </span>
                  <span style={toReactStyle("color:#D2D5CD;font-size:13px")}>
                    {"="}
                  </span>
                  <span style={toReactStyle(`${values.selected.priorityBadgeStyle}`)}>
                    {`우선순위 ${values.selected.priorityLabel}`}
                  </span>
                </div>
                <div style={toReactStyle("max-width:560px;margin-bottom:12px")}>
                  {values.selected.reviewReasonDateLabel && (
                    <div style={toReactStyle("font-size:11px;color:#8B9086;margin-bottom:3px")}>
                      {`변화 감지 ${values.selected.reviewReasonDateLabel}`}
                    </div>
                  )}
                  <div style={toReactStyle("font-size:14px;color:#1B1E1A;line-height:1.6")}>
                    {`${values.selected.reviewReasonLabel}`}
                  </div>
                </div>
                <div style={toReactStyle("display:flex;align-items:center;gap:16px;padding-top:12px;border-top:1px solid #F0F1EE")}>
                  <div>
                    <div style={toReactStyle("font-size:10.5px;color:#8B9086;margin-bottom:3px")}>
                      {"자동조치"}
                    </div>
                    <span style={toReactStyle(`font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:${values.selected.automationStatusBg};color:${values.selected.automationStatusColor}`)}>
                      {`${values.selected.automationStatusLabel}`}
                    </span>
                  </div>
                  <div>
                    <div style={toReactStyle("font-size:10.5px;color:#8B9086;margin-bottom:3px")}>
                      {"CVSS"}
                    </div>
                    <span style={toReactStyle("font-size:13px;font-weight:700")}>
                      {`${values.selected.advisory.cvss_score}`}
                    </span>
                  </div>
                  <div>
                    <div style={toReactStyle("font-size:10.5px;color:#8B9086;margin-bottom:3px")}>
                      {"패치 버전"}
                    </div>
                    <span style={toReactStyle(`font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:600;color:${values.selected.patchColor}`)}>
                      {`${values.selected.patchLabelShort}`}
                    </span>
                  </div>
                </div>
              </div>
              <div style={toReactStyle("display:flex;gap:8px;flex:none")}>
                {values.actionButtons.map((btn, _index0) => (
                  <Fragment key={_index0}>
                    <button style={toReactStyle(`${btn.style}`)} onClick={btn.onClick} title={btn.title}>
                      {`${btn.label}`}
                    </button>
                  </Fragment>
                ))}
              </div>
            </div>
          </div>
          {values.showPrUnavailableNotice && (
            <div style={toReactStyle("background:#FCEFE1;border:1px solid #E9C99A;border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:12.5px;color:#9A5A16")}>
              {"PR 생성 API 연동 전입니다."}
            </div>
          )}
          <div style={toReactStyle("background:#FFFFFF;border-left:3px solid #8B9086;border-radius:8px;padding:14px 18px;margin-bottom:20px;font-size:12.5px;line-height:1.6;color:#5B6058")}>
            {"Watchback은 위험 변화 신호를 제공하며, 실제 악용 여부와 조치 필요성은 검토자가 판단합니다."}
          </div>
          <div style={toReactStyle("display:grid;grid-template-columns:1fr 300px;gap:20px;align-items:start")}>
            <div style={toReactStyle("display:flex;flex-direction:column;gap:20px;min-width:0")}>
              <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px 22px")}>
                <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-bottom:14px")}>
                  <div style={toReactStyle("font-size:14px;font-weight:700")}>
                    {"변화 근거"}
                  </div>
                  <span style={toReactStyle(`font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:${values.selected.systemicBg};color:${values.selected.systemicColor}`)}>
                    {`${values.selected.systemicLabel}`}
                  </span>
                </div>
                <div style={toReactStyle("display:flex;flex-direction:column;gap:10px")}>
                  {values.selected.evidence.map((ev, _index0) => (
                    <Fragment key={_index0}>
                      <div style={toReactStyle("padding:11px 14px;background:#F5F6F3;border-radius:8px")}>
                        <div style={toReactStyle("display:flex;align-items:center;gap:12px")}>
                          <span style={toReactStyle("font-size:12px;font-weight:600;color:#1B1E1A;width:120px;flex:none")}>
                            {`${ev.signalLabel}`}
                          </span>
                          <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#8B9086")}>
                            {`${ev.previousValueLabel}`}
                          </span>
                          <span style={toReactStyle("color:#D2D5CD")}>
                            {"→"}
                          </span>
                          <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#1B1E1A;font-weight:600")}>
                            {`${ev.currentValueLabel}`}
                          </span>
                          <span style={toReactStyle("font-size:11px;color:#8B9086;margin-left:auto")}>
                            {`${ev.observedLabel}`}
                          </span>
                        </div>
                        <div style={toReactStyle("font-size:12.5px;color:#5B6058;line-height:1.5;margin-top:6px")}>
                          {`${ev.reasonSummary}`}
                        </div>
                      </div>
                    </Fragment>
                  ))}
                </div>
              </div>
              <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px 22px")}>
                <div style={toReactStyle("font-size:14px;font-weight:700;margin-bottom:14px")}>
                  {"검토 활동"}
                </div>
                {values.showActivityForm && (
                  <>
                    <div style={toReactStyle("background:#F5F6F3;border:1px solid #E4E6E1;border-radius:10px;padding:14px 16px;margin-bottom:14px")}>
                      <div style={toReactStyle("font-size:12.5px;font-weight:600;margin-bottom:8px")}>
                        {`${values.activityFormTitle}`}
                      </div>
                      <textarea style={toReactStyle("width:100%;box-sizing:border-box;font-family:inherit;font-size:13px;line-height:1.6;color:#1B1E1A;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:8px;padding:10px 12px;resize:vertical;min-height:56px")} placeholder="검토 근거나 조치 내용을 기록하세요" value={values.noteDraft} onChange={values.onNoteChange}></textarea>
                      <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-top:10px")}>
                        <select style={toReactStyle("font-size:12px;font-family:inherit;color:#1B1E1A;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:6px 8px")} value={values.linkType} onChange={values.onLinkTypeChange}>
                          <option value="">
                            {"외부 링크 없음"}
                          </option>
                          <option value="issue">
                            {"GitHub Issue 링크"}
                          </option>
                          <option value="pull_request">
                            {"GitHub PR 링크"}
                          </option>
                        </select>
                        <input style={toReactStyle("flex:1;font-size:12px;font-family:inherit;color:#1B1E1A;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:7px 10px")} placeholder="https://github.com/org/repo/issues/21" value={values.linkUrl} onChange={values.onLinkUrlChange} />
                        <button style={toReactStyle("font-size:12px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer;white-space:nowrap")} onClick={values.submitActivity}>
                          {"기록하기"}
                        </button>
                        <button style={toReactStyle("font-size:12px;font-family:inherit;color:#5B6058;background:none;border:none;cursor:pointer")} onClick={values.cancelActivityForm}>
                          {"취소"}
                        </button>
                      </div>
                    </div>
                  </>
                )}
                <div style={toReactStyle("display:flex;flex-direction:column;gap:0")}>
                  {values.selected.activityTimeline.length === 0 && (
                    <div style={toReactStyle("font-size:12.5px;color:#8B9086;padding:8px 0 4px")}>
                      {"아직 처리된 사항이 없습니다."}
                    </div>
                  )}
                  {values.selected.activityTimeline.map((act, _index0) => (
                    <Fragment key={_index0}>
                      <div style={toReactStyle(`${act.rowStyle}`)}>
                        <div style={toReactStyle("width:6px;height:6px;border-radius:50%;background:#D2D5CD;margin-top:6px;flex:none")}></div>
                        <div style={toReactStyle("min-width:0")}>
                          <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-bottom:3px;flex-wrap:wrap")}>
                            <span style={toReactStyle("font-size:12px;font-weight:600")}>
                              {`${act.typeLabel}`}
                            </span>
                            <span style={toReactStyle("font-size:11px;color:#8B9086")}>
                              {`${act.actorLabel} · ${act.occurredLabel}`}
                            </span>
                          </div>
                          {act.hasNote && (
                            <>
                              <div style={toReactStyle("font-size:13px;color:#1B1E1A;line-height:1.5;margin-bottom:4px")}>
                                {`${act.note}`}
                              </div>
                            </>
                          )}
                          {act.hasLink && (
                            <>
                              <a href={act.linkUrl} target="_blank" style={toReactStyle("font-size:12px;color:#2F8F5B;text-decoration:none")}>
                                {`${act.linkLabel} ↗`}
                              </a>
                            </>
                          )}
                        </div>
                      </div>
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
            <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:18px 20px;display:flex;flex-direction:column;gap:14px;font-size:12.5px;height:fit-content")}>
              <div>
                <div style={toReactStyle("font-size:11px;font-weight:700;color:#8B9086;letter-spacing:.02em;margin-bottom:8px")}>
                  {"취약점 정보"}
                </div>
                <div style={toReactStyle("display:flex;flex-direction:column;gap:7px")}>
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px;white-space:nowrap;flex:none")}>
                      {"패키지"}
                    </span>
                    <span style={toReactStyle("font-family:ui-monospace,monospace;font-size:12.5px;font-weight:600;line-height:18px;min-width:0;text-align:right;overflow-wrap:anywhere")}>
                      {`${values.selected.alert.package_name} · ${values.selected.alert.ecosystem}`}
                    </span>
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px")}>
                      {"CVE"}
                    </span>
                    <span style={toReactStyle("font-family:ui-monospace,monospace;font-size:11.5px;font-weight:600;line-height:18px;text-align:right")}>
                      {`${values.selected.advisory.cve_id || '-'}`}
                    </span>
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px")}>
                      {"GHSA"}
                    </span>
                    <span style={toReactStyle("font-family:ui-monospace,monospace;font-size:11.5px;line-height:18px;text-align:right")}>
                      {`${values.selected.advisory.ghsa_id}`}
                    </span>
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px")}>
                      {"사용 범위"}
                    </span>
                    <span style={toReactStyle("line-height:18px")}>
                      {`${values.selected.scopeLabel}`}
                    </span>
                  </div>
                  {values.selected.hasKnownRelationship && (
                    <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                      <span style={toReactStyle("color:#8B9086;line-height:18px")}>
                        {"의존 관계"}
                      </span>
                      <span style={toReactStyle("line-height:18px")}>
                        {`${values.selected.relationshipLabel}`}
                      </span>
                    </div>
                  )}
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px")}>
                      {"영향 버전"}
                    </span>
                    <span style={toReactStyle("font-family:ui-monospace,monospace;font-size:11px;line-height:18px;text-align:right")}>
                      {`${values.selected.alert.vulnerable_version_range}`}
                    </span>
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px")}>
                      {"수정 버전"}
                    </span>
                    <span style={toReactStyle("font-family:ui-monospace,monospace;font-size:11px;line-height:18px;text-align:right")}>
                      {`${values.selected.alert.first_patched_version || '없음'}`}
                    </span>
                  </div>
                </div>
                <div style={toReactStyle("padding-top:12px;margin-top:10px;border-top:1px solid #F0F1EE")}>
                  <div style={toReactStyle("font-size:11px;font-weight:700;color:#8B9086;letter-spacing:.02em;margin-bottom:7px")}>
                    {"Advisory 요약"}
                  </div>
                  <div style={toReactStyle("font-size:12.5px;color:#1B1E1A;line-height:1.6")}>
                    {`${values.selected.advisory.summary}`}
                  </div>
                  <div style={toReactStyle("display:flex;align-items:center;gap:14px;margin-top:8px;flex-wrap:wrap")}>
                    {values.selected.advisory.cve_id && (
                      <a href={`https://nvd.nist.gov/vuln/detail/${values.selected.advisory.cve_id}`} target="_blank" rel="noreferrer" style={toReactStyle("font-size:12px;color:#2F8F5B;text-decoration:none")}>
                        {"CVE 상세 보기 ↗"}
                      </a>
                    )}
                    <a href={values.selected.alert.html_url} target="_blank" rel="noreferrer" style={toReactStyle("font-size:12px;color:#2F8F5B;text-decoration:none")}>
                      {"GitHub Alert 보기 ↗"}
                    </a>
                  </div>
                </div>
              </div>
              {values.selected.hasPr && (
                <>
                  <div style={toReactStyle("padding-top:12px;border-top:1px solid #F0F1EE")}>
                    <a href={values.selected.automation.prUrl} target="_blank" style={toReactStyle("font-size:12px;color:#2F8F5B;text-decoration:none")}>
                      {"생성된 PR 보기 ↗"}
                    </a>
                  </div>
                </>
              )}
              <div style={toReactStyle("padding-top:12px;border-top:1px solid #F0F1EE")}>
                <div style={toReactStyle("font-size:11px;font-weight:700;color:#8B9086;letter-spacing:.02em;margin-bottom:8px")}>
                  {"REPOSITORY"}
                </div>
                <div style={toReactStyle("display:flex;justify-content:space-between;gap:10px;margin-bottom:6px")}>
                  <span style={toReactStyle("color:#8B9086")}>
                    {"이름"}
                  </span>
                  <a href={values.selected.repositoryUrl} target="_blank" rel="noreferrer" title={values.selected.repository.full_name} style={toReactStyle("font-weight:600;color:#1B1E1A;text-decoration:none;text-align:right")}>
                    {`${values.selected.repository.display_name} ↗`}
                  </a>
                </div>
                <div style={toReactStyle("display:flex;justify-content:space-between;align-items:center;gap:10px")}>
                  <span style={toReactStyle("color:#8B9086")}>
                    {"중요도"}
                  </span>
                  <span style={toReactStyle("font-size:11px;font-weight:500;color:#8B9086;padding:3px 9px;border-radius:20px;border:1px solid #E4E6E1")}>
                    {`${values.selected.importanceLabel}`}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </>
    )}
    </>
  );
}
