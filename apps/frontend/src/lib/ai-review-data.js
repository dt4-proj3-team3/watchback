export class AIReviewError extends Error {
  constructor(message, status = 500, code = 'ai_review_error') {
    super(message);
    this.name = 'AIReviewError';
    this.status = status;
    this.code = code;
  }
}

export async function askAIReview({ question, caseId = null, remediationGroupId = null, history = [] }, fetcher = fetch) {
  const response = await fetcher('/api/ai/review', {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      history,
      ...(caseId ? { case_id: caseId } : {}),
      ...(remediationGroupId ? { remediation_group_id: remediationGroupId } : {}),
    }),
  });
  let body = null;
  try {
    body = await response.json();
  } catch {
    // The proxy converts upstream failures to JSON; keep a safe fallback.
  }
  if (!response.ok) {
    throw new AIReviewError(
      body?.message ?? 'AI 검토 도우미의 답변을 불러오지 못했습니다.',
      response.status,
      body?.code ?? 'ai_review_error',
    );
  }
  if (typeof body?.answer !== 'string' || !Array.isArray(body?.sources)) {
    throw new AIReviewError('AI 응답 형식이 올바르지 않습니다.', 502, 'invalid_ai_response');
  }
  return body;
}
