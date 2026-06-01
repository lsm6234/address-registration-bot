# 빗썸 주소등록봇

CSV/엑셀 주소 목록을 읽어서 빗썸 주소록 등록 화면을 자동 입력하는 로컬 운영자 도구입니다.

## 안전 원칙

- 출금 실행은 하지 않습니다.
- CAPTCHA/MFA/SMS/이메일/OTP가 나오면 우회하지 않고 `needs_manual`로 멈춥니다.
- 비밀번호, OTP, 세션 쿠키를 프로젝트 파일에 저장하지 않습니다.
- `run --confirm-register` 없이는 최종 `주소 등록` 클릭을 하지 않습니다.
- 네트워크/메모/태그를 추측하지 않습니다.
- 기존 주소 삭제/수정은 하지 않습니다.

## 입력 파일

필수 컬럼:

```csv
exchange,coin,network,address,memo_or_tag,alias,owner_name_kr,status
```

- `status`가 `ready`인 행만 등록 대상입니다.
- `XRP`, `XLM`, `EOS`, `ATOM`, `HBAR`는 `memo_or_tag`가 비어 있으면 스킵합니다.
- `owner_type`은 사용하지 않습니다. 개인 기본 플로우만 지원합니다.

샘플:

```text
configs/sample_addresses.csv
```

## 설치

```powershell
cd "C:\Users\lsm62\Desktop\주소등록봇"
python -m pip install -e .[dev]
python -m playwright install chromium
```

## 전용 Chrome 실행

일반 Chrome 프로필이 아니라 봇 전용 프로필을 사용합니다.

```powershell
.\scripts\launch_chrome_debug.ps1 -Port 9222
```

열린 Chrome에서 빗썸에 직접 로그인한 뒤 주소록 화면을 열어두세요.

## 사용 순서

1. 입력 검증:

```powershell
python -m address_bot.cli validate --input configs/sample_addresses.csv
```

2. 드라이런:

```powershell
python -m address_bot.cli dry-run --input configs/sample_addresses.csv --cdp http://127.0.0.1:9222 --stop-on-error
```

3. 실제 주소등록 클릭 허용:

```powershell
python -m address_bot.cli run --input configs/sample_addresses.csv --cdp http://127.0.0.1:9222 --confirm-register --stop-on-error
```

명령 실행 중 manifest가 출력되며, `REGISTER`를 입력해야 최종 클릭이 진행됩니다.

## 결과 파일

`reports/` 아래에 JSONL 원본 감사 로그와 마스킹된 CSV 요약이 생성됩니다.  
`reports/`, `screenshots/`, `traces/`, 브라우저 프로필은 git에 올리지 않습니다.

## 검증

```powershell
python -m pytest
python -m address_bot.cli validate --input configs/sample_addresses.csv
python -m address_bot.cli run --input configs/sample_addresses.csv --cdp http://127.0.0.1:9222 --stop-on-error
```

마지막 명령은 `--confirm-register`가 없기 때문에 최종 클릭을 거부해야 정상입니다.

## v2: 다중 거래소 주소 수집/검증/후보 생성

v2는 바로 실등록을 누르는 기능이 아니라, 먼저 **잘못된 주소가 등록 단계까지 못 가게 막는 파이프라인**입니다.

흐름:

```text
거래소 입금주소 수집
  -> network_aliases 승인표 확인
  -> token contract / 주소 형식 / memo-tag 검증
  -> 이미 등록된 주소 reconcile
  -> ready 행만 기존 Bithumb validate/dry-run/run으로 전달
```

### 네트워크 매핑 승인표

샘플:

```text
configs/network_aliases.sample.csv
```

`review_status=approved`인 매핑만 등록 후보가 될 수 있습니다. 매핑이 없거나 `needs_review`이면 `needs_mapping`/`blocked_unapproved_mapping`으로 멈춥니다.

### 오프라인 후보 수집 예시

실제 API 키 없이 JSON fixture에서 후보 CSV를 만들 수 있습니다.

