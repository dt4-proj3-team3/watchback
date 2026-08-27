'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';

import { WatchbackApp } from '@/components/original/watchback-app';
import {
  loadReviewCase,
  loadReviewCases,
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
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!usesCaseData) return;

    let cancelled = false;

    const request = view === 'detail' && selectedId
      ? loadReviewCase(dataSource, selectedId).then((detail) => [detail])
      : loadReviewCases(dataSource);

    request
      .then((nextCases) => {
        if (cancelled) return;
        setCases(nextCases);
        setLoadState('ready');
      })
      .catch((error) => {
        if (cancelled) return;
        setCases([]);
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

  return (
    <WatchbackApp
      initialView={view}
      initialSelectedId={selectedId}
      initialCases={cases}
      dataSource={dataSource}
      onDataSourceChange={changeDataSource}
      loadState={usesCaseData ? loadState : 'ready'}
      loadError={loadError}
      onRetry={() => {
        setLoadState('loading');
        setLoadError('');
        setRetryKey((key) => key + 1);
      }}
      isPreview={view === 'settings'}
    />
  );
}
