#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the user-facing VPS handoff handbook from a local JSON summary."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MISSING = "未记录"


def get(data: dict[str, Any], path: str, default: Any = MISSING) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    if current in (None, ""):
        return default
    return current


def text(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    if value in (None, ""):
        return MISSING
    return str(value)


def bullet(label: str, value: Any) -> str:
    return f"- {label}: {text(value)}"


def bullet_list(items: Any) -> list[str]:
    if not items:
        return ["- 未记录"]
    if isinstance(items, str):
        return [f"- {items}"]
    if isinstance(items, list):
        return [f"- {text(item)}" for item in items if text(item) != MISSING] or ["- 未记录"]
    return [f"- {text(items)}"]


def code_block(value: Any, language: str = "") -> list[str]:
    if value in (None, ""):
        return ["未记录"]
    return [f"```{language}", str(value), "```"]


def generated_at(data: dict[str, Any]) -> str:
    value = get(data, "generated_at", "")
    if value != MISSING:
        return str(value)
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def render(data: dict[str, Any]) -> str:
    panel_url = get(data, "panel.url")
    panel_username = get(data, "panel.username")
    panel_password = get(data, "panel.password")
    ssh_command = get(data, "server.ssh_command", f"ssh {get(data, 'server.ssh_alias')}")
    troubleshoot_prompt = get(
        data,
        "troubleshooting.assistant_prompt",
        "我的VPS现在出现了问题：<请在这里描述你遇到的问题>。请帮助我排查。下面是这台 VPS 的部署说明文档，请结合文档里的 SSH、3x-ui、入站和客户端配置来判断问题。",
    )

    lines: list[str] = [
        "# VPS 使用说明（请妥善保存）",
        "",
        f"生成时间: {generated_at(data)}",
        "",
        "这份文档包含 3x-ui 面板密码、客户端连接信息、SSH 连接方式等敏感内容。请保存在安全位置，不要发给不信任的人。",
        "",
        "## 1. 3x-ui 面板服务",
        "",
        "3x-ui 面板服务已经部署完成。以后需要查看或调整入站、客户端、订阅等配置时，可以使用下面的信息登录面板。",
        "",
        bullet("面板链接", panel_url),
        bullet("用户名", panel_username),
        bullet("密码", panel_password),
        bullet("访问方式", get(data, "panel.access")),
        bullet("面板端口", get(data, "panel.port")),
        bullet("面板路径", get(data, "panel.path")),
        bullet("服务状态", get(data, "panel.service_status")),
        "",
        "## 2. 已配置的入站和客户端",
        "",
        "本次已经为你配置了一套默认可用的 VLESS/Reality 入站和一个客户端。一般情况下，客户端直接使用这里的导入链接或本地配置文件即可。",
        "",
        "### 入站规则",
        "",
        bullet("名称", get(data, "inbound.remark")),
        bullet("协议", get(data, "inbound.protocol")),
        bullet("端口", get(data, "inbound.port")),
        bullet("传输", get(data, "inbound.transport")),
        bullet("安全", get(data, "inbound.security")),
        bullet("Flow", get(data, "inbound.flow")),
        bullet("SNI/serverName", get(data, "inbound.server_name")),
        bullet("Reality 公钥", get(data, "inbound.public_key")),
        bullet("Reality short ID", get(data, "inbound.short_id")),
        bullet("连接路线", get(data, "inbound.route")),
        "",
        "### 客户端规则",
        "",
        bullet("客户端名称", get(data, "client.name")),
        bullet("已启用", get(data, "client.enabled")),
        bullet("客户端服务器地址", get(data, "client.server")),
        bullet("客户端导出文件", get(data, "client.export_file", get(data, "files.client_export"))),
        bullet("Mihomo/Clash 配置文件", get(data, "client.mihomo_file")),
        bullet("订阅链接", get(data, "client.subscription_url")),
        "",
        "客户端导入链接:",
        "",
        *code_block(get(data, "client.vless_uri")),
        "",
        "## 3. VPS 服务器连接方式",
        "",
        "这台 VPS 的 SSH 登录已经改为密钥登录。以后连接服务器时，优先使用下面的命令。",
        "",
        *code_block(ssh_command, "bash"),
        "",
        bullet("SSH 别名", get(data, "server.ssh_alias")),
        bullet("服务器 IP/主机", get(data, "server.host_ip")),
        bullet("服务器用户", get(data, "server.ssh_user")),
        bullet("SSH 端口", get(data, "server.ssh_port")),
        bullet("本地私钥路径", get(data, "server.identity_file")),
        bullet("密码登录", get(data, "server.password_auth")),
        bullet("远端主机名", get(data, "server.hostname")),
        bullet("系统版本", get(data, "server.os")),
        "",
        "## 4. 本次对 VPS 做了哪些配置",
        "",
        "已经完成的主要变更:",
        "",
        *bullet_list(get(data, "changes", [
            "安装或确认 SSH 公钥登录",
            "将 SSH 切换到随机高位端口",
            "关闭 SSH 密码登录",
            "配置本地 SSH alias",
            "安装并启用 UFW 防火墙",
            "安装并配置 3x-ui 面板",
            "创建 VLESS/Reality 入站和客户端",
            "导出本地客户端配置",
        ])),
        "",
        "当前防火墙规则摘要:",
        "",
        *bullet_list(get(data, "firewall.rules")),
        "",
        "## 5. 本地保存的文件",
        "",
        bullet("最终说明文档", get(data, "files.handoff_doc")),
        bullet("技术运行记录", get(data, "files.technical_runbook")),
        bullet("客户端导出", get(data, "files.client_export", get(data, "client.export_file"))),
        bullet("Mihomo/Clash 配置", get(data, "files.mihomo_yaml", get(data, "client.mihomo_file"))),
        "",
        "## 6. 验证结果",
        "",
        *bullet_list([
            get(data, "verification.ssh"),
            get(data, "verification.panel"),
            get(data, "verification.inbound"),
            get(data, "verification.client_export"),
        ]),
        "",
        "## 7. 如果有疑问或出现问题",
        "",
        "你可以继续在当前聊天里提问。也可以把下面这段话发给你的智能助手，并把这份文档一起发送过去:",
        "",
        *code_block(troubleshoot_prompt),
        "",
        "发送给其他人或其他智能助手前，请确认你信任对方，因为这份文档里包含可以登录面板和使用客户端的敏感信息。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VPS user handoff handbook.")
    parser.add_argument("--input", required=True, help="Path to deployment-summary.json")
    parser.add_argument("--output", required=True, help="Path to VPS-使用说明.md")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("input JSON must be an object")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    previous_umask = os.umask(0o177)
    try:
        output_path.write_text(render(data), encoding="utf-8")
    finally:
        os.umask(previous_umask)
    output_path.chmod(0o600)
    print(f"Wrote handbook: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