```powershell
python -m address_bot.cli collect-addresses `
  --fixture-json .localdata/source_addresses.json `
  --target bithumb `
  --owner-name-kr "홍길동" `
  --out .localdata/candidates/bithumb_candidates.csv
```

fixture 예시:

```json
[
  {
    "exchange": "binance",
    "coin": "USDT",
    "network": "ETH",
    "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "contract_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }
]
```

### 검증 실행

```powershell
python -m address_bot.cli verify-candidates `
  --input .localdata/candidates/bithumb_candidates.csv `
  --network-aliases configs/network_aliases.sample.csv `
  --out .localdata/plans/bithumb_verified.csv `
  --ready-output .localdata/plans/bithumb_ready_for_registration.csv
```

`ready-output`은 기존 빗썸 등록 CLI가 읽을 수 있는 CSV 형식입니다.

### 이미 등록된 주소 제외

```powershell
python -m address_bot.cli reconcile `
  --input .localdata/candidates/bithumb_candidates.csv `
  --registered-input .localdata/current_registered.csv `
  --network-aliases configs/network_aliases.sample.csv `
  --out .localdata/plans/bithumb_reconciled.csv `
  --ready-output .localdata/plans/bithumb_ready_for_registration.csv
```

### 신규 상장 감지

```powershell
python -m address_bot.cli watch-listings `
  --exchange bithumb `
  --markets-json .localdata/bithumb_markets.json `
  --state .localdata/listing_watch_state.json `
  --out .localdata/new_listings.jsonl
```

첫 실행은 현재 목록을 기준선으로 저장합니다. 이후 새 market이 보이면 JSONL에 기록합니다.

### `.env` 사용

비밀값은 repo로 복사하지 마세요. 기본값으로 현재 폴더의 `.env`를 읽고, 다른 파일을 쓰려면:

```powershell
$env:ADDRESS_BOT_ENV_FILE="C:\path\to\.env"
```

다음 키 이름을 지원합니다:

- `UPBIT_ACCESS_KEY` / `UPBIT_SECRET_KEY`
- `BITHUMB_ACCESS_KEY` / `BITHUMB_SECRET_KEY`
- `BITGET_API_PASSWORD`
- `OKX_API_PASSPHRASE`

### API 키 환경 변수

읽기/주소조회 권한만 사용하세요. 출금/거래 권한은 필요 없습니다.

```text
BINANCE_API_KEY / BINANCE_API_SECRET
BYBIT_API_KEY / BYBIT_API_SECRET
BITGET_API_KEY / BITGET_API_SECRET / BITGET_PASSPHRASE
OKX_API_KEY / OKX_API_SECRET / OKX_PASSPHRASE
UPBIT_API_KEY / UPBIT_API_SECRET
BITHUMB_API_KEY / BITHUMB_API_SECRET
```

확인:

```powershell
python -m address_bot.cli check-api --exchange binance
```

### Upbit 등록 타겟

`run-upbit`은 현재도 `--confirm-register` 없이는 브라우저 연결 전에 거부합니다. Upbit PC Web selector와 Travel Rule 화면은 실계정 화면에서 별도 calibration이 필요하므로, calibration 전에는 `needs_manual`로 멈추도록 보수적으로 구현되어 있습니다.

### Live API 주소 수집

API 키가 준비된 뒤에는 fixture 대신 read-only private API로 주소를 수집할 수 있습니다. 네트워크는 절대 추측하지 않기 위해 `--network-aliases`의 approved 행만 사용합니다.

```powershell
python -m address_bot.cli collect-addresses `
  --live-api `
  --owners upbit,binance,bybit,bitget,okx `
  --coins USDT,XRP `
  --network-aliases configs/network_aliases.sample.csv `
  --target bithumb `
  --owner-name-kr "홍길동" `
  --out .localdata/candidates/bithumb_candidates.csv
```

### Live API 등록주소 reconcile

빗썸/업비트에 이미 등록된 출금 허용 주소는 private read API로 조회해서 제외할 수 있습니다.

```powershell
python -m address_bot.cli reconcile `
  --input .localdata/candidates/bithumb_candidates.csv `
  --network-aliases configs/network_aliases.sample.csv `
  --target bithumb `
  --fetch-registered-live `
  --out .localdata/plans/bithumb_reconciled.csv `
  --ready-output .localdata/plans/bithumb_ready_for_registration.csv
```

