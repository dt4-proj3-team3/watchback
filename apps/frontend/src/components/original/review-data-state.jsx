import { toReactStyle } from './style';

export function ReviewDataState({ state, message, onRetry }) {
  const loading = state === 'loading';
  const notFound = state === 'not_found';
  return (
    <main style={toReactStyle('max-width:960px;margin:0 auto;padding:96px 32px;text-align:center')} aria-live="polite">
      <div style={toReactStyle('background:#FFFFFF;border:1px solid #E4E6E1;border-radius:12px;padding:56px 24px')}>
        <div style={toReactStyle('font-size:15px;font-weight:600;margin-bottom:8px')}>
          {loading ? '재검토 데이터를 불러오는 중입니다' : notFound ? '재검토 Case를 찾을 수 없습니다' : '재검토 데이터를 불러오지 못했습니다'}
        </div>
        {!loading && (
          <>
            <div style={toReactStyle('font-size:13px;color:#5B6058;line-height:1.6;margin-bottom:18px')}>
              {message || '잠시 후 다시 시도해 주세요.'}
            </div>
            {!notFound && (
              <button type="button" onClick={onRetry} style={toReactStyle('font-size:12.5px;font-weight:600;font-family:inherit;color:#FFFFFF;background:#2F8F5B;border:none;border-radius:7px;padding:8px 14px;cursor:pointer')}>
                다시 시도
              </button>
            )}
          </>
        )}
      </div>
    </main>
  );
}
