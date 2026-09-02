import { RemediationPreviewPage } from '@/components/remediation-preview-page';

export default async function ReviewCasesPage({
  searchParams,
}: {
  searchParams: Promise<{ repository?: string | string[] }>;
}) {
  const params = await searchParams;
  const repository = Array.isArray(params.repository)
    ? params.repository[0]
    : params.repository;

  return (
    <RemediationPreviewPage
      view="list"
      initialRepositoryFullName={repository ?? null}
    />
  );
}
