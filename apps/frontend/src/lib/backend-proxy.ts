const ERROR_BODY = {
  code: 'backend_unavailable',
  message: 'Backend에 연결할 수 없습니다.',
  details: null,
};

const READ_ONLY_BODY = {
  code: 'read_only',
  message: '공개 미리보기에서는 검토 활동을 기록할 수 없습니다.',
  details: null,
};

function backendConfiguration() {
  const baseUrl = process.env.WATCHBACK_API_BASE_URL;
  const organizationId = process.env.WATCHBACK_ORGANIZATION_ID;
  const userId = process.env.WATCHBACK_USER_ID;
  if (!baseUrl || !organizationId || !userId) return null;
  return { baseUrl, organizationId, userId };
}

async function proxyBackend(
  path: string,
  { method = 'GET', search = '', body }: { method?: 'GET' | 'POST'; search?: string; body?: unknown } = {},
): Promise<Response> {
  const config = backendConfiguration();
  if (!config) return Response.json(ERROR_BODY, { status: 502 });

  let target: URL;
  try {
    target = new URL(path, config.baseUrl.endsWith('/') ? config.baseUrl : `${config.baseUrl}/`);
  } catch {
    return Response.json(ERROR_BODY, { status: 502 });
  }
  target.search = search;

  try {
    const upstream = await fetch(target, {
      method,
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        'X-Organization-ID': config.organizationId,
        'X-User-ID': config.userId,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const text = await upstream.text();
    const contentType = upstream.headers.get('content-type') ?? '';
    if (!contentType.includes('application/json')) {
      return Response.json(ERROR_BODY, { status: 502 });
    }
    return new Response(text, {
      status: upstream.status,
      headers: { 'content-type': 'application/json' },
    });
  } catch {
    return Response.json(ERROR_BODY, { status: 502 });
  }
}

export function proxyBackendGet(path: string, search = ''): Promise<Response> {
  return proxyBackend(path, { search });
}

export function proxyBackendPost(
  path: string,
  body: unknown,
  { allowReadOnly = false }: { allowReadOnly?: boolean } = {},
): Promise<Response> {
  if (!allowReadOnly && process.env.WATCHBACK_READ_ONLY === 'true') {
    return Promise.resolve(Response.json(READ_ONLY_BODY, { status: 403 }));
  }
  return proxyBackend(path, { method: 'POST', body });
}
