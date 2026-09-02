import { RemediationPreviewPage } from '@/components/remediation-preview-page';

export default async function ReviewCasePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <RemediationPreviewPage view="list" initialExpandedGroupId={decodeURIComponent(caseId)} />;
}
