'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';

import { WatchbackApp } from '@/components/original/watchback-app';
import {
  createReviewActivity,
  loadReviewCase,
  loadReviewCases,
  loadDashboardSummary,
  readStoredDataSource,
  storeDataSource,
  subscribeToDataSource,
} from '@/lib/review-case-data';

type View = 'dashboard' | 'list' | 'detail' | 'repos' | 'settings';

const CASE_DATA_VIEWS = new Set<View>(['dashboard', 'list', 'detail', 'repos']);

export function DemoWatchbackPage({
  view,
  selectedId = null,
}: {
  view: View;
  selectedId?: string | null;
}) {
  const usesCaseData = CASE_DATA_VIEWS.has(view);
  const dataSource = useSyncExternalStore(
    subscribeToDataSource,
    () => readStoredDataSource(window.localStorage),
    () => 'db',
  ) as 'db' | 'demo';
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error' | 'not_found'>(
    usesCaseData ? 'loading' : 'ready',
  );
  const [loadError, setLoadError] = useState('');
  const [cases, setCases] = useState<Awaited<ReturnType<typeof loadReviewCases>>>([]);
  const [dashboardSummary, setDashboardSummary] = useState<Awaited<ReturnType<typeof loadDashboardSummary>>>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!usesCaseData) return;

    let cancelled = false;

    const request = view === 'detail' && selectedId
      ? loadReviewCase(dataSource, selectedId).then((detail) => ({ cases: [detail], dashboardSummary: null }))
      : Promise.all([
        loadReviewCases(dataSource),
        view === 'dashboard' ? loadDashboardSummary(dataSource) : Promise.resolve(null),
      ]).then(([nextCases, nextSummary]) => ({ cases: nextCases, dashboardSummary: nextSummary }));

    request
      .then((result) => {
        if (cancelled) return;
        setCases(result.cases);
        setDashboardSummary(result.dashboardSummary);
        setLoadState('ready');
      })
      .catch((error) => {
        if (cancelled) return;
        setCases([]);
        setDashboardSummary(null);
        setLoadError(error instanceof Error ? error.message : '재검토 데이터를 불러오지 못했습니다.');
        setLoadState(error?.status === 404 ? 'not_found' : 'error');
      });

    return () => {
      cancelled = true;
    };
  }, [dataSource, retryKey, selectedId, usesCaseData, view]);

  function changeDataSource(source: 'db' | 'demo') {
    if (source === dataSource) return;
    if (usesCaseData) setLoadState('loading');
    setLoadError('');
    storeDataSource(window.localStorage, source);
  }

  async function recordActivity(caseId: string, payload: unknown) {
    await createReviewActivity(dataSource, caseId, payload);
    const detail = await loadReviewCase(dataSource, caseId);
    setCases([detail]);
    return detail;
  }

  return (
    <WatchbackApp
      initialView={view}
      initialSelectedId={selectedId}
      initialCases={cases}
      dashboardSummary={dashboardSummary}
      dataSource={dataSource}
      onDataSourceChange={changeDataSource}
      loadState={usesCaseData ? loadState : 'ready'}
      loadError={loadError}
      onRetry={() => {
        setLoadState('loading');
        setLoadError('');
        setRetryKey((key) => key + 1);
      }}
      onCreateActivity={recordActivity}
      isPreview={view === 'settings'}
    />
  );
}
