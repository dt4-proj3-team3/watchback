import { notFound } from 'next/navigation';

import { DemoWatchbackPage } from '@/components/demo-watchback-page';
import { hasDemoReviewCase } from '@/lib/demo-review-cases';

export default async function ReviewCasePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;

  if (!hasDemoReviewCase(caseId)) {
    notFound();
  }

  return <DemoWatchbackPage view="detail" selectedId={caseId} />;
}
