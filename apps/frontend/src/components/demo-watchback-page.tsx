import { WatchbackApp } from '@/components/original/watchback-app';
import { getDemoReviewCases } from '@/lib/demo-review-cases';

type View = 'dashboard' | 'list' | 'detail' | 'repos' | 'settings';

export function DemoWatchbackPage({
  view,
  selectedId = null,
}: {
  view: View;
  selectedId?: string | null;
}) {
  return (
    <WatchbackApp
      initialView={view}
      initialSelectedId={selectedId}
      initialCases={getDemoReviewCases()}
    />
  );
}
