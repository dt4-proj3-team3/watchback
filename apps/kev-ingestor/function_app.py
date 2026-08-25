# ============================================================
# Azure Function: KEV 변경 감지 → Fabric Bronze 적재 (10분마다 실행)
# ------------------------------------------------------------
# 동작 순서 (KEV_Function_구현_스펙.md 4절):
# 1. GitHub Commits API로 known_exploited_vulnerabilities.json의 최신 커밋 SHA 조회
# 2. pending_removed 중 24시간 경과한 항목을 REMOVED 확정 처리 (새 커밋 유무와 무관하게 항상 실행)
# 3. 새 커밋이 없으면 -> 여기서 종료 (전체 다운로드 안 함)
# 4. 새 커밋이 있으면 -> cisagov/kev-data의 해당 커밋 raw JSON을 받아
#    cveID를 키로 이전 상태와 구조적으로 비교 -> added/updated/removed_candidates 계산
# 5. removed_candidates는 즉시 확정하지 않고 pending_removed에 등록 (debounce)
# 6. ADDED/UPDATED(+ 2단계에서 확정된 REMOVED)를 Bronze에 적재
# 7. Bronze 적재가 전부 성공한 뒤에만 checkpoint(last_processed_commit_sha)를 갱신
#
# Azure Function은 실행마다 메모리가 초기화되기 때문에,
# "이전 상태"는 함수 밖(Blob Storage)에 저장해야 합니다.
# ============================================================

import azure.functions as func
import requests
import json
import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from azure.identity import DefaultAzureCredential

app = func.FunctionApp()

# ---- 환경 변수로 관리할 값들 (Function App 설정에서 등록) ----
# GITHUB_TOKEN: GitHub PAT (없어도 동작하지만, 시간당 60회 제한 -> 있으면 5000회로 늘어남)
# STORAGE_CONNECTION_STRING: 상태 저장용 Storage 계정 연결 문자열 (Function 기본 스토리지 재사용 가능)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
STORAGE_CONNECTION_STRING = os.environ["STORAGE_CONNECTION_STRING"]

STATE_CONTAINER = "kev-state"       # 상태 파일을 저장할 Blob 컨테이너 이름
STATE_BLOB_NAME = "kev_state.json"  # 상태 파일 이름

GITHUB_KEV_PATH = "known_exploited_vulnerabilities.json"
GITHUB_COMMITS_URL = "https://api.github.com/repos/cisagov/kev-data/commits"
GITHUB_RAW_URL_TEMPLATE = "https://raw.githubusercontent.com/cisagov/kev-data/{sha}/" + GITHUB_KEV_PATH

REMOVED_DEBOUNCE_HOURS = 24

# ---- Fabric OneLake (Bronze) 대상 경로 ----
ONELAKE_ENDPOINT = "https://onelake.dfs.fabric.microsoft.com"
FABRIC_WORKSPACE_ID = "ee9ff4be-4a01-40cd-b194-a92e69b0171a"
FABRIC_LAKEHOUSE_ID = "d9fd84b1-706e-4ff8-929f-bfa9ab033e56"
BRONZE_DIR_PATH = f"{FABRIC_LAKEHOUSE_ID}/Files/bronze/kev"


def load_state() -> dict:
    """
    Blob Storage에서 이전 상태를 읽어옵니다.
    처음 실행이라 파일이 없으면 빈 상태로 시작합니다.
    """
    blob_service = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    container_client = blob_service.get_container_client(STATE_CONTAINER)

    try:
        container_client.create_container()
    except Exception:
        pass  # 이미 컨테이너가 있으면 에러가 나는데, 무시해도 됨

    blob_client = container_client.get_blob_client(STATE_BLOB_NAME)

    try:
        content = blob_client.download_blob().readall()
        return json.loads(content)
    except Exception:
        logging.info("[상태] 저장된 상태 파일이 없어 최초 실행으로 간주합니다.")
        return {
            "last_processed_commit_sha": None,
            "last_processed_at": None,
            "last_catalog_version": None,
            "items": {},
            "pending_removed": {},
        }


def save_state(state: dict) -> None:
    """다음 실행을 위해 이번 상태를 Blob에 저장합니다."""
    blob_service = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    blob_client = blob_service.get_blob_client(container=STATE_CONTAINER, blob=STATE_BLOB_NAME)

    blob_client.upload_blob(json.dumps(state, ensure_ascii=False), overwrite=True)
    logging.info(
        f"[상태 저장] items {len(state['items'])}건, pending_removed {len(state['pending_removed'])}건, "
        f"sha={state['last_processed_commit_sha']}"
    )


