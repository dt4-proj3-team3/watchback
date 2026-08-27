const ERROR_BODY = {
  code: 'backend_unavailable',
  message: 'Backend에 연결할 수 없습니다.',
  details: null,
};

function backendConfiguration() {
  const baseUrl = process.env.WATCHBACK_API_BASE_URL;
  const organizationId = process.env.WATCHBACK_ORGANIZATION_ID;
  const userId = process.env.WATCHBACK_USER_ID;
  if (!baseUrl || !organizationId || !userId) return null;
  return { baseUrl, organizationId, userId };
}

export async function proxyBackendGet(path: string, search = ''): Promise<Response> {
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
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'X-Organization-ID': config.organizationId,
        'X-User-ID': config.userId,
      },
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
