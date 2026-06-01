from __future__ import annotations

import argparse
from dataclasses import replace
import json
import sys
from pathlib import Path

from .address_verification import AddressCandidate
from .bithumb_ui import BithumbUi, RegistrationOptions, RunMode
from .browser import BrowserSafetyError, connect_over_cdp
from .candidates import export_bithumb_address_rows, load_candidate_csv, write_candidate_csv
from .exchanges import SUPPORTED_EXCHANGES
from .exchanges.binance import BinanceClient
from .exchanges.bitget import BitgetClient
from .exchanges.bithumb import BithumbClient
from .exchanges.bybit import BybitClient
from .exchanges.okx import OkxClient
from .exchanges.upbit import UpbitClient
from .input_loader import InputLoadError, load_rows
from .listing_watch import detect_new_listings, write_listing_changes
from .models import Outcome, RowResult
from .network_aliases import NetworkAliasIndex, load_network_aliases
from .onchain import OnchainVerifier
from .reconcile import reconcile_candidates, verify_candidates
from .report import write_reports
from .secrets import load_credentials
from .upbit_ui import UpbitRegistrationOptions, UpbitRunMode, UpbitUi
from .ui_inspector import inspect_bithumb_page
from .validation import ready_rows, validate_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bithumb/Upbit address-book registration assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate CSV/XLSX input without opening a browser")
    validate.add_argument("--input", required=True)
    validate.add_argument("--report-dir", default="reports")

    dry_run = subparsers.add_parser("dry-run", help="Fill Bithumb UI but skip final registration clicks")
    _add_browser_args(dry_run)

    run = subparsers.add_parser("run", help="Register Bithumb addresses only when --confirm-register is supplied")
    _add_browser_args(run)
    run.add_argument("--confirm-register", action="store_true", help="Allow final address registration clicks after manifest acceptance")

    list_exchanges = subparsers.add_parser("list-exchanges", help="List supported source/target exchanges")
    list_exchanges.set_defaults(_noop=True)

    check_api = subparsers.add_parser("check-api", help="Check whether API credentials are present for an exchange")
    check_api.add_argument("--exchange", required=True, choices=SUPPORTED_EXCHANGES)

    collect = subparsers.add_parser("collect-addresses", help="Collect/normalize source exchange deposit addresses into candidate CSV")
    collect.add_argument("--fixture-json", help="Offline JSON fixture of deposit addresses; safe for tests and manual imports")
    collect.add_argument("--live-api", action="store_true", help="Use private read-only exchange APIs when --fixture-json is not supplied")
    collect.add_argument("--owners", default="", help="Comma-separated source exchanges, e.g. upbit,binance,bybit,bitget,okx")
    collect.add_argument("--coins", default="", help="Comma-separated coins, e.g. USDT,XRP")
    collect.add_argument("--network-aliases", help="Alias CSV used to decide which source networks to fetch")
    collect.add_argument("--target", default="bithumb", choices=("bithumb", "upbit"))
    collect.add_argument("--owner-name-kr", default="")
    collect.add_argument("--out", required=True)

    verify = subparsers.add_parser("verify-candidates", help="Run hard-stop address verification against candidate CSV")
    _add_candidate_verification_args(verify)

    reconcile = subparsers.add_parser("reconcile", help="Verify candidates and skip already-registered target addresses")
    _add_candidate_verification_args(reconcile)
    reconcile.add_argument("--registered-input", help="Candidate-style CSV of addresses already registered on target")
    reconcile.add_argument("--target", default="bithumb", choices=("bithumb", "upbit"))
    reconcile.add_argument("--fetch-registered-live", action="store_true", help="Fetch target's registered-address list through private read-only API")

    watch = subparsers.add_parser("watch-listings", help="Detect newly seen markets from a market-list JSON fixture")
    watch.add_argument("--exchange", required=True, choices=("bithumb", "upbit", "binance", "bybit", "bitget", "okx"))
    watch.add_argument("--markets-json", required=True)
    watch.add_argument("--state", default=".localdata/listing_watch_state.json")
    watch.add_argument("--out", required=True)

    dry_run_upbit = subparsers.add_parser("dry-run-upbit", help="Upbit UI dry-run; selector calibration currently required")
    _add_browser_args(dry_run_upbit)

    run_upbit = subparsers.add_parser("run-upbit", help="Upbit address registration only when --confirm-register is supplied")
    _add_browser_args(run_upbit)
    run_upbit.add_argument("--confirm-register", action="store_true")

    inspect_bithumb = subparsers.add_parser("inspect-bithumb", help="Read-only Bithumb UI calibration; no clicks or form fills")
    inspect_bithumb.add_argument("--cdp", required=True)
    inspect_bithumb.add_argument("--out", default=".localdata/calibration/bithumb_inspection.json")
    inspect_bithumb.add_argument("--screenshot", default="")

    return parser


