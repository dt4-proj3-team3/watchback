import { describe, expect, it, vi } from 'vitest';

import { AIReviewError, askAIReview } from './ai-review-data';

describe('AI review data provider', () => {
  it('sends the selected case and session history without persistence options', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      answer: '근거 기반 답변 [1]',
      model: 'gpt-5.6-luna',
      sources: [{ citation: '1', title: 'Evidence' }],
    }), { status: 200, headers: { 'content-type': 'application/json' } }));

    await askAIReview({
      question: '왜 재검토 대상인가요?',
      remediationGroupId: 'a'.repeat(64),
      history: [{ role: 'user', content: '이전 질문' }],
    }, fetcher);

    const [, request] = fetcher.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual({
      question: '왜 재검토 대상인가요?',
      remediation_group_id: 'a'.repeat(64),
      history: [{ role: 'user', content: '이전 질문' }],
    });
    expect(request.body).not.toContain('store');
  });

  it('preserves the backend error code and never falls back to demo', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      code: 'ai_not_configured',
      message: 'AI 검토 도우미가 아직 구성되지 않았습니다.',
    }), { status: 503, headers: { 'content-type': 'application/json' } }));

    await expect(askAIReview({ question: '질문' }, fetcher)).rejects.toMatchObject({
      name: 'AIReviewError',
      status: 503,
      code: 'ai_not_configured',
    });
    expect(AIReviewError).toBeTypeOf('function');
  });
});
