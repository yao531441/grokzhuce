"""邮箱服务类 - 适配 freemail API"""

import os
import time
import requests
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning

# 禁用 SSL 警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class EmailService:
    def __init__(self):
        load_dotenv()
        self.worker_domain = os.getenv("WORKER_DOMAIN")
        self.freemail_token = os.getenv("FREEMAIL_TOKEN")
        if not all([self.worker_domain, self.freemail_token]):
            raise ValueError("Missing: WORKER_DOMAIN or FREEMAIL_TOKEN")
        self.base_url = f"https://{self.worker_domain}"
        self.headers = {"Authorization": f"Bearer {self.freemail_token}"}

        # 从环境变量获取代理配置
        self.proxies = self._get_proxies()

    def _get_proxies(self):
        """获取代理配置"""
        # 优先使用环境变量中的代理配置
        http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

        # 如果没有设置代理，检查 WPAD 配置
        if not http_proxy and not https_proxy:
            # 尝试获取系统代理（Windows）
            try:
                import urllib.request

                # 检查是否有 WPAD 配置
                proxy_handler = urllib.request.ProxyHandler()
                opener = urllib.request.build_opener(proxy_handler)
                # 这里只是初始化，实际代理会在请求时自动获取
            except:
                pass

        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies["http"] = http_proxy
            if https_proxy:
                proxies["https"] = https_proxy
            print(f"[*] 使用代理: {proxies}")
            return proxies

        return None

    def create_email(self):
        """创建临时邮箱 GET /api/generate"""
        try:
            res = requests.get(
                f"{self.base_url}/api/generate",
                headers=self.headers,
                timeout=10,
                proxies=self.proxies,
                verify=False,  # 禁用 SSL 验证以避免证书问题
            )
            if res.status_code == 200:
                email = res.json().get("email")
                return email, email  # 兼容原接口 (jwt, email)
            print(f"[-] 创建邮箱失败: {res.status_code} - {res.text}")
            return None, None
        except Exception as e:
            print(f"[-] 创建邮箱失败: {e}")
            return None, None

    def fetch_verification_code(self, email, max_attempts=30):
        """轮询获取验证码 GET /api/emails?mailbox=xxx"""
        for _ in range(max_attempts):
            try:
                res = requests.get(
                    f"{self.base_url}/api/emails",
                    params={"mailbox": email},
                    headers=self.headers,
                    timeout=10,
                    proxies=self.proxies,
                    verify=False,
                )
                if res.status_code == 200:
                    emails = res.json()
                    if emails and emails[0].get("verification_code"):
                        code = emails[0]["verification_code"]
                        return code.replace("-", "")
            except Exception as e:
                print(f"[-] 获取验证码异常: {e}")
            time.sleep(2)
        return None

    def delete_email(self, address):
        """删除邮箱 DELETE /api/mailboxes?address=xxx"""
        try:
            res = requests.delete(
                f"{self.base_url}/api/mailboxes",
                params={"address": address},
                headers=self.headers,
                timeout=10,
                proxies=self.proxies,
                verify=False,
            )
            return res.status_code == 200 and res.json().get("success")
        except Exception as e:
            print(f"[-] 删除邮箱异常: {e}")
            return False
