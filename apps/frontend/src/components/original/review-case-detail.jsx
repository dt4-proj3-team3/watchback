import { Fragment } from 'react';
import { toReactStyle } from './style';

const SCORE_MARKER_POSITION = {
  90: { left: 106, top: 36 },
  65: { left: 81, top: 11 },
  40: { left: 46, top: 11 },
  15: { left: 21, top: 36 },
};

export function ReviewCaseDetail({ values }) {
  const scoreMarker = SCORE_MARKER_POSITION[values.selected?.rereviewScore] ?? SCORE_MARKER_POSITION[15];

  return (
    <>
    {values.isDetailView && (
      <>
        <div className="watchback-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:34px 0 96px")}>
          <button type="button" aria-label="이전 화면으로" style={toReactStyle("display:flex;align-items:center;gap:6px;font:13px inherit;color:#5B6058;cursor:pointer;margin-bottom:20px;width:fit-content;background:none;border:none;padding:0")} onClick={values.backToPrevious}>
            <span>
              {"←"}
            </span>
            <span>
              {"이전 화면으로"}
            </span>
          </button>
          <div className="watchback-case-summary" style={toReactStyle("position:relative;height:176px;background:#FFFFFF;border:1px solid #E4E6E1;border-radius:9px;margin-bottom:16px;overflow:hidden")}>
            <div aria-label={`재검토 점수 ${values.selected.rereviewScore}점`} style={toReactStyle("position:absolute;left:22px;top:22px;width:132px;height:71px;text-align:center")}>
              <div style={toReactStyle("position:relative;width:132px;height:70px;background:url('/watchback-meter-base.svg') center top/132px 66px no-repeat")}>
                <strong style={toReactStyle("position:absolute;left:0;right:0;bottom:5px;font:500 22px/23px Inter,Arial,sans-serif;color:#515050")}>{values.selected.rereviewScore}</strong>
                <span data-testid="rereview-score-marker" aria-hidden="true" style={toReactStyle(`position:absolute;left:${scoreMarker.left}px;top:${scoreMarker.top}px;width:5px;height:5px;background:url('/watchback-meter-dot.svg') center/5px 5px no-repeat`)}></span>
              </div>
            </div>
            <div style={toReactStyle("position:absolute;left:179px;top:29px;width:330px;display:flex;align-items:center;gap:9px") }>
              <span style={toReactStyle("font:700 20px/28px Inter,Arial,sans-serif;color:#1B1E1A;letter-spacing:-0.01em")}>
                {`${values.selected.alert.package_name}`}
              </span>
              {values.selected.isResolved && (
                <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;padding:3px 9px;border-radius:20px;background:#EEF0EE")}>
                  {"해결됨"}
                </span>
              )}
            </div>
            <div style={toReactStyle("position:absolute;left:179px;top:64px;width:540px;font:400 14px/22px Inter,Arial,sans-serif;color:#1B1E1A")}>
              {`${values.selected.reviewReasonLabel}`}
            </div>
            <div style={toReactStyle("position:absolute;left:33px;top:113px;width:60px")}>
              <div style={toReactStyle("font:400 11px/15px Inter,Arial,sans-serif;color:#7C8379;margin-bottom:5px")}>{"CVSS"}</div>
              <div style={toReactStyle("font:400 12px/19px Inter,Arial,sans-serif;color:#1B1E1A")}>{`${values.selected.advisory.cvss_score}`}</div>
            </div>
            <div style={toReactStyle("position:absolute;left:105px;top:113px;width:70px")}>
              <div style={toReactStyle("font:400 11px/15px Inter,Arial,sans-serif;color:#7C8379;margin-bottom:5px")}>{"패치 버전"}</div>
              <div style={toReactStyle(`font:400 12px/19px Inter,Arial,sans-serif;color:${values.selected.patchColor}`)}>{`${values.selected.patchLabelShort}`}</div>
            </div>
            <div style={toReactStyle("position:absolute;left:187px;top:113px;width:100px")}>
              <div style={toReactStyle("font:400 11px/15px Inter,Arial,sans-serif;color:#7C8379;margin-bottom:5px")}>{"자동조치"}</div>
              <div style={toReactStyle("font:400 12px/19px Inter,Arial,sans-serif;color:#1B1E1A;white-space:nowrap")}>{values.selected.alert.first_patched_version ? 'PR 생성 대상' : values.selected.automationStatusLabel}</div>
            </div>
            <div style={toReactStyle("position:absolute;left:299px;top:113px;width:140px")}>
              <div style={toReactStyle("font:400 11px/15px Inter,Arial,sans-serif;color:#8B9086;margin-bottom:5px")}>{"변화 감지일"}</div>
              <div style={toReactStyle("font:400 12px/19px Inter,Arial,sans-serif;color:#1B1E1A")}>{values.selected.reviewReasonDateLabel || '-'}</div>
            </div>
            <div style={toReactStyle("position:absolute;right:14px;top:22px;display:flex;gap:8px") }>
                {values.actionButtons.map((btn, _index0) => (
                  <Fragment key={_index0}>
                    <button style={toReactStyle(`${btn.style}`)} onClick={btn.onClick} title={btn.title}>
                      {`${btn.label}`}
                    </button>
                  </Fragment>
                ))}
            </div>
          </div>
          {values.showActionMenu && (
            <div style={toReactStyle("background:#FFFFFF;border:1px solid #D2D5CD;border-radius:10px;padding:16px 18px;margin-bottom:16px")}>
              <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px")}>
                <div>
                  <div style={toReactStyle("font-size:13px;font-weight:700;margin-bottom:3px")}>{"조치 방법 선택"}</div>
                  <div style={toReactStyle("font-size:11.5px;color:#8B9086")}>{"외부 협업 도구에서 이어갈 작업을 선택하세요."}</div>
                </div>
                <button style={toReactStyle("font-size:12px;font-family:inherit;color:#5B6058;background:none;border:none;cursor:pointer")} onClick={values.closeActionMenu}>{"닫기"}</button>
              </div>
              <div style={toReactStyle("display:grid;grid-template-columns:1fr 1fr;gap:10px")}>
                <button style={toReactStyle("text-align:left;font-family:inherit;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:8px;padding:12px 14px;cursor:pointer")} onClick={values.createIssue}>
                  <div style={toReactStyle("font-size:12.5px;font-weight:700;color:#1B1E1A;margin-bottom:3px")}>{"GitHub Issue 생성"}</div>
                  <div style={toReactStyle("font-size:11.5px;color:#8B9086")}>{"담당자가 검토하고 수정할 업무를 만듭니다."}</div>
                </button>
                <button style={toReactStyle("text-align:left;font-family:inherit;background:#F5F6F3;border:1px solid #E4E6E1;border-radius:8px;padding:12px 14px;cursor:pointer")} onClick={values.createPullRequest}>
                  <div style={toReactStyle("font-size:12.5px;font-weight:700;color:#1B1E1A;margin-bottom:3px")}>{"업데이트 PR 생성"}</div>
                  <div style={toReactStyle("font-size:11.5px;color:#8B9086")}>{"수정 버전으로 의존성을 업데이트합니다."}</div>
                </button>
              </div>
              {values.actionNotice && (
                <div role="status" style={toReactStyle("background:#FCEFE1;border:1px solid #E9C99A;border-radius:7px;padding:9px 12px;margin-top:10px;font-size:12px;color:#9A5A16")}>
                  {`${values.actionNotice}`}
                </div>
              )}
            </div>
          )}
          <div style={toReactStyle("background:#FFFFFF;border-left:3px solid #8B9086;border-radius:8px;padding:14px 18px;margin-bottom:20px;font-size:12.5px;line-height:1.6;color:#5B6058")}>
            {"Watchback은 위험 변화 신호를 제공하며, 실제 악용 여부와 조치 필요성은 검토자가 판단합니다."}
          </div>
          <div className="watchback-detail-grid" style={toReactStyle("display:grid;grid-template-columns:1fr 300px;gap:20px;align-items:start")}>
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
                <div style={toReactStyle("display:flex;flex-direction:column;gap:14px")}>
                  {values.selected.evidenceGroups.map((group) => (
                    <div key={group.id} style={toReactStyle("padding-left:14px;border-left:2px solid #D2D5CD")}>
                      <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;flex-wrap:wrap")}>
                        <span style={toReactStyle("font-size:12px;font-weight:700;color:#1B1E1A")}>
                          {group.changeTypeLabel}
                        </span>
                        {group.selectedLabel && (
                          <span style={toReactStyle("font-size:11px;color:#8B9086")}>
                            {`후보 선정 ${group.selectedLabel}`}
                          </span>
                        )}
                      </div>
                      {group.sourceAnnotations.map((annotation) => (
                        <div key={`${annotation.snapshot_date}-${annotation.annotation_type}`} style={toReactStyle("background:#FFF8ED;border:1px solid #E9C99A;border-radius:8px;padding:10px 12px;margin-bottom:8px")}>
                          <div style={toReactStyle("display:flex;align-items:flex-start;justify-content:space-between;gap:12px")}>
                            <div>
                              <div style={toReactStyle("font-size:12px;font-weight:700;color:#9A5A16")}>
                                {annotation.label}
                              </div>
                              <div style={toReactStyle("font-size:11px;color:#8B9086;margin-top:3px")}>
                                {`변동일 ${annotation.snapshot_date.replaceAll('-', '.')}`}
                              </div>
                            </div>
                            <a href={annotation.source_url} target="_blank" rel="noreferrer" style={toReactStyle("font-size:11.5px;color:#2F8F5B;text-decoration:none;white-space:nowrap;margin-left:auto")}>
                              {"출처 보기 ↗"}
                            </a>
                          </div>
                          <div style={toReactStyle("font-size:12px;color:#5B6058;line-height:1.5;margin-top:6px")}>
                            {annotation.description}
                          </div>
                        </div>
                      ))}
                      <div style={toReactStyle("display:flex;flex-direction:column;gap:8px")}>
                      {group.evidence.map((ev) => (
                      <div key={ev.id} style={toReactStyle("padding:11px 14px;background:#F5F6F3;border-radius:8px")}>
                        <div style={toReactStyle("display:flex;align-items:center;gap:12px;flex-wrap:wrap")}>
                          <span style={toReactStyle("font-size:12px;font-weight:600;color:#1B1E1A;width:170px;flex:none;white-space:nowrap")}>
                            {`${ev.signalLabel}`}
                          </span>
                          <span className="watchback-evidence-values" style={toReactStyle("display:flex;align-items:center;gap:12px;margin-left:auto;white-space:nowrap")}>
                            <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#8B9086")}>
                              {`${ev.previousValueLabel}`}
                            </span>
                            <span style={toReactStyle("color:#D2D5CD")}>
                              {"→"}
                            </span>
                            <span style={toReactStyle("font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#1B1E1A;font-weight:600")}>
                              {`${ev.currentValueLabel}`}
                            </span>
                          </span>
                        </div>
                        {ev.observedLabel && (
                          <div style={toReactStyle("font-size:11px;color:#8B9086;margin-top:3px")}>
                            {`관찰일 ${ev.observedLabel}`}
                          </div>
                        )}
                        <div style={toReactStyle(`font-size:12.5px;color:#5B6058;line-height:1.5;margin-top:${ev.observedLabel ? '5px' : '6px'}`)}>
                          {`${ev.reasonSummary}`}
                        </div>
                      </div>
                      ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:20px 22px")}>
                <div style={toReactStyle("margin-bottom:14px")}>
                  <div style={toReactStyle("font-size:14px;font-weight:700")}>
                    {"검토 활동"}
                  </div>
                </div>
                {values.showActivityForm && (
                  <>
                    <div style={toReactStyle("background:#F5F6F3;border:1px solid #E4E6E1;border-radius:10px;padding:14px 16px;margin-bottom:14px")}>
                      <div style={toReactStyle("font-size:12.5px;font-weight:600;margin-bottom:8px")}>
                        {`${values.activityFormTitle}`}
                      </div>
                      <textarea aria-label="활동 메모" style={toReactStyle("width:100%;box-sizing:border-box;font-family:inherit;font-size:13px;line-height:1.6;color:#1B1E1A;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:8px;padding:10px 12px;resize:vertical;min-height:56px")} placeholder="검토 근거나 판단 사유를 입력하세요" value={values.noteDraft} onChange={values.onNoteChange} disabled={values.isSubmittingActivity}></textarea>
                      <div style={toReactStyle("display:flex;align-items:center;gap:8px;margin-top:10px")}>
                        <select aria-label="외부 링크 유형" style={toReactStyle("font-size:12px;font-family:inherit;color:#1B1E1A;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:6px 8px")} value={values.linkType} onChange={values.onLinkTypeChange} disabled={values.isSubmittingActivity}>
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
                        <input aria-label="외부 링크 URL" style={toReactStyle("flex:1;font-size:12px;font-family:inherit;color:#1B1E1A;background:#FFFFFF;border:1px solid #D2D5CD;border-radius:7px;padding:7px 10px")} placeholder="https://github.com/org/repo/issues/21" value={values.linkUrl} onChange={values.onLinkUrlChange} disabled={values.isSubmittingActivity} />
                        <button style={toReactStyle("font-size:12px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer;white-space:nowrap")} onClick={values.submitActivity} disabled={values.isSubmittingActivity}>
                          {values.isSubmittingActivity ? "기록 중…" : "기록하기"}
                        </button>
                        <button style={toReactStyle("font-size:12px;font-family:inherit;color:#5B6058;background:none;border:none;cursor:pointer")} onClick={values.cancelActivityForm} disabled={values.isSubmittingActivity}>
                          {"취소"}
                        </button>
                      </div>
                      {values.activityError && (
                        <div role="alert" style={toReactStyle("font-size:12px;color:#A6321B;margin-top:8px")}>
                          {`${values.activityError}`}
                        </div>
                      )}
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
                  <div style={toReactStyle("display:flex;align-items:flex-start;justify-content:space-between;gap:10px;min-height:18px")}>
                    <span style={toReactStyle("color:#8B9086;line-height:18px;white-space:nowrap")}>
                      {"영향 파일"}
                    </span>
                    <span style={toReactStyle("font-family:ui-monospace,monospace;font-size:11px;line-height:18px;text-align:right;overflow-wrap:anywhere")}>
                      {values.selected.manifestLabel}
                    </span>
                  </div>
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
