'use client';

import { useEffect, useState } from 'react';
import { askAIReview } from '@/lib/ai-review-data';
import { toReactStyle } from './style';

const GLOBAL_SUGGESTIONS = [
  '지금 우선 확인할 취약점은?',
  '영향 저장소가 많은 항목을 알려줘',
  'KEV 등재 항목을 요약해줘',
];

const DETAIL_SUGGESTIONS = [
  '이 취약점들은 어떤 조건에서 문제가 되나요?',
  '우리 저장소에서 이 취약점들의 발생 조건이 확인되나요?',
  '이 업데이트로 어떤 문제가 해결되나요?',
  '업데이트할 때 확인할 변경사항이 있나요?',
];
const MINIMUM_LOADING_MS = 2000;
const STREAM_WORDS_PER_TICK = 6;
const STREAM_TICK_MS = 40;

function InlineMarkdown({ text }) {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g).filter(Boolean);
  return tokens.map((token, index) => {
    if (token.startsWith('**') && token.endsWith('**')) {
      return <strong key={`${index}-${token}`}><InlineMarkdown text={token.slice(2, -2)} /></strong>;
    }
    if (token.startsWith('`') && token.endsWith('`')) {
      return <code key={`${index}-${token}`} style={toReactStyle('padding:1px 4px;border-radius:4px;background:#E7EAE5;font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace')}>{token.slice(1, -1)}</code>;
    }
    if (/^\[\d+\]$/.test(token)) {
      return <sup key={`${index}-${token}`} style={toReactStyle('margin-left:2px;color:#9A9F97;font-size:9px;line-height:0;font-weight:600;vertical-align:super')}>{token}</sup>;
    }
    return <span key={`${index}-${token}`}>{token}</span>;
  });
}

function MarkdownAnswer({ text }) {
  return <div>{text.split('\n').map((line, index) => {
    if (!line.trim()) return <div key={index} style={toReactStyle('height:8px')} />;
    const listItem = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+)$/);
    if (listItem) return <div key={index} style={toReactStyle('display:flex;align-items:flex-start;gap:7px;margin:3px 0')}><span aria-hidden="true">•</span><span><InlineMarkdown text={listItem[1]} /></span></div>;
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) return <div key={index} style={toReactStyle('font-weight:700;margin:5px 0 2px')}><InlineMarkdown text={heading[1]} /></div>;
    return <div key={index}><InlineMarkdown text={line} /></div>;
  })}</div>;
}

