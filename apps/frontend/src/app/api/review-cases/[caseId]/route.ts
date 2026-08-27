import { proxyBackendGet, proxyBackendPost } from '@/lib/backend-proxy';

export async function GET(
  _request: Request,
  context: RouteContext<'/api/review-cases/[caseId]'>,
) {
  const { caseId } = await context.params;
  return proxyBackendGet(`/api/v1/review-cases/${encodeURIComponent(caseId)}`);
}

export async function POST(
  request: Request,
  context: RouteContext<'/api/review-cases/[caseId]'>,
) {
  const { caseId } = await context.params;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({
      code: 'validation_error',
      message: '요청 본문이 올바른 JSON이 아닙니다.',
      details: null,
    }, { status: 422 });
  }
  return proxyBackendPost(
    `/api/v1/review-cases/${encodeURIComponent(caseId)}/activities`,
    body,
  );
}
