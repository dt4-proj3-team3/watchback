import { Fragment, useState } from 'react';
import { DEFAULT_POLICY_MATRIX, PolicyMatrix } from './policy-matrix';
import { toReactStyle } from './style';

const AVAILABLE_REPOSITORIES = [
  { full_name: 'novalink/admin-fe', display_name: 'novalink/admin-fe' },
  { full_name: 'novalink/reporting-api', display_name: 'novalink/reporting-api' },
  { full_name: 'novalink/security-portal', display_name: 'novalink/security-portal' },
  { full_name: 'novalink/batch-worker', display_name: 'novalink/batch-worker' },
];

const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'];

function summarizePolicy(importanceLabel, matrix) {
  const actions = matrix[importanceLabel] ?? [];
  const summaries = [
    ['auto_create_pr', 'PR 자동 생성'],
    ['auto_merge_pr', 'PR 자동 병합'],
  ].map(([action, label]) => {
    const severities = SEVERITIES.filter((_, index) => actions[index] === action);
    return severities.length ? `${severities.join('/')} ${label}` : null;
  }).filter(Boolean);
  return summaries.join(' · ') || '자동조치 없음';
}

export function Repositories({ values }) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isPolicyOpen, setIsPolicyOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedNames, setSelectedNames] = useState([]);
  const [importance, setImportance] = useState('high');
  const [policyMatrix, setPolicyMatrix] = useState(() => Object.fromEntries(
    Object.entries(DEFAULT_POLICY_MATRIX).map(([key, policies]) => [key, [...policies]]),
  ));
  const [addedRepositories, setAddedRepositories] = useState([]);
  const connectedNames = new Set([
    ...values.repoRows.flatMap((repository) => [repository.full_name, repository.display_name]),
    ...addedRepositories.map((repository) => repository.full_name),
  ]);
  const visibleRepositories = AVAILABLE_REPOSITORIES.filter((repository) => (
    repository.display_name.toLowerCase().includes(query.trim().toLowerCase())
  ));
  const repoRows = [...values.repoRows, ...addedRepositories];

  const closeAddModal = () => {
    setIsAddOpen(false);
    setQuery('');
    setSelectedNames([]);
  };

  const addSelectedRepositories = () => {
    const importanceLabel = importance === 'high' ? 'High' : importance === 'medium' ? 'Medium' : 'Low';
    const importanceColors = {
      high: 'background:#FCEFE1;color:#B76A12;border:1px solid #F5D5AF;border-radius:999px;padding:4px 10px;font-size:11px;line-height:16px',
      medium: 'background:#E9F4FC;color:#1876A8;border:1px solid #CBE4F3;border-radius:999px;padding:4px 10px;font-size:11px;line-height:16px',
      low: 'background:#E8F5EE;color:#2F8F5B;border:1px solid #C5E7D4;border-radius:999px;padding:4px 10px;font-size:11px;line-height:16px',
    };
    const selectedRepositories = AVAILABLE_REPOSITORIES
      .filter((repository) => selectedNames.includes(repository.full_name) && !connectedNames.has(repository.full_name))
      .map((repository) => ({
        ...repository,
        importance,
        importanceLabel,
        importanceBadgeStyle: importanceColors[importance],
        openCount: 0,
        criticalOpenCount: 0,
        policySummary: { label: importance === 'high' ? 'High/Medium PR 자동 생성 · Low PR 자동 병합' : importance === 'medium' ? 'High PR 자동 생성 · Medium/Low PR 자동 병합' : 'Critical/High PR 자동 생성 · Medium/Low PR 자동 병합', color: '#687066' },
        onOpen: () => {},
      }));
    setAddedRepositories((current) => [...current, ...selectedRepositories]);
    closeAddModal();
  };

  return (
    <>
    {values.isReposView && (
      <>
        <div className="watchback-page" style={toReactStyle("width:calc(100% - 64px);max-width:1120px;margin:0 auto;padding:46px 0 96px")}>
          <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;margin-bottom:28px")}>
            <h1 style={toReactStyle("font-size:25px;line-height:36px;font-weight:700;margin:0;letter-spacing:-0.01em")}>
              {"저장소"}
            </h1>
            <div style={toReactStyle("display:flex;align-items:center;gap:8px")}><button type="button" onClick={() => setIsPolicyOpen(true)} style={toReactStyle("height:36px;padding:0 14px;border:1px solid #D2D5CD;border-radius:8px;background:#FFFFFF;color:#5B6058;font-family:inherit;font-size:12.5px;font-weight:700;cursor:pointer")}>자동조치 기본 정책</button><button type="button" onClick={() => setIsAddOpen(true)} style={toReactStyle("height:36px;padding:0 14px;border:1px solid #2F8F5B;border-radius:8px;background:#2F8F5B;color:#FFFFFF;font-family:inherit;font-size:12.5px;font-weight:700;cursor:pointer")}>+ 저장소 추가</button></div>
          </div>
          <div style={toReactStyle("display:flex;flex-direction:column;gap:10px")}>
            {repoRows.length === 0 && (
              <div style={toReactStyle("background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:28px 20px;text-align:center;font-size:13px;color:#8B9086")}>
                {"재검토 Case가 연결된 저장소가 없습니다."}
              </div>
            )}
            {repoRows.map((r, _index0) => (
              <Fragment key={_index0}>
                <div style={toReactStyle("position:relative;height:90px;box-sizing:border-box;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:9px;overflow:hidden")}>
                  <button type="button" onClick={r.onOpen} style={toReactStyle("position:absolute;inset:0;background:transparent;border:0;cursor:pointer")} aria-label={`${r.display_name} 재검토 목록 열기`} />
                  <strong style={toReactStyle("position:absolute;left:20px;top:17px;width:600px;font-size:14px;line-height:20px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;pointer-events:none")}>
                    {r.display_name}
                  </strong>
                  <div style={toReactStyle("position:absolute;right:48px;bottom:20px;display:flex;flex-direction:column;align-items:flex-end;gap:8px;pointer-events:none")}>
                    <strong style={toReactStyle(`${r.importanceBadgeStyle};min-width:72px;box-sizing:border-box;text-align:center;font-weight:700`)}>
                      {r.importanceLabel}
                    </strong>
                    <span style={toReactStyle("font-size:12px;line-height:17px;color:#687066;white-space:nowrap")}>
                      {`열린 항목 ${r.openCount}건 · Critical ${r.criticalOpenCount}건`}
                    </span>
                  </div>
                  <span style={toReactStyle("position:absolute;right:19px;top:50%;width:16px;font-size:22px;line-height:22px;color:#C7CDC4;transform:translateY(-50%);pointer-events:none")}>›</span>
                  <span style={toReactStyle(`position:absolute;left:20px;top:52px;max-width:600px;font-size:12px;line-height:18px;font-weight:400;color:${r.policySummary.color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none`)}>
                    {summarizePolicy(r.importanceLabel, policyMatrix)}
                  </span>
                </div>
              </Fragment>
            ))}
          </div>
        </div>
        {isAddOpen && (
          <div role="presentation" style={toReactStyle("position:fixed;inset:0;z-index:80;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(27,30,26,.42)")}>
            <div role="dialog" aria-modal="true" aria-labelledby="add-repository-title" style={toReactStyle("width:520px;max-width:100%;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:14px;box-shadow:0 20px 60px rgba(27,30,26,.2);overflow:hidden")}>
              <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;padding:20px 22px;border-bottom:1px solid #ECEFEB")}>
                <h2 id="add-repository-title" style={toReactStyle("font-size:18px;line-height:26px;font-weight:700;margin:0")}>저장소 추가</h2>
                <button type="button" aria-label="저장소 추가 닫기" onClick={closeAddModal} style={toReactStyle("width:30px;height:30px;border:0;background:transparent;color:#737A71;font-size:21px;line-height:30px;cursor:pointer")}>×</button>
              </div>
              <div style={toReactStyle("padding:20px 22px 22px") }>
                <label style={toReactStyle("display:block;font-size:12px;font-weight:700;color:#5B6058;margin-bottom:7px")}>GitHub 조직</label>
                <div style={toReactStyle("height:38px;display:flex;align-items:center;padding:0 12px;margin-bottom:16px;border:1px solid #DDE2DB;border-radius:8px;background:#F7F8F6;font-size:13px;font-weight:600")}>novalink</div>
                <label htmlFor="repository-search" style={toReactStyle("display:block;font-size:12px;font-weight:700;color:#5B6058;margin-bottom:7px")}>저장소 선택</label>
                <input id="repository-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="저장소 검색" style={toReactStyle("width:100%;height:38px;box-sizing:border-box;padding:0 12px;margin-bottom:10px;border:1px solid #D7DDD4;border-radius:8px;font-family:inherit;font-size:13px;outline:none")} />
                <div style={toReactStyle("max-height:188px;overflow:auto;border:1px solid #E3E7E1;border-radius:8px") }>
                  {visibleRepositories.map((repository) => {
                    const isConnected = connectedNames.has(repository.full_name) || connectedNames.has(repository.display_name);
                    const isSelected = selectedNames.includes(repository.full_name);
                    return (
                      <label key={repository.full_name} style={toReactStyle(`height:46px;display:flex;align-items:center;gap:10px;padding:0 12px;border-bottom:1px solid #F0F2EF;font-size:13px;cursor:${isConnected ? 'default' : 'pointer'};color:${isConnected ? '#9AA097' : '#1B1E1A'}`)}>
                        <input type="checkbox" disabled={isConnected} checked={isConnected || isSelected} onChange={() => setSelectedNames((current) => (
                          isSelected ? current.filter((name) => name !== repository.full_name) : [...current, repository.full_name]
                        ))} />
                        <span style={toReactStyle("flex:1")}>{repository.display_name}</span>
                        {isConnected && <span style={toReactStyle("font-size:11px;color:#8B9086")}>연결됨</span>}
                      </label>
                    );
                  })}
                </div>
                <div style={toReactStyle("margin-top:16px") }>
                  <label style={toReactStyle("font-size:12px;font-weight:700;color:#5B6058")}>중요도
                    <select aria-label="저장소 중요도" value={importance} onChange={(event) => setImportance(event.target.value)} style={toReactStyle("width:100%;height:38px;margin-top:7px;padding:0 40px 0 12px;border:1px solid #D7DDD4;border-radius:8px;background-color:#FFFFFF;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5 6 6.5l5-5' fill='none' stroke='%235B6058' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 16px center;background-size:12px 8px;appearance:none;font-family:inherit;font-size:13px")}>
                      <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                    </select>
                  </label>
                </div>
              </div>
              <div style={toReactStyle("display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:14px 22px;border-top:1px solid #ECEFEB;background:#FAFBFA") }>
                <button type="button" onClick={closeAddModal} style={toReactStyle("height:36px;padding:0 14px;border:1px solid #D7DDD4;border-radius:8px;background:#FFFFFF;color:#5B6058;font-family:inherit;font-size:12.5px;font-weight:600;cursor:pointer")}>취소</button>
                <button type="button" disabled={selectedNames.length === 0} onClick={addSelectedRepositories} style={toReactStyle(`height:36px;padding:0 16px;border:0;border-radius:8px;background:${selectedNames.length === 0 ? '#C9CEC7' : '#2F8F5B'};color:#FFFFFF;font-family:inherit;font-size:12.5px;font-weight:700;cursor:${selectedNames.length === 0 ? 'default' : 'pointer'}`)}>저장소 추가</button>
              </div>
            </div>
          </div>
        )}
        {isPolicyOpen && <div role="presentation" style={toReactStyle("position:fixed;inset:0;z-index:80;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(27,30,26,.42)")}><div role="dialog" aria-modal="true" aria-labelledby="policy-matrix-title" style={toReactStyle("width:1040px;max-width:100%;background:#FFFFFF;border:1px solid #E3E7E1;border-radius:14px;box-shadow:0 20px 60px rgba(27,30,26,.2);overflow:hidden")}><div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;padding:20px 22px;border-bottom:1px solid #ECEFEB")}><h2 id="policy-matrix-title" style={toReactStyle("font-size:18px;line-height:26px;font-weight:700;margin:0")}>자동조치 기본 정책</h2><button type="button" aria-label="자동조치 기본 정책 닫기" onClick={() => setIsPolicyOpen(false)} style={toReactStyle("width:30px;height:30px;border:0;background:transparent;color:#737A71;font-size:21px;line-height:30px;cursor:pointer")}>×</button></div><div style={toReactStyle("padding:22px")}><PolicyMatrix rows={values.policyMatrixRows} matrix={policyMatrix} onChange={(importanceName, index, policy) => setPolicyMatrix((current) => ({ ...current, [importanceName]: current[importanceName].map((value, policyIndex) => policyIndex === index ? policy : value) }))} /></div></div></div>}
      </>
    )}
    </>
  );
}
