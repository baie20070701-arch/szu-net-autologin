#!/usr/bin/env python3
"""深圳大学 Dr.COM 内网自动登录/断线重连脚本。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import os
import re
import secrets
import signal
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_PORTAL = "http://172.30.255.42"
DEFAULT_CONFIG = Path.home() / ".config" / "szu-autologin" / "config.json"
DEFAULT_CHECK_INTERVAL = 20.0
DEFAULT_LOGIN_RETRY_INTERVAL = 300.0
DEFAULT_TIMEOUT = 5.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

LOG = logging.getLogger("szu-autologin")


class PortalError(RuntimeError):
    """门户请求或响应格式异常。"""


def result_ok(result: Any) -> bool:
    return result == 1 or str(result).lower() in ("1", "ok")


def parse_jsonp(text: str) -> dict[str, Any]:
    """兼容 JSON 和 Dr.COM 返回的 callback({...}) 两种格式。"""
    stripped = text.strip().lstrip("\ufeff")
    if not stripped:
        raise PortalError("门户返回了空响应")

    if stripped[0] == "{":
        value = json.loads(stripped)
    else:
        match = re.fullmatch(r"[^(]*\((.*)\)\s*;?", stripped, flags=re.DOTALL)
        if not match:
            preview = stripped[:160].replace("\n", " ")
            raise PortalError(f"无法解析门户响应: {preview}")
        value = json.loads(match.group(1))

    if not isinstance(value, dict):
        raise PortalError("门户响应不是 JSON 对象")
    return value


def decode_response(data: bytes, charset: str | None) -> str:
    for encoding in filter(None, (charset, "utf-8", "gb18030", "latin1")):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    raise PortalError("无法解码门户响应")


class EportalClient:
    def __init__(self, portal: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.portal = portal.rstrip("/")
        self.timeout = timeout
        # 校园网门户必须直连，不能走系统 HTTP(S) 代理。
        self.opener = build_opener(ProxyHandler({}))

    def _request_jsonp(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        callback = "dr" + secrets.token_hex(4)
        # Dr.COM 要求 callback 是查询串中的第一个参数，否则会返回 400。
        query: dict[str, Any] = {"callback": callback}
        query.update(params)
        full_url = f"{url}?{urlencode(query)}"
        request = Request(
            full_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Referer": f"{self.portal}/",
                "Connection": "close",
            },
        )

        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read()
                charset = response.headers.get_content_charset()
        except HTTPError as exc:
            try:
                preview = exc.read().decode("utf-8", "replace")[:160]
            except Exception:
                preview = ""
            raise PortalError(f"门户 HTTP {exc.code}: {preview}") from exc
        except URLError as exc:
            raise PortalError(f"无法连接门户: {exc.reason}") from exc
        except TimeoutError as exc:
            raise PortalError("连接门户超时") from exc

        return parse_jsonp(decode_response(body, charset))

    def is_online(self) -> tuple[bool, dict[str, Any]]:
        data = self._request_jsonp(f"{self.portal}/drcom/chkstatus", {})
        result = data.get("result")
        return result_ok(result), data

    def load_portal_config(self) -> dict[str, Any]:
        url = f"{self.portal}:801/eportal/portal/page/loadConfig"
        data = self._request_jsonp(url, {})
        if data.get("code") not in (1, "1", "ok"):
            raise PortalError(data.get("msg") or "读取门户配置失败")
        config = data.get("data")
        return config if isinstance(config, dict) else {}

    @staticmethod
    def _prepare_password(password: str, portal_config: dict[str, Any]) -> str:
        prepared = password

        try:
            password_cut = int(portal_config.get("password_cut") or 0)
        except (TypeError, ValueError):
            password_cut = 0

        if password_cut and len(prepared) > 16:
            if password_cut == 1:
                prepared = prepared[:8]
            elif password_cut == 2:
                prepared = prepared[-8:]
            elif password_cut == 3:
                prepared = prepared[:16]
            elif password_cut == 4:
                prepared = prepared[-16:]

        try:
            en_md5 = int(portal_config.get("en_md5") or 0)
        except (TypeError, ValueError):
            en_md5 = 0

        if en_md5:
            # 与门户 pc 登录脚本的 MD5 分支保持一致：PID=1, CALG=12345678。
            digest = hashlib.md5(("1" + prepared + "12345678").encode("utf-8")).hexdigest()
            prepared = digest + "12345678" + "1"

        return prepared

    def login(self, username: str, password: str) -> tuple[bool, dict[str, Any]]:
        portal_config: dict[str, Any] = {}
        try:
            portal_config = self.load_portal_config()
        except PortalError as exc:
            LOG.warning("读取门户配置失败，按默认参数登录: %s", exc)

        prepared_password = self._prepare_password(password, portal_config)
        try:
            en_md5 = int(portal_config.get("en_md5") or 0)
        except (TypeError, ValueError):
            en_md5 = 0

        params = {
            "DDDDD": username,
            "upass": prepared_password,
            "0MKKey": "123456",
            "R1": "0",
            "R2": "1" if en_md5 else "",
            "R3": "0",
            "R6": "0",
            "para": "00",
            "v6ip": "",
            "terminal_type": "1",
            "lang": "zh-cn",
        }
        data = self._request_jsonp(f"{self.portal}/drcom/login", params)
        result = data.get("result")
        return result_ok(result), data


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise SystemExit(f"无法读取配置文件 {path}: {exc}") from exc

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"配置文件不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"配置文件必须是 JSON 对象: {path}")
    return value


def write_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    path.chmod(0o600)


def select_portal(args: argparse.Namespace, config: dict[str, Any]) -> str:
    return str(args.portal or config.get("portal") or DEFAULT_PORTAL).rstrip("/")


def select_timeout(args: argparse.Namespace, config: dict[str, Any]) -> float:
    if args.timeout is not None:
        return max(1.0, float(args.timeout))
    try:
        return max(1.0, float(config.get("timeout", DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


def require_credentials(
    args: argparse.Namespace, config: dict[str, Any]
) -> tuple[str, str]:
    username = str(
        args.username or os.environ.get("SZU_USERNAME") or config.get("username") or ""
    ).strip()
    password = str(
        args.password or os.environ.get("SZU_PASSWORD") or config.get("password") or ""
    )
    if not username or not password:
        raise SystemExit(
            "缺少账号或密码。请先运行 `python3 szu_autologin.py init`，"
            "或设置 SZU_USERNAME / SZU_PASSWORD。"
        )
    return username, password


def portal_message(data: dict[str, Any]) -> str:
    for key in ("msg", "message", "ErrorMsg", "ret_code", "result"):
        if data.get(key) not in (None, ""):
            return str(data[key])
    return "门户未返回具体原因"


def setup_logging(verbose: bool, log_file: Path | None) -> None:
    handlers: list[logging.Handler] = []
    # pythonw.exe（Windows 计划任务）下 sys.stderr 可能为 None。
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    if not handlers:
        handlers.append(logging.NullHandler())

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )


@contextmanager
def single_instance(lock_path: Path):
    """防止 Windows 或 macOS/Linux 同时启动多个守护进程。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        import msvcrt

        handle = open(lock_path, "a+", encoding="utf-8")
        try:
            handle.seek(0)
            if handle.read(1) == "":
                handle.write("0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise SystemExit("已有另一个自动登录进程在运行") from exc
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
            yield
        finally:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            handle.close()
        return

    try:
        import fcntl
    except ImportError:
        yield
        return

    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(fd, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SystemExit("已有另一个自动登录进程在运行") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def command_init(args: argparse.Namespace) -> int:
    config_path: Path = args.config
    if config_path.exists() and not args.force:
        answer = input(f"{config_path} 已存在，覆盖吗？[y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消。")
            return 1

    username = input("请填写校园网账号（一般即学号）: ").strip()
    if not username:
        raise SystemExit("账号不能为空")
    password = getpass.getpass("请填写校园网密码（输入时不显示）: ")
    if not password:
        raise SystemExit("密码不能为空")

    config: dict[str, Any] = {
        "portal": args.portal or DEFAULT_PORTAL,
        "username": username,
        "password": password,
        "check_interval": DEFAULT_CHECK_INTERVAL,
        "login_retry_interval": DEFAULT_LOGIN_RETRY_INTERVAL,
        "timeout": args.timeout if args.timeout is not None else DEFAULT_TIMEOUT,
    }
    write_private_json(config_path, config)
    print(f"配置已写入: {config_path}")
    if os.name == "nt":
        print("密码只保存在当前 Windows 用户目录中，请不要共享该文件。")
    else:
        print("文件权限已设置为 600；密码不会写进脚本或日志。")
    return 0


def command_status(args: argparse.Namespace, config: dict[str, Any]) -> int:
    client = EportalClient(select_portal(args, config), select_timeout(args, config))
    try:
        online, _ = client.is_online()
    except PortalError as exc:
        LOG.error("状态检测失败: %s", exc)
        return 2

    if online:
        print("在线")
        return 0
    print("离线")
    return 1


def command_once(args: argparse.Namespace, config: dict[str, Any]) -> int:
    client = EportalClient(select_portal(args, config), select_timeout(args, config))

    try:
        online, _ = client.is_online()
    except PortalError as exc:
        LOG.error("状态检测失败: %s", exc)
        return 2

    if online:
        print("当前已在线，无需登录。")
        return 0

    username, password = require_credentials(args, config)
    try:
        print("当前离线，正在登录……")
        success, data = client.login(username, password)
    except PortalError as exc:
        LOG.error("登录请求失败: %s", exc)
        return 2

    if success:
        print("登录成功。")
        return 0
    LOG.error("登录失败: %s", portal_message(data))
    return 1


def command_run(args: argparse.Namespace, config: dict[str, Any]) -> int:
    username, password = require_credentials(args, config)
    portal = select_portal(args, config)
    timeout = select_timeout(args, config)
    check_interval = float(
        args.check_interval
        if args.check_interval is not None
        else config.get("check_interval", DEFAULT_CHECK_INTERVAL)
    )
    retry_interval = float(
        args.login_retry_interval
        if args.login_retry_interval is not None
        else config.get("login_retry_interval", DEFAULT_LOGIN_RETRY_INTERVAL)
    )
    check_interval = max(5.0, check_interval)
    retry_interval = max(30.0, retry_interval)

    client = EportalClient(portal, timeout)
    stop_event = threading.Event()

    def stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    lock_path = args.config.parent / "szu-autologin.lock"
    with single_instance(lock_path):
        LOG.info(
            "自动重连已启动：门户=%s，状态检查间隔=%.0fs，登录失败重试间隔=%.0fs",
            portal,
            check_interval,
            retry_interval,
        )
        last_state: bool | None = None
        last_error = ""

        while not stop_event.is_set():
            try:
                online, _ = client.is_online()
            except PortalError as exc:
                message = str(exc)
                if message != last_error:
                    LOG.warning("暂时无法检测在线状态: %s", message)
                    last_error = message
                last_state = None
                stop_event.wait(check_interval)
                continue

            last_error = ""
            if online:
                if last_state is not True:
                    LOG.info("当前在线")
                last_state = True
                stop_event.wait(check_interval)
                continue

            if last_state is not False:
                LOG.warning("检测到网络掉线，尝试重新登录")
            last_state = False

            try:
                success, data = client.login(username, password)
            except PortalError as exc:
                LOG.error("登录请求失败: %s", exc)
                stop_event.wait(retry_interval)
                continue

            if success:
                LOG.info("重新登录成功")
                last_state = True
                stop_event.wait(check_interval)
            else:
                LOG.error("登录失败: %s", portal_message(data))
                stop_event.wait(retry_interval)

        LOG.info("自动重连已停止")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="深圳大学 Dr.COM 内网自动登录和断线重连工具"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"配置文件路径（默认：{DEFAULT_CONFIG}）",
    )
    parser.add_argument("--portal", help=f"门户地址（默认：{DEFAULT_PORTAL}）")
    parser.add_argument("--timeout", type=float, help=f"网络超时秒数（默认：{DEFAULT_TIMEOUT:g}）")
    parser.add_argument("--username", help="账号；优先级高于配置文件和 SZU_USERNAME")
    parser.add_argument("--password", help="密码；不安全，建议用 init 或 SZU_PASSWORD")
    parser.add_argument("--verbose", action="store_true", help="输出调试日志")
    parser.add_argument("--log-file", type=Path, help="同时写入日志文件")

    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser(
        "init", help="交互式生成仅当前用户可读的配置文件"
    )
    init_parser.add_argument("--force", action="store_true", help="直接覆盖已有配置")
    subparsers.add_parser("status", help="只检测当前是否在线")
    subparsers.add_parser("once", help="检测并尝试登录一次")
    run_parser = subparsers.add_parser("run", help="持续监控，掉线后自动登录")
    run_parser.add_argument("--check-interval", type=float, help="在线状态检查间隔秒数")
    run_parser.add_argument(
        "--login-retry-interval", type=float, help="登录失败后的重试间隔秒数"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose, args.log_file)

    if args.command == "init":
        return command_init(args)

    config = read_json_file(args.config)
    if args.command == "status":
        return command_status(args, config)
    if args.command == "once":
        return command_once(args, config)
    if args.command == "run":
        return command_run(args, config)
    parser.error("未知命令")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
