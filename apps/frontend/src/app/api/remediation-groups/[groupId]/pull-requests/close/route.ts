import { proxyBackendPost } from '@/lib/backend-proxy';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ groupId: string }> },
) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { code: 'validation_error', message: '요청 본문이 올바르지 않습니다.', details: null },
      { status: 422 },
    );
  }
  const { groupId } = await params;
  return proxyBackendPost(
    `/api/v1/remediation-groups/${encodeURIComponent(groupId)}/pull-requests/close`,
    body,
  );
}
