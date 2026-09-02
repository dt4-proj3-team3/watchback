import { proxyBackendPost } from '@/lib/backend-proxy';

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { code: 'validation_error', message: '요청 본문이 올바르지 않습니다.', details: null },
      { status: 422 },
    );
  }
  return proxyBackendPost('/api/v1/ai/review', body, { allowReadOnly: true });
}
