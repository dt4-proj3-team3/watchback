import { proxyBackendGet } from '@/lib/backend-proxy';

export async function GET(request: Request) {
  return proxyBackendGet('/api/v1/review-cases', new URL(request.url).search);
}