def get_latest_commit_sha() -> str:
    """GitHub Commits API로 KEV JSON 파일의 최신 커밋 SHA를 조회합니다."""
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    params = {"path": GITHUB_KEV_PATH, "per_page": 1}
    resp = requests.get(GITHUB_COMMITS_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()

    commits = resp.json()
    if not commits:
        raise RuntimeError("[GitHub] 커밋 이력이 비어 있습니다.")
    return commits[0]["sha"]


def fetch_kev_catalog(sha: str) -> dict:
    """cisagov/kev-data의 특정 커밋 시점 KEV JSON 전체를 raw.githubusercontent.com에서 받아옵니다."""
    resp = requests.get(GITHUB_RAW_URL_TEMPLATE.format(sha=sha), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _normalize_for_hash(value):
    """리스트 필드의 순서 차이로 인한 hash 오탐을 막기 위해 리스트를 정렬합니다."""
    if isinstance(value, dict):
        return {k: _normalize_for_hash(v) for k, v in value.items()}
    if isinstance(value, list):
        normalized = [_normalize_for_hash(v) for v in value]
        return sorted(normalized, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return value


def compute_hash(item: dict) -> str:
    """cveID를 제외한 모든 필드를 정렬 직렬화한 뒤 SHA-256 hash를 계산합니다."""
    fields = {k: v for k, v in item.items() if k != "cveID"}
    normalized = _normalize_for_hash(fields)
    serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def diff_items(current_hashes: dict, previous_items: dict) -> tuple:
    """cveID를 키로 현재/이전 상태를 비교해 added / removed_candidates / updated 집합을 계산합니다."""
    current_ids = set(current_hashes.keys())
    previous_ids = set(previous_items.keys())

    added = current_ids - previous_ids
    removed_candidates = previous_ids - current_ids
    possibly_updated = current_ids & previous_ids
    updated = {
        cve_id for cve_id in possibly_updated
        if current_hashes[cve_id] != previous_items[cve_id]["hash"]
    }
    return added, removed_candidates, updated


def reconcile_pending_removed(state: dict, current_hashes: dict, updated: set) -> set:
    """pending_removed 중 이번 스냅샷에 재등재된 cveID를 복구하고, hash가 달라졌으면 updated에 병합합니다."""
    reappeared = set()
    for cve_id in list(state["pending_removed"].keys()):
        if cve_id not in current_hashes:
            continue
        state["pending_removed"].pop(cve_id)
        reappeared.add(cve_id)
        previous_hash = state["items"].get(cve_id, {}).get("hash")
        if previous_hash != current_hashes[cve_id]:
            updated.add(cve_id)
    return reappeared


def register_removed_candidates(state: dict, removed_candidates: set, now: datetime) -> None:
    """새로 사라진 cveID를 즉시 확정하지 않고 pending_removed에 등록합니다(debounce 시작)."""
    now_iso = now.isoformat()
    for cve_id in removed_candidates:
        if cve_id in state["pending_removed"]:
            continue
        state["pending_removed"][cve_id] = {
            "removed_detected_at": now_iso,
            "last_known_item": state["items"][cve_id]["item"],
        }


def confirm_expired_removals(state: dict, now: datetime, debounce_hours: int = REMOVED_DEBOUNCE_HOURS) -> list:
    """pending_removed 중 debounce 기간이 지난 항목을 kev_removed_confirmed 이벤트로 확정합니다."""
    confirmed_events = []
    threshold = timedelta(hours=debounce_hours)

    for cve_id in list(state["pending_removed"].keys()):
        entry = state["pending_removed"][cve_id]
        removed_at = datetime.fromisoformat(entry["removed_detected_at"])
        if now - removed_at < threshold:
            continue

        confirmed_events.append({
            "event_type": "kev_removed_confirmed",
            "cve_id": cve_id,
            # 이 확정은 새 커밋 없는 실행에서도 일어날 수 있어(4절) 이번 실행엔 최신 catalogVersion이 없음 ->
            # 직전에 실제로 fetch했을 때 저장해둔 last_catalog_version을 대신 사용
            "catalog_version": state.get("last_catalog_version"),
            "detected_at": now.isoformat(),
            "source_commit_sha": state.get("last_processed_commit_sha"),
            "data": entry["last_known_item"],
        })
        state["items"].pop(cve_id, None)
        state["pending_removed"].pop(cve_id, None)

    return confirmed_events


def build_events(event_type: str, cve_ids: set, items_by_id: dict, catalog_version, source_commit_sha: str, now: datetime) -> list:
    """ADDED/UPDATED 이벤트를 5절 payload 스키마로 조립합니다."""
    now_iso = now.isoformat()
    return [
        {
            "event_type": event_type,
            "cve_id": cve_id,
            "catalog_version": catalog_version,
            "detected_at": now_iso,
            "source_commit_sha": source_commit_sha,
            "data": items_by_id[cve_id],
        }
        for cve_id in cve_ids
    ]


def _bronze_filename(commit_sha: str, run_at: str) -> str:
    safe_run_at = run_at.replace(":", "-")
    return f"{safe_run_at}_{commit_sha[:7]}.json"


def write_to_bronze(events: list, commit_sha: str, run_at: str) -> None:
    """
    OneLake Files/bronze/kev 밑에 이번 실행의 이벤트를 파일 하나로 씁니다.
    실패 시 예외를 그대로 전파합니다(4절 체크포인트 갱신 조건에서 사용).
    """
    service_client = DataLakeServiceClient(account_url=ONELAKE_ENDPOINT, credential=DefaultAzureCredential())
    file_client = (
        service_client.get_file_system_client(FABRIC_WORKSPACE_ID)
        .get_directory_client(BRONZE_DIR_PATH)
        .get_file_client(_bronze_filename(commit_sha, run_at))
    )
    content = json.dumps(events, ensure_ascii=False).encode("utf-8")
    file_client.upload_data(content, overwrite=True)
    logging.info(f"[Bronze 적재 완료] {len(events)}건 -> {BRONZE_DIR_PATH}/{_bronze_filename(commit_sha, run_at)}")


def write_heartbeat(
    now: datetime,
    had_new_commit: bool,
    status: str,
    total_fetched: int = None,
    total_processed: int = None,
    skipped_missing_cve_id: int = None,
) -> None:
    """
    Files/bronze/kev/_heartbeat.json을 실행마다(성공/실패, 변화 유무와 무관하게) 덮어씁니다.
    "KEV에 변화가 없어 조용한 것"과 "Function이 죽어서 조용한 것"을 구분하기 위한 용도이므로,
    heartbeat 기록 자체가 실패해도 메인 로직(checkpoint 갱신 여부)에 영향을 주면 안 됩니다.

    total_fetched/total_processed/skipped_missing_cve_id는 fetch_kev_catalog를 실제로 호출한
    실행에서만 값이 있고, 새 커밋이 없어 fetch를 건너뛴 실행에서는 None으로 둡니다.
    """
    try:
        service_client = DataLakeServiceClient(account_url=ONELAKE_ENDPOINT, credential=DefaultAzureCredential())
        file_client = (
            service_client.get_file_system_client(FABRIC_WORKSPACE_ID)
            .get_directory_client(BRONZE_DIR_PATH)
            .get_file_client("_heartbeat.json")
        )
        payload = {"last_run_at": now.isoformat(), "had_new_commit": had_new_commit, "status": status}
        if total_fetched is not None:
            payload["total_fetched"] = total_fetched
        if total_processed is not None:
            payload["total_processed"] = total_processed
        if skipped_missing_cve_id is not None:
            payload["skipped_missing_cve_id"] = skipped_missing_cve_id
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        file_client.upload_data(content, overwrite=True)
        logging.info(f"[Heartbeat] had_new_commit={had_new_commit} status={status}")
    except Exception as e:
        logging.error(f"[에러] Heartbeat 기록 실패: {e}")


def run_poll_cycle(now: datetime) -> None:
    """kev_poll의 실제 로직. now를 인자로 받아 테스트에서 시간을 주입할 수 있게 분리."""
    logging.info(f"[실행 시작] {now.isoformat()}")

    # load_state/save_state 등에서 예기치 못한 예외가 나도(4개 명시 경로 밖) heartbeat는 남겨야
    # "조용한 무변화"와 "Function이 죽은 것"을 구분할 수 있음 -> 아래 except가 최후의 안전망 역할.
    had_new_commit = False
    try:
        state = load_state()

        try:
            latest_sha = get_latest_commit_sha()
        except requests.exceptions.RequestException as e:
            logging.error(f"[에러] GitHub 커밋 조회 실패: {e}")
            write_heartbeat(now, had_new_commit=False, status="error")
            return  # 이번 실행은 건너뛰고, state도 갱신하지 않음

        had_new_commit = latest_sha != state.get("last_processed_commit_sha")

        # pending_removed 만료분 확정 처리 (새 커밋 유무와 무관하게 항상 실행)
        confirmed_events = confirm_expired_removals(state, now)

        if not had_new_commit:
            if confirmed_events:
                try:
                    write_to_bronze(confirmed_events, commit_sha=latest_sha, run_at=now.isoformat())
                except Exception as e:
                    logging.error(f"[에러] Bronze 적재 실패(만료 REMOVED): {e}")
                    write_heartbeat(now, had_new_commit=False, status="error")
                    return  # 저장하지 않고 다음 실행에서 재시도
            save_state(state)
            logging.info("[결과] 새 커밋 없음. 만료된 REMOVED만 처리 후 종료.")
            write_heartbeat(now, had_new_commit=False, status="ok")
            return

        try:
            snapshot = fetch_kev_catalog(latest_sha)
        except requests.exceptions.RequestException as e:
            logging.error(f"[에러] KEV 카탈로그 다운로드 실패: {e}")
            write_heartbeat(now, had_new_commit=False, status="error")
            return

        catalog_version = snapshot.get("catalogVersion")
        vulnerabilities = snapshot.get("vulnerabilities", [])

        items_by_id = {}
        skipped_missing_cve_id = 0
        for v in vulnerabilities:
            if "cveID" not in v:
                skipped_missing_cve_id += 1
                continue
            items_by_id[v["cveID"]] = v
        if skipped_missing_cve_id:
            logging.warning(f"[데이터 이상] cveID 없는 항목 {skipped_missing_cve_id}건 스킵")

        total_fetched = len(vulnerabilities)
        total_processed = len(items_by_id)
        logging.info(
            f"[건수 확인] fetched={total_fetched} processed={total_processed} skipped={skipped_missing_cve_id}"
        )

        current_hashes = {cve_id: compute_hash(item) for cve_id, item in items_by_id.items()}

        added, removed_candidates, updated = diff_items(current_hashes, state["items"])
        reconcile_pending_removed(state, current_hashes, updated)
        register_removed_candidates(state, removed_candidates, now)

        events = confirmed_events
        events += build_events("kev_added", added, items_by_id, catalog_version, latest_sha, now)
        events += build_events("kev_updated", updated, items_by_id, catalog_version, latest_sha, now)

        if events:
            try:
                write_to_bronze(events, commit_sha=latest_sha, run_at=now.isoformat())
            except Exception as e:
                logging.error(f"[에러] Bronze 적재 실패: {e}")
                write_heartbeat(
                    now, had_new_commit=True, status="error",
                    total_fetched=total_fetched, total_processed=total_processed,
                    skipped_missing_cve_id=skipped_missing_cve_id,
                )
                return  # 저장하지 않고 다음 실행에서 같은 커밋을 재처리

        for cve_id in added | updated:
            state["items"][cve_id] = {"hash": current_hashes[cve_id], "item": items_by_id[cve_id]}

        state["last_processed_commit_sha"] = latest_sha
        state["last_processed_at"] = now.isoformat()
        state["last_catalog_version"] = catalog_version
        save_state(state)
        write_heartbeat(
            now, had_new_commit=True, status="ok",
            total_fetched=total_fetched, total_processed=total_processed,
            skipped_missing_cve_id=skipped_missing_cve_id,
        )

        logging.info(
            f"[실행 종료] added={len(added)} updated={len(updated)} removed_confirmed={len(confirmed_events)}"
        )
    except Exception as e:
        # load_state/save_state/diff 등 위에서 개별적으로 처리하지 않은 예기치 못한 예외.
        # heartbeat만 남기고 예외는 그대로 다시 던져 Azure Function 자체의 실패 처리(재시도/알림)가 동작하게 함.
        logging.error(f"[에러] 예기치 못한 오류로 실행 중단: {e}")
        write_heartbeat(now, had_new_commit=had_new_commit, status="error")
        raise


@app.timer_trigger(schedule="0 */10 * * * *", arg_name="mytimer", run_on_startup=False)
def kev_poll(mytimer: func.TimerRequest) -> None:
    """10분마다 실행되는 timer trigger. cron "0 */10 * * * *" = 매 10분마다."""
    run_poll_cycle(datetime.now(timezone.utc))


# monitor_app.py는 heartbeat 감시용 Blueprint(bp)만 정의합니다. Azure Functions Python v2는
# entry point의 FunctionApp 인스턴스만 자동 인식하므로, 여기서 등록해야 kev_heartbeat_monitor가
# 실제로 배포/실행됩니다.
from monitor_app import bp  # noqa: E402
app.register_functions(bp)