export function AiAssistantPreview({ values }) {
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [messagesByContext, setMessagesByContext] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const selected = values.selected;
  const aiEnabled = values.dataSource === 'db';
  const contextKey = selected?.remediationGroupId
    ?? selected?.caseId
    ?? selected?.id
    ?? selected?.advisory?.cve_id
    ?? (values.isDashboardView ? 'dashboard' : values.isListView ? 'list' : 'global');
  const messages = messagesByContext[contextKey] ?? [];
  const contextLabel = selected
    ? `${selected.advisory.cve_id} · ${selected.affectedRepositoryLabel}`
    : values.isDashboardView
    ? '조직 위험 현황'
    : values.isListView
    ? `재검토 목록 · ${values.resultCountLabel}`
    : 'Watchback 전체';
  const suggestions = selected ? DETAIL_SUGGESTIONS : GLOBAL_SUGGESTIONS;
  const remainingSuggestions = suggestions.filter((suggestion) => (
    !messages.some((message) => message.question === suggestion)
  ));

  useEffect(() => {
    document.body.classList.toggle('watchback-ai-docked', isOpen);
    return () => document.body.classList.remove('watchback-ai-docked');
  }, [isOpen]);

  const askQuestion = async (questionValue) => {
    const question = questionValue.trim();
    if (!question || isSubmitting) return;
    setDraft('');
    setError('');
    if (!aiEnabled) {
      setError('AI 답변은 실제 DB 모드에서 확인할 수 있습니다.');
      return;
    }
    const requestId = `${contextKey}-${messages.length}`;
    const pendingMessage = {
      id: requestId,
      question,
      answer: '',
      sources: [],
      model: null,
      status: 'loading',
    };
    const updatePendingMessage = (updates) => {
      setMessagesByContext((contexts) => ({
        ...contexts,
        [contextKey]: (contexts[contextKey] ?? []).map((message) => (
          message.id === requestId ? { ...message, ...updates } : message
        )),
      }));
    };
    setMessagesByContext((contexts) => ({
      ...contexts,
      [contextKey]: [...(contexts[contextKey] ?? []), pendingMessage],
    }));
    setIsSubmitting(true);
    try {
      const minimumLoading = new Promise((resolve) => {
        window.setTimeout(resolve, MINIMUM_LOADING_MS);
      });
      const history = messages.flatMap((message) => [
        { role: 'user', content: message.question },
        { role: 'assistant', content: message.answer },
      ]).slice(-8);
      const [response] = await Promise.all([
        askAIReview({
          question,
          caseId: selected?.remediationGroupId ? null : (selected?.caseId ?? selected?.id ?? null),
          remediationGroupId: selected?.remediationGroupId ?? null,
          history,
        }),
        minimumLoading,
      ]);
      const words = response.answer.match(/\S+\s*/g) ?? [response.answer];
      updatePendingMessage({ status: 'streaming' });
      for (let index = STREAM_WORDS_PER_TICK; index < words.length; index += STREAM_WORDS_PER_TICK) {
        updatePendingMessage({ answer: words.slice(0, index).join('') });
        await new Promise((resolve) => window.setTimeout(resolve, STREAM_TICK_MS));
      }
      updatePendingMessage({
        answer: response.answer,
        sources: response.sources,
        model: response.model,
        status: 'complete',
      });
    } catch (requestError) {
      updatePendingMessage({ status: 'failed' });
      setError(requestError instanceof Error ? requestError.message : 'AI 답변을 불러오지 못했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitQuestion = (event) => {
    event.preventDefault();
    void askQuestion(draft);
  };

  if (!isOpen) {
    return <button type="button" aria-label="AI 도우미 열기" onClick={() => setIsOpen(true)} style={toReactStyle("position:fixed;right:24px;bottom:72px;z-index:45;display:flex;align-items:center;gap:8px;height:44px;padding:0 16px;border:1px solid #1F8F60;border-radius:24px;background:#1F8F60;color:#FFFFFF;font:600 12.5px/1 'Noto Sans KR',sans-serif;box-shadow:0 8px 24px rgba(27,30,26,.18);cursor:pointer")}>
      <span aria-hidden="true" style={toReactStyle("font-size:16px")}>✦</span>
      <span>AI 도우미</span>
    </button>;
  }

  return <aside className="watchback-ai-panel" aria-label="Watchback AI 도우미" style={toReactStyle("position:fixed;right:0;top:64px;bottom:0;z-index:45;width:410px;box-sizing:border-box;display:flex;flex-direction:column;background:#FFFFFF;border-left:1px solid #DDE2DC;box-shadow:-10px 0 30px rgba(27,30,26,.1)")}>
    <header style={toReactStyle("padding:18px 18px 14px;border-bottom:1px solid #E4E6E1")}>
      <div style={toReactStyle("display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px")}>
        <div style={toReactStyle("display:flex;align-items:center;gap:9px")}>
          <span aria-hidden="true" style={toReactStyle("display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:#E7F3EC;color:#1F8F60;font-size:15px")}>✦</span>
          <strong style={toReactStyle("font-size:14px;color:#1B1E1A")}>Watchback AI</strong>
        </div>
        <button type="button" aria-label="AI 도우미 닫기" onClick={() => setIsOpen(false)} style={toReactStyle("width:30px;height:30px;border:0;border-radius:7px;background:transparent;color:#737A71;font-size:18px;cursor:pointer")}>×</button>
      </div>
      <div style={toReactStyle("display:flex;align-items:center;gap:7px;padding:8px 10px;background:#F5F6F3;border-radius:7px;font-size:11px;color:#5B6058") }>
        <span style={toReactStyle("color:#8B9086")}>현재 컨텍스트</span>
        <strong style={toReactStyle("overflow:hidden;text-overflow:ellipsis;white-space:nowrap")}>{contextLabel}</strong>
      </div>
    </header>

    <div style={toReactStyle("flex:1;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:14px") }>
      <div style={toReactStyle("align-self:flex-start;max-width:88%;padding:12px 13px;background:#F5F6F3;border-radius:4px 12px 12px 12px;font-size:12.5px;line-height:1.6;color:#3F443D") }>
        현재 패키지의 조치 범위와 취약 조건을 근거와 함께 확인할 수 있습니다.
      </div>
      {messages.length === 0 && remainingSuggestions.length > 0 && <div>
        <div style={toReactStyle("font-size:10px;font-weight:700;color:#8B9086;margin-bottom:8px")}>추천 질문</div>
        <div style={toReactStyle("display:flex;flex-direction:column;align-items:flex-start;gap:7px") }>
          {remainingSuggestions.map((suggestion) => <button key={suggestion} type="button" disabled={isSubmitting} onClick={() => { void askQuestion(suggestion); }} style={toReactStyle(`max-width:100%;text-align:left;font:500 11.5px/17px 'Noto Sans KR',sans-serif;color:#2F6F52;background:#FFFFFF;border:1px solid #BFE0CE;border-radius:16px;padding:6px 10px;cursor:${isSubmitting ? 'default' : 'pointer'};opacity:${isSubmitting ? '.55' : '1'}`)}>{suggestion}</button>)}
        </div>
      </div>}
      {messages.map((message, index) => <div key={message.id ?? `${index}-${message.question}`} style={toReactStyle('display:contents')}>
        <div style={toReactStyle("align-self:flex-end;max-width:84%;padding:10px 12px;background:#1F8F60;border-radius:12px 4px 12px 12px;font-size:12.5px;line-height:1.55;color:#FFFFFF")}>{message.question}</div>
        {message.status === 'loading'
          ? <div role="status" style={toReactStyle("align-self:flex-start;padding:10px 12px;background:#F5F6F3;border-radius:4px 12px 12px 12px;font-size:12px;color:#737A71")}>근거를 확인하고 있습니다…</div>
          : message.status !== 'failed' && <div style={toReactStyle("align-self:flex-start;max-width:88%;padding:12px 13px;background:#F5F6F3;border-radius:4px 12px 12px 12px;font-size:12.5px;line-height:1.6;color:#3F443D;white-space:pre-wrap") }>
          <MarkdownAnswer text={message.answer} />
          {message.status === 'complete' && message.sources.length > 0 && <div style={toReactStyle("display:flex;flex-direction:column;gap:5px;margin-top:9px;padding-top:8px;border-top:1px solid #DDE2DC;font-size:10.5px;color:#737A71")}>{message.sources.map((source) => source.source_url
            ? <a key={source.citation} href={source.source_url} target="_blank" rel="noreferrer" style={toReactStyle('color:#2F8F5B;text-decoration:none')}><strong>[{source.citation}]</strong> {source.title} ↗</a>
            : <span key={source.citation}><strong>[{source.citation}]</strong> {source.title}</span>)}</div>}
        </div>}
      </div>)}
      {messages.length > 0 && !isSubmitting && remainingSuggestions.length > 0 && <div style={toReactStyle("display:flex;flex-direction:column;align-items:flex-start;gap:7px") }>
        {remainingSuggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => { void askQuestion(suggestion); }} style={toReactStyle("max-width:100%;text-align:left;font:500 11.5px/17px 'Noto Sans KR',sans-serif;color:#2F6F52;background:#FFFFFF;border:1px solid #BFE0CE;border-radius:16px;padding:6px 10px;cursor:pointer")}>{suggestion}</button>)}
      </div>}
      {error && <div role="alert" style={toReactStyle('align-self:flex-start;max-width:88%;padding:10px 12px;background:#FCEFE1;border:1px solid #E9C99A;border-radius:8px;font-size:11.5px;line-height:18px;color:#9A5A16')}>{error}</div>}
    </div>

    <form onSubmit={submitQuestion} style={toReactStyle("padding:14px 16px 16px;border-top:1px solid #E4E6E1;background:#FFFFFF") }>
      <div style={toReactStyle("display:flex;align-items:flex-end;gap:8px;padding:8px 8px 8px 12px;border:1px solid #D2D5CD;border-radius:12px;background:#FFFFFF") }>
        <textarea aria-label="AI 질문" value={draft} onChange={(event) => setDraft(event.target.value)} rows={2} placeholder="현재 화면에 대해 질문하세요" style={toReactStyle("flex:1;min-height:40px;max-height:110px;resize:none;border:0;outline:0;padding:3px 0;font:12.5px/18px 'Noto Sans KR',sans-serif;color:#1B1E1A;background:transparent")}></textarea>
        <button type="submit" aria-label="질문 보내기" disabled={!draft.trim() || isSubmitting} style={toReactStyle(`width:32px;height:32px;border:0;border-radius:8px;background:${draft.trim() && !isSubmitting ? '#1F8F60' : '#DDE2DC'};color:#FFFFFF;font-size:15px;cursor:${draft.trim() && !isSubmitting ? 'pointer' : 'default'}`)}>↑</button>
      </div>
      <div style={toReactStyle("font-size:9.5px;line-height:14px;color:#9A9F97;text-align:center;margin-top:7px")}>AI 답변은 원문 근거와 함께 검토하세요.</div>
    </form>
  </aside>;
}
