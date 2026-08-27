import { proxyBackendGet } from '@/lib/backend-proxy';

export async function GET(
  _request: Request,
  context: RouteContext<'/api/review-cases/[caseId]'>,
) {
  const { caseId } = await context.params;
  return proxyBackendGet(`/api/v1/review-cases/${encodeURIComponent(caseId)}`);
}
