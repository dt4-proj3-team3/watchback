param(
    [string]$WorkspaceId = "ee9ff4be-4a01-40cd-b194-a92e69b0171a"
)

$ErrorActionPreference = "Stop"

$ApiBase = "https://api.fabric.microsoft.com/v1"

# ------------------------------------------------------------
# 1. 로컬 Notebook ↔ Fabric Item ID 매핑
# ------------------------------------------------------------

$Notebooks = @(
    # Silver
    @{
        Name = "00_silver_common"
        Path = "fabric/workspace/transformation/silver/00_silver_common.ipynb"
        ItemId = "cef271e7-3d55-4224-857f-3913e44b93b9"
    },
    @{
        Name = "01_validate_ghsa"
        Path = "fabric/workspace/transformation/silver/01_validate_ghsa.ipynb"
        ItemId = "7f26548f-5fdd-4841-8998-d3d37c983333"
    },
    @{
        Name = "02_normalize_ghsa"
        Path = "fabric/workspace/transformation/silver/02_normalize_ghsa.ipynb"
        ItemId = "9809b288-8d47-4bd9-aa0f-9c3b0ad66bde"
    },
    @{
        Name = "03_build_advisory_ghsa"
        Path = "fabric/workspace/transformation/silver/03_build_advisory_ghsa.ipynb"
        ItemId = "4dcff49e-47db-4900-8e0c-4a4b425c572d"
    },
    @{
        Name = "04_build_vuln_alias"
        Path = "fabric/workspace/transformation/silver/04_build_vuln_alias.ipynb"
        ItemId = "a25f3a87-6ab6-4fa3-a932-0a950a954485"
    },
    @{
        Name = "05_build_affected_range"
        Path = "fabric/workspace/transformation/silver/05_build_affected_range.ipynb"
        ItemId = "6f0e733c-6faf-491d-8aee-f9d72050879c"
    },
    @{
        Name = "06_build_package"
        Path = "fabric/workspace/transformation/silver/06_build_package.ipynb"
        ItemId = "870cfb7d-6160-4b73-89ab-ed96636e597c"
    },
    @{
        Name = "07_build_active_cve_set"
        Path = "fabric/workspace/transformation/silver/07_build_active_cve_set.ipynb"
        ItemId = "da09426e-1939-48fc-b80c-ccf435b6ab1f"
    },
    @{
        Name = "08_validate_epss"
        Path = "fabric/workspace/transformation/silver/08_validate_epss.ipynb"
        ItemId = "e2ada858-15a9-4e21-a6f2-0dfd8a353829"
    },
    @{
        Name = "09_build_silver_epss"
        Path = "fabric/workspace/transformation/silver/09_build_silver_epss.ipynb"
        ItemId = "e1e0578a-1e34-4a9d-9136-939f86e252e8"
    },
    @{
        Name = "10_build_epss_distribution"
        Path = "fabric/workspace/transformation/silver/10_build_epss_distribution.ipynb"
        ItemId = "0e2f9df6-0e58-435f-ab3b-bbe5088a80f3"
    },
    @{
        Name = "11_validate_kev"
        Path = "fabric/workspace/transformation/silver/11_validate_kev.ipynb"
        ItemId = "e300c8eb-3b7c-4e68-acb1-284b677dea8b"
    },
    @{
        Name = "12_build_silver_kev"
        Path = "fabric/workspace/transformation/silver/12_build_silver_kev.ipynb"
        ItemId = "667e7957-34fc-4687-bd51-bab20e9de6ee"
    },
    @{
        Name = "13_reconcile_silver"
        Path = "fabric/workspace/transformation/silver/13_reconcile_silver.ipynb"
        ItemId = "2359df02-6e7e-4323-ba0b-719ce9a20db7"
    },

    # Gold
    @{
        Name = "00_gold_common"
        Path = "fabric/workspace/transformation/gold/00_gold_common.ipynb"
        ItemId = "52c35394-eb9a-4a32-b704-6d96b59885d7"
    },
    @{
        Name = "01_gold_vuln_package_build"
        Path = "fabric/workspace/transformation/gold/01_gold_vuln_package_build.ipynb"
        ItemId = "ad56cb2b-7f92-4b7c-b693-f55c921ebf7a"
    },
    @{
        Name = "02_gold_vuln_daily_build"
        Path = "fabric/workspace/transformation/gold/02_gold_vuln_daily_build.ipynb"
        ItemId = "1b2f61ea-0c02-4fca-9e79-2e2246af9e31"
    },
    @{
        Name = "03_gold_circuit_breaker_check"
        Path = "fabric/workspace/transformation/gold/03_gold_circuit_breaker_check.ipynb"
        ItemId = "bb0d9f8b-0ce0-4d49-863b-190a080c5528"
    },
    @{
        Name = "04_publish_vulnerability_package_build"
        Path = "fabric/workspace/transformation/gold/04_publish_vulnerability_package_build.ipynb"
        ItemId = "d7b51aeb-69c4-4c97-a812-490870b50498"
    },
    @{
        Name = "05_publish_risk_current_build"
        Path = "fabric/workspace/transformation/gold/05_publish_risk_current_build.ipynb"
        ItemId = "827a60f1-ea2e-4b06-8508-bb4aee12c59d"
    },
    @{
        Name = "06_publish_epss_trend_build"
        Path = "fabric/workspace/transformation/gold/06_publish_epss_trend_build.ipynb"
        ItemId = "3df2a0a4-4d29-4a63-a2c8-5f56edc702aa"
    },
    @{
        Name = "07_publish_risk_events_build"
        Path = "fabric/workspace/transformation/gold/07_publish_risk_events_build.ipynb"
        ItemId = "af8a92c1-f58a-43df-a2bb-399f6e119c76"
    }
)

