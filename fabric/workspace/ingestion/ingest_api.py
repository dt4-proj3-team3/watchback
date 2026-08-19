import time
from urllib import response
import requests
import random

def _calculate_backoff(attempt, backoff_factor):
    '''
    지수적 증가 + Jitter를 적용한 재시도 대기 시간 계산하는 함수
    '''
    base_wait = backoff_factor * (2 ** attempt)
    jitter = random.uniform(0, 1)
    return base_wait + jitter

def _handle_github_rate_limit(response, attempt, backoff_factor, secondary_wait=60.0):
    '''
    GitHub API의 Rate Limit을 처리하는 함수
    '''
    # Retry-After 헤더가 있으면 해당 시간만큼 대기 후 재시도
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        return float(retry_after)

    # GitHub Rate Limit 헤더를 확인하여 남은 요청 수가 0이면 reset 시간까지 대기
    remaining = response.headers.get("x-ratelimit-remaining")
    reset = response.headers.get("x-ratelimit-reset")
    if remaining == "0" and reset:
        wait_seconds = max(float(reset) - time.time(), 0)
        print(f"remaining={remaining}, reset={reset}")    
        return wait_seconds

    # Retry-After와 reset 정보가 없으면 Secondary Rate Limit으로 보고 최소 60초부터 지수적으로 대기
    return _calculate_backoff(attempt, secondary_wait)
    
def request_with_retry(
    method,
    url,
    *,
    headers=None,
    params=None,
    json=None,

    # 요청 타임아웃 설정 (초 단위)
    timeout=5,

    # 최대 재시도 횟수는 3회로 설정 (최초요청 1회 미포함)
    max_retries=3,

    # 재시도 간격을 지수적으로 증가시키기 위한 backoff factor
    backoff_factor=1.0,
    source=None
):
    '''
    HTTP 요청을 보내고, 실패 시 재시도하는 함수
    '''
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json,
                timeout=timeout,
            )

            print(
                f"attempt={attempt + 1}, "
                f"status={response.status_code}"
            )

            # 성공
            if 200 <= response.status_code < 300:
                return response

            # 공통 오류 증 재시도 하지 않음: 400, 404 는 요청 오류 또는 리소스 문제로 보고 재시도하지 않고 즉시 예외 발생
            elif response.status_code in (400, 404):
                response.raise_for_status()

            # GHSA 오류: 403는 Primary/Secondary Rate Limit인지 판별하고, 그 외 권한 오류는 재시도하지 않음
            elif source == "ghsa" and response.status_code == 403:
                remaining = response.headers.get("x-ratelimit-remaining")
                message = response.json().get("message", "").lower()

                if remaining == "0":
                    wait_seconds = _handle_github_rate_limit( response, attempt, backoff_factor)
                    retry_reason = "GitHub Primary Rate Limit"

                elif "secondary rate limit" in message:
                    wait_seconds = _handle_github_rate_limit( response, attempt, backoff_factor)
                    retry_reason = "GitHub Secondary Rate Limit"
    
                else:
                    # 그 외 권한 오류
                    response.raise_for_status()

            # GHSA 오류: 429는 과부한 요청으로 인해 서버가 요청을 처리할 수 없음을 나타내므로 GitHub Rate Limit 처리    
            elif source == "ghsa" and response.status_code == 429:
                wait_seconds = _handle_github_rate_limit(response,attempt,backoff_factor)
                retry_reason = "GitHub Rate Limit"

            # 공통 오류 중 재시도 : 429 는 과부한 요청으로 인해 서버가 요청을 처리할 수 없음을 나타내므로 retry_after 헤더를 확인하여 재시도 간격을 설정
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")

                # retry_after 헤더가 있으면 해당 시간만큼 대기 후 재시도
                if retry_after:
                    wait_seconds = float(retry_after)
                    retry_reason = "429 Too Many Requests - Retry-After"

                # retry_after 헤더가 없으면 backoff_factor 기반으로 지수적 증가 + jitter 적용
                else:
                    wait_seconds = _calculate_backoff(attempt, backoff_factor)
                    retry_reason = "429 Too Many Requests - Backoff + Jitter"

            # 공통 오류 중 재시도 : 5xx 는 서버측 오류이므로 재시도
            elif 500 <= response.status_code < 600:
                retry_reason = f"{response.status_code} Server Error"
                wait_seconds = _calculate_backoff(attempt, backoff_factor)

            # 그 외 상태코드는 기본적으로 즉시 실패
            else:
                response.raise_for_status()

        # Timeout, ConnectionError 발생 시 재시도
        except (requests.Timeout, requests.ConnectionError) as e:
            retry_reason = f"{type(e).__name__}: {e}"
            wait_seconds = _calculate_backoff(attempt, backoff_factor)

        # 최대 retry 초과
        if attempt == max_retries:
            raise RuntimeError(
                f"Maximum retry count exceeded: {url}"
            )

        print(f"{wait_seconds:.1f}초 후 재시도")
        print(
            f"[RETRY] reason={retry_reason}, "
            f"[RETRY] attempt={attempt + 1}/{max_retries + 1}, "
            f"wait={wait_seconds:.1f}s"
        )
        time.sleep(wait_seconds)

