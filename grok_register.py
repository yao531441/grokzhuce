#!/usr/bin/env python3
"""
Grok 注册机 - Playwright 版本
使用浏览器自动化完成注册流程
"""

import os
import sys
import json
import random
import string
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# 导入现有服务
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g import EmailService, UserAgreementService, NsfwSettingsService

console = Console()


class GrokRegister:
    """Grok 注册器"""

    def __init__(
        self,
        chrome_path: Optional[str] = None,
        headless: bool = False,
        output_file: str = "accounts.jsonl",
    ):
        self.chrome_path = chrome_path
        self.headless = headless
        self.output_file = output_file
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 初始化服务
        self.email_service = EmailService()
        self.user_agreement_service = UserAgreementService()
        self.nsfw_service = NsfwSettingsService()

    def generate_random_string(self, length: int = 15) -> str:
        """生成随机字符串"""
        return "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(length)
        )

    def generate_random_name(self) -> str:
        """生成随机姓名"""
        length = random.randint(4, 6)
        return random.choice(string.ascii_uppercase) + "".join(
            random.choice(string.ascii_lowercase) for _ in range(length - 1)
        )

    def save_account(self, account_data: Dict[str, Any]):
        """保存账号信息到 JSONL 文件"""
        account_data["timestamp"] = datetime.now().isoformat()
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(account_data, ensure_ascii=False) + "\n")
        console.print(f"[green]✓[/green] 账号已保存到 {self.output_file}")

    def init_browser(self):
        """初始化浏览器"""
        console.print("[blue]正在启动浏览器...[/blue]")

        self.playwright = sync_playwright().start()

        # 浏览器启动参数
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
        ]

        # 如果指定了 Chrome 路径
        if self.chrome_path and os.path.exists(self.chrome_path):
            browser_type = self.playwright.chromium
            launch_options = {
                "headless": self.headless,
                "args": args,
                "executable_path": self.chrome_path,
            }
        else:
            # 自动检测或使用默认
            browser_type = self.playwright.chromium
            launch_options = {
                "headless": self.headless,
                "args": args,
                "channel": "chrome",  # 尝试使用系统 Chrome
            }

        try:
            self.browser = browser_type.launch(**launch_options)
        except Exception as e:
            console.print(
                f"[yellow]警告: 使用系统 Chrome 失败 ({e})，尝试使用 Playwright 自带 Chromium[/yellow]"
            )
            launch_options.pop("executable_path", None)
            launch_options.pop("channel", None)
            self.browser = browser_type.launch(**launch_options)

        # 创建上下文
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        # 创建页面
        self.page = self.context.new_page()

        # 应用 stealth 插件（新版 API）
        stealth = Stealth()
        stealth.apply_stealth_sync(self.page)

        console.print(f"[green]✓[/green] 浏览器启动成功 (headless={self.headless})")

    def close_browser(self):
        """关闭浏览器"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        console.print("[blue]浏览器已关闭[/blue]")

    def handle_turnstile(self, timeout: int = 30) -> bool:
        """
        处理 Turnstile 验证
        自动尝试，失败时提示人工介入
        """
        console.print("[blue]等待 Turnstile 验证...[/blue]")

        # 等待 Turnstile widget 加载
        try:
            # 检查是否存在 Turnstile iframe
            iframe_locator = self.page.locator(
                'iframe[src*="challenges.cloudflare.com"]'
            ).first
            iframe_exists = iframe_locator.count() > 0

            if not iframe_exists:
                # 检查是否有隐藏的 input 字段（可能已自动完成）
                token_input = self.page.locator(
                    'input[name="cf-turnstile-response"]'
                ).first
                if token_input.count() > 0:
                    token = token_input.input_value()
                    if token:
                        console.print("[green]✓[/green] Turnstile 已自动完成")
                        return True

                console.print(
                    "[yellow]未检测到 Turnstile widget，可能不需要验证[/yellow]"
                )
                return True

            # 尝试自动点击
            console.print("[blue]尝试自动点击 Turnstile checkbox...[/blue]")

            # 获取 iframe
            iframe_element = iframe_locator.element_handle()
            iframe = iframe_element.content_frame()

            if iframe:
                # 尝试点击 checkbox
                checkbox = iframe.locator('input[type="checkbox"]').first
                try:
                    checkbox.click(timeout=5000)
                    console.print("[green]✓[/green] 已自动点击 checkbox")
                except Exception as e:
                    console.print(f"[yellow]自动点击失败: {e}[/yellow]")

            # 等待验证完成（检查 token）
            start_time = time.time()
            while time.time() - start_time < timeout:
                token_input = self.page.locator(
                    'input[name="cf-turnstile-response"]'
                ).first
                if token_input.count() > 0:
                    token = token_input.input_value()
                    if token:
                        console.print("[green]✓[/green] Turnstile 验证成功")
                        return True
                time.sleep(0.5)

            # 超时，提示人工介入
            console.print(
                Panel.fit(
                    "[yellow]Turnstile 验证需要人工介入[/yellow]\n"
                    "请在浏览器中手动完成验证，完成后按回车继续...",
                    title="人工验证",
                    border_style="yellow",
                )
            )
            input()

            # 再次检查
            token_input = self.page.locator('input[name="cf-turnstile-response"]').first
            if token_input.count() > 0:
                token = token_input.input_value()
                if token:
                    console.print("[green]✓[/green] Turnstile 验证完成")
                    return True

            console.print("[red]✗[/red] Turnstile 验证失败")
            return False

        except Exception as e:
            console.print(f"[red]✗[/red] Turnstile 处理异常: {e}")
            return False

    def register_account(self) -> bool:
        """
        注册单个账号
        返回是否成功
        """
        try:
            # 1. 打开注册页面
            console.print("\n[bold blue]=== 开始注册新账号 ===[/bold blue]")
            self.page.goto("https://accounts.x.ai/sign-up", wait_until="networkidle")
            console.print("[green]✓[/green] 页面加载完成")

            # 2. 处理 Turnstile
            if not self.handle_turnstile():
                console.print("[red]✗[/red] Turnstile 验证失败，停止注册")
                return False

            # 3. 创建邮箱
            console.print("[blue]创建临时邮箱...[/blue]")
            jwt, email = self.email_service.create_email()
            if not email:
                console.print("[red]✗[/red] 创建邮箱失败")
                return False
            console.print(f"[green]✓[/green] 邮箱创建成功: {email}")

            # 4. 点击 "Sign up with email" 按钮
            console.print("[blue]点击 Sign up with email 按钮...[/blue]")
            sign_up_email_btn = self.page.locator(
                'button:has-text("Sign up with email")'
            ).first
            if sign_up_email_btn.count() > 0:
                sign_up_email_btn.click()
                console.print("[green]✓[/green] 已点击 Sign up with email")
                # 等待邮箱输入框出现
                self.page.wait_for_selector('input[type="email"]', timeout=10000)

            # 5. 填写邮箱并发送验证码
            console.print("[blue]填写邮箱并发送验证码...[/blue]")
            email_input = self.page.locator('input[type="email"]').first
            email_input.fill(email)

            # 点击发送验证码按钮
            send_code_btn = self.page.locator('button:has-text("Send code")').first
            if send_code_btn.count() == 0:
                send_code_btn = self.page.locator('button:has-text("发送验证码")').first
            send_code_btn.click()
            console.print("[green]✓[/green] 验证码已发送")

            # 5. 获取验证码
            console.print("[blue]等待验证码...[/blue]")
            verify_code = None
            for attempt in range(30):  # 最多等待 60 秒
                verify_code = self.email_service.fetch_verification_code(email)
                if verify_code:
                    break
                time.sleep(2)

            if not verify_code:
                console.print("[red]✗[/red] 获取验证码超时")
                self.email_service.delete_email(email)
                return False
            console.print(f"[green]✓[/green] 验证码获取成功: {verify_code}")

            # 6. 填写验证码
            code_input = self.page.locator(
                'input[placeholder*="code"], input[placeholder*="验证码"]'
            ).first
            code_input.fill(verify_code)

            # 7. 填写密码
            password = self.generate_random_string()
            password_input = self.page.locator('input[type="password"]').first
            password_input.fill(password)
            console.print("[green]✓[/green] 密码已填写")

            # 8. 填写姓名
            first_name = self.generate_random_name()
            last_name = self.generate_random_name()

            first_name_input = self.page.locator(
                'input[placeholder*="First"], input[name*="first"], input[id*="first"]'
            ).first
            last_name_input = self.page.locator(
                'input[placeholder*="Last"], input[name*="last"], input[id*="last"]'
            ).first

            if first_name_input.count() > 0:
                first_name_input.fill(first_name)
            if last_name_input.count() > 0:
                last_name_input.fill(last_name)
            console.print("[green]✓[/green] 姓名已填写")

            # 9. 提交注册
            console.print("[blue]提交注册...[/blue]")
            submit_btn = self.page.locator('button[type="submit"]').first
            submit_btn.click()

            # 等待注册完成
            self.page.wait_for_load_state("networkidle")
            time.sleep(3)

            # 10. 检查是否成功
            current_url = self.page.url
            if "sign-up" in current_url or "error" in current_url.lower():
                console.print("[red]✗[/red] 注册可能失败，请检查页面")
                self.email_service.delete_email(email)
                return False

            console.print("[green]✓[/green] 注册提交成功")

            # 11. 获取 SSO cookie
            cookies = self.context.cookies()
            sso_cookie = None
            for cookie in cookies:
                if cookie["name"] == "sso":
                    sso_cookie = cookie["value"]
                    break

            if not sso_cookie:
                console.print("[red]✗[/red] 未获取到 SSO cookie")
                self.email_service.delete_email(email)
                return False

            console.print(f"[green]✓[/green] SSO 获取成功: {sso_cookie[:20]}...")

            # 12. 自动完成 TOS 和 NSFW 设置
            console.print("[blue]自动完成 TOS 和 NSFW 设置...[/blue]")

            # 获取 sso-rw cookie
            sso_rw_cookie = None
            for cookie in cookies:
                if cookie["name"] == "sso-rw":
                    sso_rw_cookie = cookie["value"]
                    break

            # 接受 TOS
            tos_result = self.user_agreement_service.accept_tos_version(
                sso=sso_cookie,
                sso_rw=sso_rw_cookie or "",
                impersonate="chrome120",
                user_agent=self.page.evaluate("() => navigator.userAgent"),
            )
            if tos_result.get("ok"):
                console.print("[green]✓[/green] TOS 已接受")
            else:
                console.print(
                    f"[yellow]![/yellow] TOS 接受失败: {tos_result.get('error')}"
                )

            # 启用 NSFW
            nsfw_result = self.nsfw_service.enable_nsfw(
                sso=sso_cookie,
                sso_rw=sso_rw_cookie or "",
                impersonate="chrome120",
                user_agent=self.page.evaluate("() => navigator.userAgent"),
            )
            if nsfw_result.get("ok"):
                console.print("[green]✓[/green] NSFW 已启用")
            else:
                console.print(
                    f"[yellow]![/yellow] NSFW 启用失败: {nsfw_result.get('error')}"
                )

            # 启用 Unhinged 模式
            unhinged_result = self.nsfw_service.enable_unhinged(
                sso=sso_cookie,
                impersonate="chrome120",
                user_agent=self.page.evaluate("() => navigator.userAgent"),
            )
            if unhinged_result.get("ok"):
                console.print("[green]✓[/green] Unhinged 模式已启用")
            else:
                console.print(
                    f"[yellow]![/yellow] Unhinged 启用失败: {unhinged_result.get('error')}"
                )

            # 13. 保存账号信息
            account_data = {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "sso": sso_cookie,
                "status": "success",
            }
            self.save_account(account_data)

            # 14. 删除邮箱
            self.email_service.delete_email(email)

            console.print("[bold green]=== 账号注册成功 ===[/bold green]\n")
            return True

        except Exception as e:
            console.print(f"[red]✗[/red] 注册过程异常: {e}")
            import traceback

            traceback.print_exc()
            return False

    def run(self, count: int = 1):
        """运行注册流程"""
        console.print(
            Panel.fit(
                "[bold blue]Grok 注册机[/bold blue]\n"
                f"目标数量: {count}\n"
                f"输出文件: {self.output_file}",
                title="开始运行",
                border_style="blue",
            )
        )

        try:
            self.init_browser()

            for i in range(count):
                console.print(f"\n[bold]--- 第 {i + 1}/{count} 个账号 ---[/bold]")
                success = self.register_account()

                if not success:
                    console.print("[red]注册失败，停止运行[/red]")
                    break

                if i < count - 1:
                    console.print("[blue]等待 5 秒后继续下一个...[/blue]")
                    time.sleep(5)

            console.print("\n[bold green]所有任务完成！[/bold green]")

        except KeyboardInterrupt:
            console.print("\n[yellow]用户中断[/yellow]")
        except Exception as e:
            console.print(f"\n[red]运行异常: {e}[/red]")
            import traceback

            traceback.print_exc()
        finally:
            self.close_browser()


def find_chrome() -> Optional[str]:
    """自动查找 Chrome 可执行文件路径"""
    possible_paths = [
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        # Linux
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]

    for path in possible_paths:
        expanded_path = os.path.expandvars(path)
        if os.path.exists(expanded_path):
            return expanded_path

    return None


def main():
    parser = argparse.ArgumentParser(description="Grok 注册机 - Playwright 版本")
    parser.add_argument(
        "--chrome", type=str, help="Chrome 可执行文件路径（可选，默认自动检测）"
    )
    parser.add_argument(
        "--headless", action="store_true", help="无头模式（不显示浏览器界面）"
    )
    parser.add_argument("--count", type=int, default=1, help="注册数量（默认 1）")
    parser.add_argument(
        "--output",
        type=str,
        default="accounts.jsonl",
        help="输出文件路径（默认 accounts.jsonl）",
    )

    args = parser.parse_args()

    # 确定 Chrome 路径
    chrome_path = args.chrome
    if not chrome_path:
        chrome_path = find_chrome()
        if chrome_path:
            console.print(f"[green]✓[/green] 自动检测到 Chrome: {chrome_path}")
        else:
            console.print(
                "[yellow]未检测到系统 Chrome，将使用 Playwright 自带 Chromium[/yellow]"
            )

    # 创建注册器并运行
    register = GrokRegister(
        chrome_path=chrome_path, headless=args.headless, output_file=args.output
    )

    register.run(count=args.count)


if __name__ == "__main__":
    main()
