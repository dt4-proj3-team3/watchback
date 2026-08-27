import { DemoWatchbackPage } from '@/components/demo-watchback-page';

export default async function ReviewCasePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <DemoWatchbackPage view="detail" selectedId={caseId} />;
}
