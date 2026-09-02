import { afterEach, describe, expect, it, vi } from 'vitest';

import { proxyBackendGet, proxyBackendPost } from './backend-proxy';

const ORGANIZATION_ID = 'ff178e49-d218-50b7-bf56-ac3513330b99';
const USER_ID = '7889d975-3d64-536f-8740-3d0a28ee3a1d';

function configureBackend() {
  vi.stubEnv('WATCHBACK_API_BASE_URL', 'https://backend.example.test');
  vi.stubEnv('WATCHBACK_ORGANIZATION_ID', ORGANIZATION_ID);
  vi.stubEnv('WATCHBACK_USER_ID', USER_ID);
}

describe('backend proxy', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('forwards the development context and preserves a JSON response', async () => {
    configureBackend();
    const fetchMock = vi.fn(async (_url, init) => {
      expect(init.headers['X-Organization-ID']).toBe(ORGANIZATION_ID);
      expect(init.headers['X-User-ID']).toBe(USER_ID);
      return new Response(JSON.stringify({ items: [], page: 1, page_size: 100, total: 0 }), {
        headers: { 'content-type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyBackendGet('/api/v1/review-cases', '?status=all');
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe('https://backend.example.test/api/v1/review-cases?status=all');
  });

  it('preserves backend contract errors', async () => {
    configureBackend();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      code: 'review_case_not_found', message: '없음', details: null,
    }), { status: 404, headers: { 'content-type': 'application/json' } })));
    const response = await proxyBackendGet('/api/v1/review-cases/missing');
    expect(response.status).toBe(404);
    expect(await response.json()).toMatchObject({ code: 'review_case_not_found' });
  });

  it('forwards activity JSON and preserves the created response', async () => {
    configureBackend();
    const payload = {
      activity_type: 'risk_accepted',
      candidate_id: '10000000-0000-0000-0000-000000000001',
      note: '위험을 수용합니다.',
    };
    const fetchMock = vi.fn(async (_url, init) => {
      expect(init.method).toBe('POST');
      expect(init.headers['Content-Type']).toBe('application/json');
      expect(JSON.parse(init.body)).toEqual(payload);
      return new Response(JSON.stringify({ case_status: 'resolved', activity: { id: 'activity-id' } }), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyBackendPost(
      '/api/v1/review-cases/case-id/activities',
      payload,
    );
    expect(response.status).toBe(201);
    expect(await response.json()).toMatchObject({ case_status: 'resolved' });
  });

  it('blocks activity writes in a read-only preview without calling the backend', async () => {
    configureBackend();
    vi.stubEnv('WATCHBACK_READ_ONLY', 'true');
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyBackendPost(
      '/api/v1/review-cases/case-id/activities',
      { activity_type: 'risk_accepted' },
    );

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({
      code: 'read_only',
      message: '공개 미리보기에서는 검토 활동을 기록할 수 없습니다.',
      details: null,
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('allows a read-only AI query POST in a public preview', async () => {
    configureBackend();
    vi.stubEnv('WATCHBACK_READ_ONLY', 'true');
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ answer: '근거 답변' }), {
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyBackendPost(
      '/api/v1/ai/review',
      { question: '왜 검토해야 하나요?' },
      { allowReadOnly: true },
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('sanitizes missing configuration, transport errors, and non-JSON responses', async () => {
    expect((await proxyBackendGet('/api/v1/review-cases')).status).toBe(502);

    configureBackend();
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('secret upstream details'); }));
    const transport = await proxyBackendGet('/api/v1/review-cases');
    expect(await transport.json()).toEqual({
      code: 'backend_unavailable', message: 'Backend에 연결할 수 없습니다.', details: null,
    });

    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>error</html>', { status: 500 })));
    expect((await proxyBackendGet('/api/v1/review-cases')).status).toBe(502);
  });
});
