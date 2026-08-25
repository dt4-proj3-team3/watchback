# ============================================================
# Azure Function: KEV heartbeat 모니터링 → Teams 알림 (1시간마다 실행)
# ------------------------------------------------------------
# kev_poll(function_app.py)이 매 실행마다 남기는 Files/bronze/kev/_heartbeat.json을
# 읽어 이상 징후가 있으면 Teams Workflows 웹훅으로 알림을 보냅니다.
#
# Azure Functions Python v2는 entry point(function_app.py)의 FunctionApp 인스턴스만
# 자동으로 인식하므로, 이 파일은 자체 FunctionApp을 만들지 않고 Blueprint로 함수를 정의합니다.
# function_app.py가 이 bp를 import해서 app.register_functions(bp)로 등록합니다
# (function_app.py -> monitor_app.py 단방향 참조만 존재 — 순환 임포트 없음).
# ============================================================

import json
import logging
import os
from datetime import datetime, timezone

import azure.functions as func
import requests
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient

bp = func.Blueprint()

ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")
STALE_THRESHOLD_MINUTES = int(os.environ.get("STALE_THRESHOLD_MINUTES", "30"))

# ---- Fabric OneLake (Bronze) 대상 경로 (function_app.py와 동일한 위치) ----
ONELAKE_ENDPOINT = "https://onelake.dfs.fabric.microsoft.com"
FABRIC_WORKSPACE_ID = "ee9ff4be-4a01-40cd-b194-a92e69b0171a"
FABRIC_LAKEHOUSE_ID = "d9fd84b1-706e-4ff8-929f-bfa9ab033e56"
BRONZE_DIR_PATH = f"{FABRIC_LAKEHOUSE_ID}/Files/bronze/kev"


def read_heartbeat() -> dict:
    """Files/bronze/kev/_heartbeat.json을 읽어옵니다. write_heartbeat와 동일한 DataLakeServiceClient 방식."""
    service_client = DataLakeServiceClient(account_url=ONELAKE_ENDPOINT, credential=DefaultAzureCredential())
    file_client = (
        service_client.get_file_system_client(FABRIC_WORKSPACE_ID)
        .get_directory_client(BRONZE_DIR_PATH)
        .get_file_client("_heartbeat.json")
    )
    content = file_client.download_file().readall()
    return json.loads(content)


def send_alert(message: str) -> None:
    """
    Teams Workflows 웹훅(ALERT_WEBHOOK_URL)으로 알림을 보냅니다.
    채널 미설정/전송 실패 모두 예외를 던지지 않고 로그만 남깁니다.
    """
    if not ALERT_WEBHOOK_URL:
        logging.warning(f"[알림 미발송 - 채널 미설정] {message}")
        return
    try:
        requests.post(ALERT_WEBHOOK_URL, json={"text": message}, timeout=30)
    except Exception as e:
        logging.error(f"[에러] Teams 웹훅 전송 실패: {e}")


def check_heartbeat(now: datetime) -> None:
    """kev_heartbeat_monitor의 실제 로직. now를 인자로 받아 테스트에서 시간을 주입할 수 있게 분리."""
    try:
        heartbeat = read_heartbeat()
    except Exception as e:
        logging.error(f"[에러] heartbeat 파일 읽기 실패: {e}")
        send_alert(f"[KEV 모니터링] heartbeat 파일 자체를 읽을 수 없음: {e}")
        return

    reasons = []

    last_run_at = heartbeat.get("last_run_at")
    if last_run_at is not None:
        age_minutes = (now - datetime.fromisoformat(last_run_at)).total_seconds() / 60
        if age_minutes > STALE_THRESHOLD_MINUTES:
            reasons.append(f"Function이 멈춘 것으로 의심됨 (last_run_at={last_run_at}, {age_minutes:.0f}분 경과)")

    if heartbeat.get("status") == "error":
        reasons.append("Function 실행 중 에러 발생")

    skipped = heartbeat.get("skipped_missing_cve_id")
    if skipped is not None and skipped > 0:
        reasons.append(f"cveID 없는 항목 발견 (skipped_missing_cve_id={skipped})")

    total_fetched = heartbeat.get("total_fetched")
    total_processed = heartbeat.get("total_processed")
    if total_fetched is not None and total_processed is not None and total_fetched != total_processed:
        reasons.append(f"건수 불일치 (total_fetched={total_fetched}, total_processed={total_processed})")

    if reasons:
        send_alert("[KEV 모니터링]\n" + "\n".join(reasons))
    else:
        logging.info("[모니터링] heartbeat 정상.")


@bp.timer_trigger(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False)
def kev_heartbeat_monitor(mytimer: func.TimerRequest) -> None:
    """1시간마다 실행되는 timer trigger. cron "0 0 * * * *" = 매시 정각."""
    check_heartbeat(datetime.now(timezone.utc))
