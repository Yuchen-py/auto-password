# -*- coding: utf-8 -*-
"""
pswd.py — 本地命令行密码生成与记录管理工具

解决的问题
----------
在不同应用 / 账号下需要一套可追溯、可本地留存的密码时，手工记录容易遗漏、
难以核对。本工具根据「应用标识 + 当前时间戳」按固定规则生成密码，并把生成
记录（应用标识、密码、可选账号标识）保存到本地 JSON 文件，便于事后查询核对。

密码生成规则（与历史版本保持一致，请勿随意改动）
--------------------------------------------------
1. 头部：用户输入的应用标识 app_id（必填；留空则取消本次生成，不创建记录）；
2. 可选：手机号 / 邮箱等账号标识 account_id（仅用于记录与区分账号，不参与密码拼接）；
3. 分隔符：固定特殊字符 "@"；
4. 尾部：当前时间格式化为 YYYYMMDDHHMMSS，转为整数后再转为十六进制（去掉 0x 前缀），
   对十六进制字符串中的每个字符做 ASCII 码 +2 处理；
5. 最终密码 = app_id + "@" + 尾部。

数据文件
--------
password.json 为 JSON 数组，每条记录形如：
    {"app": "google", "password": "google@...", "id": "user@example.com"}
其中 "id" 字段仅在填写了账号标识时存在。文件保存在脚本（或打包后的可执行
程序）所在目录，而不是启动命令时的工作目录。
"""

import json
import os
import sys
from datetime import datetime


def _init_console_encoding():
    """Windows 下将控制台与标准输入输出统一为 UTF-8，避免中文提示乱码。

    打包后的可执行程序默认按系统区域编码（如 GBK）初始化 stdio，重定向或
    非 UTF-8 代码页下中文会出现乱码；这里切换控制台代码页为 65001（UTF-8），
    并把 stdin / stdout / stderr 重新配置为 UTF-8。非 Windows 平台自动跳过。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        # 个别宿主环境不支持重配置时保持默认行为，不影响主流程
        pass


_init_console_encoding()

# ---------- 常量定义 ----------
SEPARATOR = "@"                    # 密码中应用标识与尾部之间的固定分隔符
JSON_FILENAME = "password.json"   # 本地记录文件名


def get_data_path():
    """返回记录文件 password.json 的完整路径。

    - 打包为可执行程序（PyInstaller 等）后，文件保存在可执行程序所在目录；
    - 直接以脚本方式运行时，文件保存在脚本所在目录。
    这样无论从哪个工作目录启动，记录文件位置都保持固定、可预期。
    """
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, JSON_FILENAME)


def load_records():
    """读取本地记录文件，返回记录列表（list[dict]）。

    - 文件不存在：返回空列表；
    - 文件损坏 / 为空 / JSON 解析失败：视为空列表；
    - 旧数据不是数组（单个对象）：包装成列表后返回。
    """
    filepath = get_data_path()
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]
    except (json.JSONDecodeError, OSError, ValueError):
        return []


def save_records(records):
    """将记录列表写回本地 JSON 文件（UTF-8 编码，缩进 4 空格，保留中文）。"""
    filepath = get_data_path()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=4)


def build_tail(now=None):
    """根据给定时间生成密码尾部（规则见模块 docstring）。

    参数:
        now: datetime 对象；不传则使用当前时间，便于测试与复算。
    返回:
        十六进制时间戳逐字符 ASCII 码 +2 后的字符串。
    """
    now = now or datetime.now()
    time_str = now.strftime("%Y%m%d%H%M%S")   # 例如 20260607234559
    time_int = int(time_str)
    hex_str = hex(time_int)[2:]                # 去掉 '0x' 前缀
    # 对十六进制字符串的每个字符进行 ASCII 码 +2 操作
    tail = "".join(chr(ord(ch) + 2) for ch in hex_str)
    return tail


def generate_password():
    """交互式生成一条密码并保存到本地记录文件。"""
    # 1. 获取应用标识（必填；留空则取消本次生成，不创建任何记录）
    app_id = input("请输入应用标识（例如 google、facebook）: ").strip()
    if not app_id:
        print("应用标识不能为空，已取消生成。")
        return

    # 2. 可选：手机号或邮箱（账号标识），留空则不记录该字段
    account_id = input("请输入手机号或邮箱（用于区分账号，若不需则直接回车）: ").strip()
    if account_id == "":
        account_id = None

    # 3. 按固定规则生成密码
    tail = build_tail()
    password = app_id + SEPARATOR + tail

    # 4. 在控制台输出生成的密码及关联的账号标识（如果有）
    if account_id:
        print(f"应用标识：{app_id}，账号：{account_id}，生成的密码为：{password}")
    else:
        print(f"应用标识：{app_id}，生成的密码为：{password}")

    # 5. 查重提示，并追加保存新记录
    records = load_records()
    duplicate = any(
        r.get("app") == app_id and r.get("id") == account_id
        for r in records
    )
    if duplicate:
        print("提示：已存在相同应用标识与账号的记录，本次仍会追加保存。")

    new_entry = {"app": app_id, "password": password}
    if account_id:
        new_entry["id"] = account_id
    records.append(new_entry)
    save_records(records)
    print(f"已保存记录到 {get_data_path()}")


def format_record(index, record):
    """将单条记录格式化为一行可读文本。"""
    app = record.get("app", "")
    pwd = record.get("password", "")
    acc = record.get("id", "—")
    return f"[{index}] 应用：{app}  账号：{acc}  密码：{pwd}"


def list_records():
    """列出本地保存的全部密码记录。"""
    records = load_records()
    if not records:
        print("当前没有保存任何记录。")
        return
    print(f"共 {len(records)} 条记录：")
    for i, record in enumerate(records, start=1):
        print(format_record(i, record))


def search_records():
    """按关键字在应用标识 / 账号标识中模糊查找记录。"""
    keyword = input("请输入要查找的应用标识或账号关键字: ").strip()
    if not keyword:
        print("关键字不能为空。")
        return
    records = load_records()
    matched = [
        r for r in records
        if keyword in str(r.get("app", "")) or keyword in str(r.get("id", ""))
    ]
    if not matched:
        print(f"未找到包含 '{keyword}' 的记录。")
        return
    print(f"找到 {len(matched)} 条匹配记录：")
    for i, record in enumerate(matched, start=1):
        print(format_record(i, record))


def main():
    """主菜单：循环提供 生成密码 / 查看全部 / 查找记录 / 退出 四项操作。"""
    menu = (
        "\n===== 密码生成与记录管理工具 =====\n"
        "1. 生成新密码\n"
        "2. 查看全部记录\n"
        "3. 按关键字查找记录\n"
        "4. 退出\n"
    )
    while True:
        print(menu)
        choice = input("请选择操作（1-4）: ").strip()
        if choice == "1":
            generate_password()
        elif choice == "2":
            list_records()
        elif choice == "3":
            search_records()
        elif choice == "4":
            print("已退出。")
            break
        else:
            print("输入无效，请输入 1-4 之间的数字。")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n已退出。")