# ------------------------------------------------------------
# 2. Fabric access token
# ------------------------------------------------------------

Write-Host ""
Write-Host "Getting Fabric access token..."

$Token = az account get-access-token `
    --resource https://api.fabric.microsoft.com `
    --query accessToken `
    --output tsv

if (-not $Token) {
    throw "Fabric access token을 가져오지 못했습니다. az login 상태를 확인하세요."
}

$Headers = @{
    Authorization = "Bearer $Token"
    "Content-Type" = "application/json"
}

# ------------------------------------------------------------
# 3. LRO 완료 대기
# ------------------------------------------------------------

function Wait-FabricOperation {
    param(
        [Parameter(Mandatory)]
        [string]$OperationId
    )

    while ($true) {

        Start-Sleep -Seconds 5

        $OperationUrl = "$ApiBase/operations/$OperationId"

        $Result = Invoke-RestMethod `
            -Method Get `
            -Uri $OperationUrl `
            -Headers @{ Authorization = "Bearer $Token" }

        if ($Result.status -eq "Succeeded") {
            return
        }

        if ($Result.status -eq "Failed") {
            throw "Fabric operation failed: $($Result | ConvertTo-Json -Depth 10)"
        }

        Write-Host "    status: $($Result.status)"
    }
}

# ------------------------------------------------------------
# 4. Notebook 배포
# ------------------------------------------------------------

$Success = @()
$Failed = @()

foreach ($Notebook in $Notebooks) {

    Write-Host ""
    Write-Host "================================================="
    Write-Host "Deploying: $($Notebook.Name)"
    Write-Host "================================================="

    try {

        if (-not (Test-Path $Notebook.Path)) {
            throw "Local file not found: $($Notebook.Path)"
        }

        # ipynb → Base64
        $Bytes = [System.IO.File]::ReadAllBytes($Notebook.Path)
        $Base64 = [Convert]::ToBase64String($Bytes)

        $Payload = @{
            definition = @{
                format = "ipynb"
                parts = @(
                    @{
                        path = "notebook-content.ipynb"
                        payload = $Base64
                        payloadType = "InlineBase64"
                    }
                )
            }
        } | ConvertTo-Json -Depth 10

        $Url = "$ApiBase/workspaces/$WorkspaceId/notebooks/$($Notebook.ItemId)/updateDefinition"

        $Response = Invoke-WebRequest `
            -Method Post `
            -Uri $Url `
            -Headers $Headers `
            -Body $Payload `
           
        if ($Response.StatusCode -eq 200) {

            Write-Host "SUCCESS: $($Notebook.Name) (200)"
            $Success += $Notebook.Name
            continue
        }

        if ($Response.StatusCode -ne 202) {
            throw "Unexpected HTTP status: $($Response.StatusCode) $($Response.Content)"
        }

        $OperationId = $Response.Headers["x-ms-operation-id"]

        if (-not $OperationId) {
            throw "202 응답에서 x-ms-operation-id를 찾지 못했습니다."
        }

        Write-Host "Operation: $OperationId"

        Wait-FabricOperation -OperationId $OperationId

        Write-Host "SUCCESS: $($Notebook.Name)"

        $Success += $Notebook.Name
    }
    catch {

        Write-Host "FAILED: $($Notebook.Name)"
        Write-Host $_

        $Failed += $Notebook.Name
    }
}

# ------------------------------------------------------------
# 5. 결과 요약
# ------------------------------------------------------------

Write-Host ""
Write-Host "================================================="
Write-Host "DEPLOYMENT SUMMARY"
Write-Host "================================================="

Write-Host ""
Write-Host "Succeeded: $($Success.Count)"

foreach ($Name in $Success) {
    Write-Host "  [OK] $Name"
}

Write-Host ""
Write-Host "Failed: $($Failed.Count)"

foreach ($Name in $Failed) {
    Write-Host "  [FAIL] $Name"
}

Write-Host ""

if ($Failed.Count -gt 0) {
    exit 1
}

exit 0