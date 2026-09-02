import { afterEach, describe, expect, it, vi } from 'vitest';

import { GET } from './route';


describe('remediation groups route', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('forwards context headers, query string, and the backend response', async () => {
    vi.stubEnv('WATCHBACK_API_BASE_URL', 'https://backend.example.test');
    vi.stubEnv('WATCHBACK_ORGANIZATION_ID', '10000000-0000-0000-0000-000000000001');
    vi.stubEnv('WATCHBACK_USER_ID', '20000000-0000-0000-0000-000000000001');
    const fetcher = vi.fn(async (url, init) => {
      expect(url.toString()).toBe(
        'https://backend.example.test/api/v1/remediation-groups?status=all',
      );
      expect(init.headers['X-Organization-ID']).toBe(
        '10000000-0000-0000-0000-000000000001',
      );
      expect(init.headers['X-User-ID']).toBe(
        '20000000-0000-0000-0000-000000000001',
      );
      return new Response(JSON.stringify({ items: [], total: 0 }), {
        headers: { 'content-type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetcher);

    const response = await GET(
      new Request('http://localhost/api/remediation-groups?status=all'),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ items: [], total: 0 });
  });

  it('preserves a JSON backend error', async () => {
    vi.stubEnv('WATCHBACK_API_BASE_URL', 'https://backend.example.test');
    vi.stubEnv('WATCHBACK_ORGANIZATION_ID', '10000000-0000-0000-0000-000000000001');
    vi.stubEnv('WATCHBACK_USER_ID', '20000000-0000-0000-0000-000000000001');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      code: 'organization_scope_violation',
      message: '요청한 조직 범위에 접근할 수 없습니다.',
      details: null,
    }), {
      status: 403,
      headers: { 'content-type': 'application/json' },
    })));

    const response = await GET(new Request('http://localhost/api/remediation-groups'));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: 'organization_scope_violation',
    });
  });
});