주의: 이 명령도 등록/출금은 하지 않고 조회만 합니다. 실제 등록은 항상 기존처럼 `dry-run` 후 `run --confirm-register`에서만 가능합니다.

### 온체인 검증 옵션

후보 검증에 `--onchain-check`를 붙이면 ready 후보에 대해 온체인 조회를 추가합니다. 이 검증은 **차단 조건이 아니라 경고 보강용**입니다. 새 거래소 입금주소는 아직 잔액/거래내역이 없을 수 있기 때문입니다.

```powershell
python -m address_bot.cli verify-candidates `
  --input .localdata/candidates/bithumb_candidates.csv `
  --network-aliases configs/network_aliases.sample.csv `
  --out .localdata/plans/bithumb_verified.csv `
  --ready-output .localdata/plans/bithumb_ready_for_registration.csv `
  --onchain-check
```

지원되는 조회:

- EVM 계열: `eth_getCode`, `eth_getTransactionCount`, `eth_getBalance`
- TRON: TronGrid account lookup
- Solana: `getAccountInfo`, `getBalance`
- XRP Ledger: `account_info`

EVM RPC는 기본 공개 endpoint를 넣지 않았습니다. 직접 준비한 RPC URL을 환경변수로 넣어야 합니다.

```text
ADDRESS_BOT_EVM_RPC_URL          # 모든 EVM 공통 fallback
ADDRESS_BOT_ETHEREUM_RPC_URL
ADDRESS_BOT_BSC_RPC_URL
ADDRESS_BOT_POLYGON_RPC_URL
ADDRESS_BOT_ARBITRUM_RPC_URL
ADDRESS_BOT_OPTIMISM_RPC_URL
ADDRESS_BOT_BASE_RPC_URL
```

선택 환경변수:

```text
ADDRESS_BOT_SOLANA_RPC_URL       # 기본값: https://api.mainnet-beta.solana.com
ADDRESS_BOT_XRP_RPC_URL          # 기본값: https://s1.ripple.com:51234/
ADDRESS_BOT_TRONGRID_URL         # 기본값: https://api.trongrid.io
TRONGRID_API_KEY                 # 있으면 TronGrid 헤더로 사용
```

경고 코드:

- `warn_onchain_unavailable`: endpoint 미설정 또는 조회 실패
- `warn_onchain_inactive`: 온체인 계정/잔액/거래활동을 확인하지 못함
- `warn_deposit_kind_mismatch`: 기대한 EOA/contract 종류와 실제 kind가 다름

주의: 온체인 활동 없음은 등록 금지가 아닙니다. 거래소가 새로 발급한 입금주소일 수 있으므로, hard-stop은 여전히 network alias, contract address, address format, memo/tag, UI readback입니다.

## 빗썸 UI 캘리브레이션

캘리브레이션은 이 터미널에서 실행합니다. 단, 로그인/OTP/SMS/이메일 인증은 사용자가 직접 Chrome에서 처리해야 합니다.

1. Windows PowerShell에서 CDP Chrome 실행:

```powershell
.\scripts\launch_chrome_debug.ps1 -Port 9222
```

2. 열린 Chrome에서 직접 빗썸 로그인 후 주소록 화면으로 이동:

```text
https://www.bithumb.com/react/inout/address
```

3. 이 WSL 터미널에서 읽기 전용 inspection 실행:

```bash
.venv/bin/python -m address_bot.cli inspect-bithumb \
  --cdp http://127.0.0.1:9222 \
  --out .localdata/calibration/bithumb_inspection.json \
  --screenshot .localdata/calibration/bithumb_inspection.png
```

이 명령은 클릭/입력/등록을 하지 않습니다. 현재 URL, 버튼 텍스트, label, input, combobox 후보만 읽습니다. 결과에서 `safe_route=true`, `challenge_detected=false`, `has_register_text=true`가 나와야 다음 dry-run selector 조정으로 넘어갑니다.