def _add_browser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True)
    parser.add_argument("--cdp", required=True)
    parser.add_argument("--report-dir", default="reports")
    parser.add_argument("--stop-on-error", action="store_true")


def _add_candidate_verification_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True)
    parser.add_argument("--network-aliases", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--ready-output", help="Optional Bithumb-compatible CSV containing only ready rows")
    parser.add_argument("--onchain-check", action="store_true", help="Add non-blocking on-chain activity/kind warnings for ready rows")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return command_validate(args)
        if args.command == "dry-run":
            return command_browser(args, mode=RunMode.DRY_RUN)
        if args.command == "run":
            return command_browser(args, mode=RunMode.RUN)
        if args.command == "list-exchanges":
            return command_list_exchanges(args)
        if args.command == "check-api":
            return command_check_api(args)
        if args.command == "collect-addresses":
            return command_collect_addresses(args)
        if args.command == "verify-candidates":
            return command_verify_candidates(args)
        if args.command == "reconcile":
            return command_reconcile(args)
        if args.command == "watch-listings":
            return command_watch_listings(args)
        if args.command == "dry-run-upbit":
            return command_upbit_browser(args, mode=UpbitRunMode.DRY_RUN)
        if args.command == "run-upbit":
            return command_upbit_browser(args, mode=UpbitRunMode.RUN)
        if args.command == "inspect-bithumb":
            return command_inspect_bithumb(args)
    except (InputLoadError, BrowserSafetyError, RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


def command_validate(args: argparse.Namespace) -> int:
    rows = load_rows(args.input)
    results = validate_rows(rows)
    summary = write_reports(results, report_dir=args.report_dir, prefix="validate")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def command_list_exchanges(args: argparse.Namespace) -> int:
    print(json.dumps({"supported_exchanges": SUPPORTED_EXCHANGES, "registration_targets": ["bithumb", "upbit"]}, ensure_ascii=False, indent=2))
    return 0


def command_check_api(args: argparse.Namespace) -> int:
    creds = load_credentials(args.exchange)
    result = {
        "exchange": args.exchange,
        "api_key_present": bool(creds.api_key),
        "api_secret_present": bool(creds.api_secret),
        "passphrase_present": bool(creds.passphrase),
        "ready_for_private_read": creds.is_complete_for_okx if args.exchange == "okx" else creds.has_key_secret,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready_for_private_read"] else 2


def command_collect_addresses(args: argparse.Namespace) -> int:
    if args.fixture_json:
        payload = json.loads(Path(args.fixture_json).read_text(encoding="utf-8"))
        rows = [_candidate_from_fixture(item, target=args.target, owner_name_kr=args.owner_name_kr) for item in payload]
    else:
        if not args.live_api:
            raise RuntimeError("collect-addresses without --fixture-json requires explicit --live-api")
        rows = _collect_live_candidates(args)
    write_candidate_csv(args.out, rows)
    print(json.dumps({"out": args.out, "total": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def command_verify_candidates(args: argparse.Namespace) -> int:
    candidates = load_candidate_csv(args.input)
    aliases = NetworkAliasIndex(load_network_aliases(args.network_aliases))
    results = verify_candidates(candidates, aliases)
    if args.onchain_check:
        results = _add_onchain_warnings(results)
    write_candidate_csv(args.out, results)
    if args.ready_output:
        export_bithumb_address_rows(args.ready_output, results)
    print(_verification_summary(results, out=args.out, ready_output=args.ready_output))
    return 0


def command_reconcile(args: argparse.Namespace) -> int:
    candidates = load_candidate_csv(args.input)
    aliases = NetworkAliasIndex(load_network_aliases(args.network_aliases))
    if args.registered_input:
        registered = load_candidate_csv(args.registered_input)
    elif args.fetch_registered_live:
        registered = _fetch_registered_live(args.target)
    else:
        registered = []
    results = reconcile_candidates(candidates, aliases, registered=registered)
    if args.onchain_check:
        results = _add_onchain_warnings(results)
    write_candidate_csv(args.out, results)
    if args.ready_output:
        export_bithumb_address_rows(args.ready_output, results)
    print(_verification_summary(results, out=args.out, ready_output=args.ready_output))
    return 0


def command_watch_listings(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.markets_json).read_text(encoding="utf-8"))
    changes = detect_new_listings(args.exchange, payload, args.state)
    write_listing_changes(args.out, changes)
    print(json.dumps({"out": args.out, "new_count": len(changes)}, ensure_ascii=False, indent=2))
    return 0


def command_inspect_bithumb(args: argparse.Namespace) -> int:
    playwright = browser = None
    try:
        playwright, browser = connect_over_cdp(args.cdp)
        page = _select_bithumb_page(browser)
        inspection = inspect_bithumb_page(page, screenshot_path=args.screenshot or None)
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(inspection.to_json(), encoding="utf-8")
        print(inspection.to_json())
        return 0 if inspection.safe_route and not inspection.challenge_detected else 2
    finally:
        # This tool attaches to a user-owned Chrome over CDP. Do not call
        # browser.close(), because that can close the manual login browser.
        if playwright is not None:
            playwright.stop()


def command_browser(args: argparse.Namespace, *, mode: RunMode) -> int:
    rows = load_rows(args.input)
    validation_results = validate_rows(rows)
    eligible = ready_rows(validation_results)
    non_eligible_results = [result for result in validation_results if result.outcome is not Outcome.READY]

    if mode is RunMode.RUN and not args.confirm_register:
        refusal = [
            RowResult(row=row, outcome=Outcome.NEEDS_MANUAL, reason="run refused: --confirm-register is required for final clicks")
            for row in eligible
        ]
        summary = write_reports(non_eligible_results + refusal, report_dir=args.report_dir, prefix="run_refused")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("Refused: run requires --confirm-register before any final address-registration click.", file=sys.stderr)
        return 2

    if mode is RunMode.RUN and not _manifest_accepted(eligible):
        print("Cancelled before final registration clicks.", file=sys.stderr)
        return 2

    playwright = browser = None
    results: list[RowResult] = list(non_eligible_results)
    try:
        playwright, browser = connect_over_cdp(args.cdp)
        page = _select_bithumb_page(browser)
        ui = BithumbUi(page)
        options = RegistrationOptions(
            mode=mode,
            confirm_register=bool(getattr(args, "confirm_register", False)),
            stop_on_error=bool(args.stop_on_error),
        )
        for row in eligible:
            result = ui.register_row(row, options)
            results.append(result)
            print(f"row {row.row_number}: {result.outcome.value} {result.reason}")
            if args.stop_on_error and result.outcome in {Outcome.NEEDS_MANUAL, Outcome.FAILED}:
                break
    finally:
        # This tool attaches to a user-owned Chrome over CDP. Do not call
        # browser.close(), because that can close the manual login browser.
        if playwright is not None:
            playwright.stop()

    prefix = "dry_run" if mode is RunMode.DRY_RUN else "run"
    summary = write_reports(results, report_dir=args.report_dir, prefix=prefix)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def command_upbit_browser(args: argparse.Namespace, *, mode: UpbitRunMode) -> int:
    rows = load_rows(args.input)
    validation_results = validate_rows(rows)
    eligible = ready_rows(validation_results)
    non_eligible_results = [result for result in validation_results if result.outcome is not Outcome.READY]

    if mode is UpbitRunMode.RUN and not args.confirm_register:
        refusal = [
            RowResult(row=row, outcome=Outcome.NEEDS_MANUAL, reason="run-upbit refused: --confirm-register is required for final clicks")
            for row in eligible
        ]
        summary = write_reports(non_eligible_results + refusal, report_dir=args.report_dir, prefix="run_upbit_refused")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("Refused: run-upbit requires --confirm-register before any final address-registration click.", file=sys.stderr)
        return 2

    if mode is UpbitRunMode.RUN and not _manifest_accepted(eligible):
        print("Cancelled before final Upbit registration clicks.", file=sys.stderr)
        return 2

    playwright = browser = None
    results: list[RowResult] = list(non_eligible_results)
    try:
        playwright, browser = connect_over_cdp(args.cdp)
        page = _select_upbit_page(browser)
        ui = UpbitUi(page)
        options = UpbitRegistrationOptions(mode=mode, confirm_register=bool(getattr(args, "confirm_register", False)), stop_on_error=bool(args.stop_on_error))
        for row in eligible:
            result = ui.register_row(row, options)
            results.append(result)
            print(f"row {row.row_number}: {result.outcome.value} {result.reason}")
            if args.stop_on_error and result.outcome in {Outcome.NEEDS_MANUAL, Outcome.FAILED}:
                break
    finally:
        # This tool attaches to a user-owned Chrome over CDP. Do not call
        # browser.close(), because that can close the manual login browser.
        if playwright is not None:
            playwright.stop()
    prefix = "dry_run_upbit" if mode is UpbitRunMode.DRY_RUN else "run_upbit"
    print(json.dumps(write_reports(results, report_dir=args.report_dir, prefix=prefix), ensure_ascii=False, indent=2))
    return 0


def _manifest_accepted(rows) -> bool:
    print("Registration manifest:")
    for row in rows:
        print(f"- row {row.row_number}: {row.exchange} {row.coin} {row.network} {row.alias} {row.address[:6]}...{row.address[-4:]}")
    answer = input("Type REGISTER to allow final address-registration clicks: ")
    return answer.strip() == "REGISTER"


def _select_bithumb_page(browser):
    candidates = []
    for context in browser.contexts:
        for page in context.pages:
            if "bithumb.com" in page.url:
                candidates.append(page)
    if candidates:
        def score(page) -> tuple[int, str]:
            url = page.url
            value = 0
            if "/react/inout/address/register" in url:
                value += 100
            elif "/react/inout/address" in url:
                value += 80
            if "withdraw" in url:
                value -= 1000
            return (value, url)

        return sorted(candidates, key=score, reverse=True)[0]
    if browser.contexts and browser.contexts[0].pages:
        page = browser.contexts[0].pages[0]
        page.goto("https://www.bithumb.com/react/inout/address/register", wait_until="domcontentloaded")
        return page
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.bithumb.com/react/inout/address/register", wait_until="domcontentloaded")
    return page


def _select_upbit_page(browser):
    for context in browser.contexts:
        for page in context.pages:
            if "upbit.com" in page.url:
                return page
    if browser.contexts and browser.contexts[0].pages:
        page = browser.contexts[0].pages[0]
        page.goto("https://upbit.com", wait_until="domcontentloaded")
        return page
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://upbit.com", wait_until="domcontentloaded")
    return page


def _candidate_from_fixture(item: dict[str, object], *, target: str, owner_name_kr: str) -> AddressCandidate:
    def text(*names: str) -> str:
        for name in names:
            value = item.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    return AddressCandidate(
        source_exchange=text("exchange", "source_exchange"),
        target_exchange=target,
        coin=text("coin", "currency", "ccy"),
        source_network=text("network", "source_network", "chain", "net_type"),
        target_network=text("target_network"),
        canonical_network_id=text("canonical_network_id"),
        address_family=text("address_family"),
        address=text("address", "addr", "deposit_address"),
        memo_or_tag=text("memo_or_tag", "memo", "tag", "secondary_address"),
        alias=text("alias"),
        owner_name_kr=text("owner_name_kr") or owner_name_kr,
        source_contract_address=text("contract_address", "source_contract_address", "ctAddr"),
    )


def _add_onchain_warnings(results):
    verifier = OnchainVerifier.from_env()
    updated = []
    for result in results:
        if not result.is_ready:
            updated.append(result)
            continue
        onchain = verifier.verify(result.candidate)
        warnings = tuple(dict.fromkeys((*result.warnings, *onchain.warning_codes)))
        updated.append(replace(result, warnings=warnings))
    return updated


def _verification_summary(results, *, out: str, ready_output: str | None = None) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.state.value] = counts.get(result.state.value, 0) + 1
    return json.dumps({"out": out, "ready_output": ready_output, "total": len(results), "counts": counts}, ensure_ascii=False, indent=2)


def _collect_live_candidates(args: argparse.Namespace) -> list[AddressCandidate]:
    owners = [item.strip().casefold() for item in args.owners.split(",") if item.strip()]
    coins = {item.strip().upper() for item in args.coins.split(",") if item.strip()}
    if not owners or not coins:
        raise RuntimeError("--owners and --coins are required with --live-api")
    if not args.network_aliases:
        raise RuntimeError("--network-aliases is required with --live-api so networks are never guessed")
    aliases = load_network_aliases(args.network_aliases)
    rows: list[AddressCandidate] = []
    for alias in aliases:
        if not alias.is_approved:
            continue
        if alias.source_exchange.strip().casefold() not in owners:
            continue
        if alias.target_exchange.strip().casefold() != args.target.strip().casefold():
            continue
        if alias.coin.strip().upper() not in coins:
            continue
        record = _fetch_deposit_address(alias.source_exchange, alias.coin, alias.source_network)
        rows.append(
            record.to_candidate(
                target_exchange=args.target,
                owner_name_kr=args.owner_name_kr,
                target_network=alias.target_network,
            )
        )
    return rows


def _client_for_exchange(exchange: str):
    code = exchange.strip().casefold()
    creds = load_credentials(code)
    if code == "binance":
        return BinanceClient(creds)
    if code == "bybit":
        return BybitClient(creds)
    if code == "bitget":
        return BitgetClient(creds)
    if code == "okx":
        return OkxClient(creds)
    if code == "upbit":
        return UpbitClient(creds)
    if code == "bithumb":
        return BithumbClient(creds)
    raise RuntimeError(f"Unsupported exchange: {exchange}")


def _fetch_deposit_address(exchange: str, coin: str, source_network: str):
    code = exchange.strip().casefold()
    client = _client_for_exchange(code)
    if code == "binance":
        return client.get_deposit_address(coin, source_network)
    if code == "bybit":
        return client.master_deposit_address(coin, source_network)
    if code == "bitget":
        return client.get_deposit_address(coin, source_network)
    if code == "okx":
        matches = [item for item in client.deposit_addresses(coin) if item.network.strip().casefold() == source_network.strip().casefold()]
        if not matches:
            raise RuntimeError(f"No OKX deposit address for {coin} {source_network}")
        return matches[0]
    if code in {"upbit", "bithumb"}:
        matches = [
            item
            for item in client.deposit_addresses()
            if item.coin.strip().upper() == coin.strip().upper()
            and item.network.strip().casefold() == source_network.strip().casefold()
        ]
        if not matches:
            raise RuntimeError(f"No {exchange} deposit address for {coin} {source_network}")
        return matches[0]
    raise RuntimeError(f"Unsupported exchange: {exchange}")


def _fetch_registered_live(target: str) -> list[AddressCandidate]:
    code = target.strip().casefold()
    client = _client_for_exchange(code)
    if code == "bithumb":
        payload = client.withdrawal_allowlist()
    elif code == "upbit":
        payload = client.withdrawal_allowlist()
    else:
        raise RuntimeError("live registered-address reconciliation currently supports bithumb/upbit targets")
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("result") or payload.get("rows") or []
    else:
        rows = payload or []
    return [_registered_candidate_from_record(item, target=code) for item in rows if isinstance(item, dict)]


def _registered_candidate_from_record(item: dict[str, object], *, target: str) -> AddressCandidate:
    def text(*names: str) -> str:
        for name in names:
            value = item.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    return AddressCandidate(
        source_exchange=text("exchange", "exchange_name", "beneficiary_exchange") or "registered",
        target_exchange=target,
        coin=text("currency", "coin", "asset"),
        source_network=text("net_type", "network", "chain"),
        target_network=text("net_type", "network", "chain"),
        address=text("withdraw_address", "address", "wallet_address"),
        memo_or_tag=text("secondary_address", "memo", "tag"),
        alias=text("alias", "nickname"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
