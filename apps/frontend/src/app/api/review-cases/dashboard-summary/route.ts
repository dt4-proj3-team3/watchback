import { proxyBackendGet } from '@/lib/backend-proxy';

export async function GET() {
  return proxyBackendGet('/api/v1/review-cases/dashboard-summary');
}
