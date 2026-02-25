import os
import json
import random
import string
import time
import re
import struct
import threading
import concurrent.futures
import traceback
from urllib.parse import urljoin, urlparse
from curl_cffi import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from g import EmailService, TurnstileService, UserAgreementService, NsfwSettingsService


def print_error(
    context: str, exception: Exception | None = None, details: dict | None = None
):
    """统一错误输出格式"""
    print(f"\n{'=' * 60}")
    print(f"[-] 错误位置: {context}")
    if exception:
        print(f"[-] 异常类型: {type(exception).__name__}")
        print(f"[-] 异常信息: {str(exception)}")
    if details:
        for key, value in details.items():
            print(f"[-] {key}: {value}")
    print(f"[-] 堆栈跟踪:")
    traceback.print_exc()
    print(f"{'=' * 60}\n")


# 加载 .env 文件
load_dotenv()

# 从 .env 获取代理配置（第一优先级）
HTTP_PROXY = os.getenv("HTTP_PROXY", "")
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")

# 构建代理字典
PROXIES = {}
if HTTP_PROXY:
    PROXIES["http"] = HTTP_PROXY
    print(f"[+] 从 .env 加载 HTTP 代理: {HTTP_PROXY}")
if HTTPS_PROXY:
    PROXIES["https"] = HTTPS_PROXY
    print(f"[+] 从 .env 加载 HTTPS 代理: {HTTPS_PROXY}")

# 基础配置
site_url = "https://accounts.x.ai"
DEFAULT_IMPERSONATE = "chrome120"
CHROME_PROFILES = [
    {"impersonate": "chrome110", "version": "110.0.0.0", "brand": "chrome"},
    {"impersonate": "chrome119", "version": "119.0.0.0", "brand": "chrome"},
    {"impersonate": "chrome120", "version": "120.0.0.0", "brand": "chrome"},
    {"impersonate": "edge99", "version": "99.0.1150.36", "brand": "edge"},
    {"impersonate": "edge101", "version": "101.0.1210.47", "brand": "edge"},
]


def get_random_chrome_profile():
    profile = random.choice(CHROME_PROFILES)
    if profile.get("brand") == "edge":
        chrome_major = profile["version"].split(".")[0]
        chrome_version = f"{chrome_major}.0.0.0"
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_version} Safari/537.36 Edg/{profile['version']}"
        )
    else:
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{profile['version']} Safari/537.36"
        )
    return profile["impersonate"], ua


# 动态获取的全局变量
config = {
    "site_key": "0x4AAAAAAAhr9JGVDZbrZOo0",
    "action_id": None,
    "state_tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22(app)%22%2C%7B%22children%22%3A%5B%22(auth)%22%2C%7B%22children%22%3A%5B%22sign-up%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2C%22%2Fsign-up%22%2C%22refresh%22%5D%7D%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D",
}

post_lock = threading.Lock()
file_lock = threading.Lock()
success_count = 0
start_time = time.time()
target_count = 100
stop_event = threading.Event()
output_file = None


def generate_random_name() -> str:
    length = random.randint(4, 6)
    return random.choice(string.ascii_uppercase) + "".join(
        random.choice(string.ascii_lowercase) for _ in range(length - 1)
    )


def generate_random_string(length: int = 15) -> str:
    return "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(length)
    )


def encode_grpc_message(field_id, string_value):
    key = (field_id << 3) | 2
    value_bytes = string_value.encode("utf-8")
    length = len(value_bytes)
    payload = struct.pack("B", key) + struct.pack("B", length) + value_bytes
    return b"\x00" + struct.pack(">I", len(payload)) + payload


def encode_grpc_message_verify(email, code):
    p1 = (
        struct.pack("B", (1 << 3) | 2)
        + struct.pack("B", len(email))
        + email.encode("utf-8")
    )
    p2 = (
        struct.pack("B", (2 << 3) | 2)
        + struct.pack("B", len(code))
        + code.encode("utf-8")
    )
    payload = p1 + p2
    return b"\x00" + struct.pack(">I", len(payload)) + payload


def send_email_code_grpc(session, email):
    url = f"{site_url}/auth_mgmt.AuthManagement/CreateEmailValidationCode"
    data = encode_grpc_message(1, email)
    headers = {
        "content-type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "x-user-agent": "connect-es/2.1.1",
        "origin": site_url,
        "referer": f"{site_url}/sign-up?redirect=grok-com",
    }
    try:
        res = session.post(url, data=data, headers=headers, timeout=15)
        if res.status_code != 200:
            print_error(
                f"发送验证码失败: {email}",
                details={
                    "状态码": res.status_code,
                    "响应头": dict(res.headers),
                    "响应内容前200字符": res.text[:200] if res.text else "空",
                },
            )
            return False
        return True
    except Exception as e:
        print_error(f"发送验证码异常: {email}", e, {"URL": url})
        return False


def verify_email_code_grpc(session, email, code):
    url = f"{site_url}/auth_mgmt.AuthManagement/VerifyEmailValidationCode"
    data = encode_grpc_message_verify(email, code)
    headers = {
        "content-type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "x-user-agent": "connect-es/2.1.1",
        "origin": site_url,
        "referer": f"{site_url}/sign-up?redirect=grok-com",
    }
    try:
        res = session.post(url, data=data, headers=headers, timeout=15)
        if res.status_code != 200:
            print_error(
                f"验证验证码失败: {email}",
                details={
                    "状态码": res.status_code,
                    "验证码": code[:3] + "***" if code else "空",
                    "响应头": dict(res.headers),
                    "响应内容前200字符": res.text[:200] if res.text else "空",
                },
            )
            return False
        return True
    except Exception as e:
        print_error(
            f"验证验证码异常: {email}",
            e,
            {"URL": url, "验证码": code[:3] + "***" if code else "空"},
        )
        return False


def register_single_thread():
    # 错峰启动，防止瞬时并发过高
    time.sleep(random.uniform(0, 5))

    email_service = None
    turnstile_service = None
    user_agreement_service = None
    nsfw_service = None

    try:
        email_service = EmailService()
    except Exception as e:
        print_error("EmailService初始化失败", e)
        return

    try:
        turnstile_service = TurnstileService()
    except Exception as e:
        print_error("TurnstileService初始化失败", e)
        return

    try:
        user_agreement_service = UserAgreementService()
    except Exception as e:
        print_error("UserAgreementService初始化失败", e)
        return

    try:
        nsfw_service = NsfwSettingsService()
    except Exception as e:
        print_error("NsfwSettingsService初始化失败", e)
        return

    # 修正：直接从 config 获取
    final_action_id = config["action_id"]
    if not final_action_id:
        print("[-] 线程退出：缺少 Action ID")
        return

    current_email = None  # 追踪当前邮箱，确保异常时能删除

    while True:
        try:
            if stop_event.is_set():
                if current_email:
                    try:
                        email_service.delete_email(current_email)
                    except:
                        pass
                return
            impersonate_fingerprint, account_user_agent = get_random_chrome_profile()
            with requests.Session(
                impersonate=impersonate_fingerprint, proxies=PROXIES
            ) as session:
                # 预热连接
                try:
                    session.get(site_url, timeout=10)
                except:
                    pass

                password = generate_random_string()

                try:
                    jwt, email = email_service.create_email()
                    current_email = email
                except Exception as e:
                    print(f"[-] 邮箱服务抛出异常: {e}")
                    jwt, email, current_email = None, None, None

                if not email:
                    time.sleep(5)
                    continue

                if stop_event.is_set():
                    email_service.delete_email(email)
                    current_email = None
                    return

                print(f"[*] 开始注册: {email}")

                # Step 1: 发送验证码
                if not send_email_code_grpc(session, email):
                    print(f"[-] {email} 发送验证码失败")
                    email_service.delete_email(email)
                    current_email = None
                    time.sleep(5)
                    continue

                # Step 2: 获取验证码
                try:
                    verify_code = email_service.fetch_verification_code(email)
                except Exception as e:
                    print_error(f"获取验证码异常: {email}", e)
                    verify_code = None

                if not verify_code:
                    print(f"[-] {email} 获取验证码失败（返回空或异常）")
                    try:
                        email_service.delete_email(email)
                    except Exception as del_e:
                        print_error(f"删除邮箱失败: {email}", del_e)
                    current_email = None
                    continue

                # Step 3: 验证验证码
                if not verify_email_code_grpc(session, email, verify_code):
                    print(f"[-] {email} 验证验证码失败")
                    email_service.delete_email(email)
                    current_email = None
                    continue

                # Step 4: 注册重试循环
                for attempt in range(3):
                    if stop_event.is_set():
                        email_service.delete_email(email)
                        current_email = None
                        return
                    try:
                        task_id = turnstile_service.create_task(
                            site_url, config["site_key"]
                        )
                        token = turnstile_service.get_response(task_id)
                    except Exception as e:
                        print_error(
                            f"验证码服务异常: {email}", e, {"attempt": attempt + 1}
                        )
                        continue

                    if not token or token == "CAPTCHA_FAIL":
                        print(
                            f"[-] {email} 验证码token获取失败 (attempt {attempt + 1}/3)"
                        )
                        continue

                    headers = {
                        "user-agent": account_user_agent,
                        "accept": "text/x-component",
                        "content-type": "text/plain;charset=UTF-8",
                        "origin": site_url,
                        "referer": f"{site_url}/sign-up",
                        "cookie": f"__cf_bm={session.cookies.get('__cf_bm', '')}",
                        "next-router-state-tree": config["state_tree"],
                        "next-action": final_action_id,
                    }
                    payload = [
                        {
                            "emailValidationCode": verify_code,
                            "createUserAndSessionRequest": {
                                "email": email,
                                "givenName": generate_random_name(),
                                "familyName": generate_random_name(),
                                "clearTextPassword": password,
                                "tosAcceptedVersion": "$undefined",
                            },
                            "turnstileToken": token,
                            "promptOnDuplicateEmail": True,
                        }
                    ]

                    res = None
                    try:
                        with post_lock:
                            res = session.post(
                                f"{site_url}/sign-up", json=payload, headers=headers
                            )
                    except Exception as e:
                        print_error(
                            f"注册POST请求失败: {email}",
                            e,
                            {"URL": f"{site_url}/sign-up", "attempt": attempt + 1},
                        )
                        time.sleep(3)
                        continue

                    if res.status_code == 200:
                        match = re.search(
                            r'(https://[^" \s]+set-cookie\?q=[^:" \s]+)1:', res.text
                        )
                        if not match:
                            print_error(
                                f"未找到set-cookie链接: {email}",
                                details={
                                    "响应状态码": res.status_code,
                                    "响应内容长度": len(res.text),
                                    "响应内容前500字符": res.text[:500]
                                    if res.text
                                    else "空",
                                },
                            )
                            email_service.delete_email(email)
                            current_email = None
                            break
                        if match:
                            verify_url = match.group(1)
                            try:
                                verify_res = session.get(
                                    verify_url, allow_redirects=True
                                )
                            except Exception as e:
                                print_error(
                                    f"验证URL访问失败: {email}",
                                    e,
                                    {"verify_url": verify_url[:50] + "..."},
                                )
                                email_service.delete_email(email)
                                current_email = None
                                break

                            sso = session.cookies.get("sso")
                            sso_rw = session.cookies.get("sso-rw")
                            if not sso:
                                print_error(
                                    f"未获取到SSO cookie: {email}",
                                    details={
                                        "所有cookies": dict(session.cookies),
                                        "verify_url": verify_url[:50] + "...",
                                        "验证响应状态": verify_res.status_code
                                        if "verify_res" in dir()
                                        else "未知",
                                    },
                                )
                                email_service.delete_email(email)
                                current_email = None
                                break

                            try:
                                tos_result = user_agreement_service.accept_tos_version(
                                    sso=sso,
                                    sso_rw=sso_rw or "",
                                    impersonate=impersonate_fingerprint,
                                    user_agent=account_user_agent,
                                )
                                tos_hex = tos_result.get("hex_reply") or ""
                                if not tos_result.get("ok") or not tos_hex:
                                    print_error(
                                        f"TOS接受失败: {email}",
                                        details={
                                            "TOS结果": tos_result,
                                            "SSO前20字符": sso[:20] if sso else "空",
                                        },
                                    )
                                    email_service.delete_email(email)
                                    current_email = None
                                    break
                            except Exception as e:
                                print_error(
                                    f"TOS接受异常: {email}",
                                    e,
                                    {"SSO": sso[:20] if sso else "空"},
                                )
                                email_service.delete_email(email)
                                current_email = None
                                break

                            try:
                                nsfw_result = nsfw_service.enable_nsfw(
                                    sso=sso,
                                    sso_rw=sso_rw or "",
                                    impersonate=impersonate_fingerprint,
                                    user_agent=account_user_agent,
                                )
                                nsfw_hex = nsfw_result.get("hex_reply") or ""
                                if not nsfw_result.get("ok") or not nsfw_hex:
                                    print_error(
                                        f"NSFW设置失败: {email}",
                                        details={
                                            "NSFW结果": nsfw_result,
                                            "SSO前20字符": sso[:20] if sso else "空",
                                        },
                                    )
                                    email_service.delete_email(email)
                                    current_email = None
                                    break
                            except Exception as e:
                                print_error(
                                    f"NSFW设置异常: {email}",
                                    e,
                                    {"SSO": sso[:20] if sso else "空"},
                                )
                                email_service.delete_email(email)
                                current_email = None
                                break

                            # 立即进行二次验证 (enable_unhinged)
                            try:
                                unhinged_result = nsfw_service.enable_unhinged(sso)
                                unhinged_ok = unhinged_result.get("ok", False)
                            except Exception as e:
                                print_error(f"Unhinged设置异常: {email}", e)
                                unhinged_ok = False

                            with file_lock:
                                global success_count
                                if success_count >= target_count:
                                    if not stop_event.is_set():
                                        stop_event.set()
                                    print(f"[*] 已达到目标数量，删除邮箱: {email}")
                                    email_service.delete_email(email)
                                    current_email = None
                                    break
                                if not output_file:
                                    print_error(
                                        "输出文件未设置", details={"email": email}
                                    )
                                    email_service.delete_email(email)
                                    current_email = None
                                    break
                                try:
                                    with open(output_file, "a") as f:
                                        f.write(sso + "\n")
                                except Exception as write_err:
                                    print_error(
                                        f"写入文件失败: {email}",
                                        write_err,
                                        {
                                            "输出文件": output_file,
                                            "SSO": sso[:20] if sso else "空",
                                        },
                                    )
                                    email_service.delete_email(email)
                                    current_email = None
                                    break

                            nsfw_result = nsfw_service.enable_nsfw(
                                sso=sso,
                                sso_rw=sso_rw or "",
                                impersonate=impersonate_fingerprint,
                                user_agent=account_user_agent,
                            )
                            nsfw_hex = nsfw_result.get("hex_reply") or ""
                            if not nsfw_result.get("ok") or not nsfw_hex:
                                print(f"[-] {email} NSFW设置失败: {nsfw_result}")
                                email_service.delete_email(email)
                                current_email = None
                                break

                            # 立即进行二次验证 (enable_unhinged)
                            try:
                                unhinged_result = nsfw_service.enable_unhinged(sso)
                                unhinged_ok = unhinged_result.get("ok", False)
                            except Exception as e:
                                print_error(f"Unhinged设置异常: {email}", e)
                                unhinged_ok = False

                            with file_lock:
                                if success_count >= target_count:
                                    if not stop_event.is_set():
                                        stop_event.set()
                                    print(f"[*] 已达到目标数量，删除邮箱: {email}")
                                    email_service.delete_email(email)
                                    current_email = None
                                    break
                                try:
                                    with open(output_file, "a") as f:
                                        f.write(sso + "\n")
                                except Exception as write_err:
                                    print(f"[-] 写入文件失败: {write_err}")
                                    email_service.delete_email(email)
                                    current_email = None
                                    break
                                success_count += 1
                                avg = (time.time() - start_time) / success_count
                                nsfw_tag = "✓" if unhinged_ok else "✗"
                                print(
                                    f"[✓] 注册成功: {success_count}/{target_count} | {email} | SSO: {sso[:15]}... | 平均: {avg:.1f}s | NSFW: {nsfw_tag}"
                                )
                                email_service.delete_email(email)
                                current_email = None
                                if (
                                    success_count >= target_count
                                    and not stop_event.is_set()
                                ):
                                    stop_event.set()
                                    print(
                                        f"[*] 已达到目标数量: {success_count}/{target_count}，停止新注册"
                                    )
                            break  # 跳出 for 循环，继续 while True 注册下一个

                    time.sleep(3)
                else:
                    # 如果重试 3 次都失败 (for 循环没有被 break)
                    email_service.delete_email(email)
                    current_email = None
                    time.sleep(5)

        except Exception as e:
            print_error(
                "注册流程主异常",
                e,
                {
                    "当前邮箱": current_email[:20] + "..."
                    if current_email and len(current_email) > 20
                    else current_email,
                    "线程状态": "已停止" if stop_event.is_set() else "运行中",
                },
            )
            # 异常时确保删除邮箱
            if current_email:
                try:
                    email_service.delete_email(current_email)
                except Exception as del_e:
                    print_error(f"异常时删除邮箱失败: {current_email}", del_e)
                current_email = None
            time.sleep(5)


def main():
    print("=" * 60 + "\nGrok 注册机\n" + "=" * 60)

    # 打印调试信息
    print(f"[*] 调试信息:")
    print(f"    - 目标站点: {site_url}")
    print(f"    - 默认浏览器指纹: {DEFAULT_IMPERSONATE}")
    print(f"    - 代理状态: {'已启用' if PROXIES else '未启用'}")
    if PROXIES:
        print(f"    - HTTP代理: {PROXIES.get('http', '未设置')[:30]}...")
        print(f"    - HTTPS代理: {PROXIES.get('https', '未设置')[:30]}...")
    print(f"    - 初始site_key: {config['site_key'][:20]}...")
    print(f"    - 初始action_id: {config['action_id']}")

    # 1. 扫描参数
    print("\n[*] 正在初始化...")
    start_url = f"{site_url}/sign-up"
    with requests.Session(impersonate=DEFAULT_IMPERSONATE) as s:
        try:
            html = s.get(start_url).text
            # Key
            key_match = re.search(r'sitekey":"(0x4[a-zA-Z0-9_-]+)"', html)
            if key_match:
                config["site_key"] = key_match.group(1)
                print(f"[+] 找到 site_key: {config['site_key'][:20]}...")
            else:
                print("[-] 警告: 未找到 site_key")
            # Tree
            tree_match = re.search(r'next-router-state-tree":"([^"]+)"', html)
            if tree_match:
                config["state_tree"] = tree_match.group(1)
                print(f"[+] 找到 state_tree: {config['state_tree'][:50]}...")
            else:
                print("[-] 警告: 未找到 state_tree")
            # Action ID
            soup = BeautifulSoup(html, "html.parser")
            js_urls = [
                urljoin(start_url, script["src"])
                for script in soup.find_all("script", src=True)
                if "_next/static" in script["src"]
            ]
            print(f"[*] 扫描 {len(js_urls)} 个JS文件查找 Action ID...")
            for js_url in js_urls:
                js_content = s.get(js_url).text
                match = re.search(r"7f[a-fA-F0-9]{40}", js_content)
                if match:
                    config["action_id"] = match.group(0)
                    print(f"[+] Action ID: {config['action_id']}")
                    break
        except Exception as e:
            print_error(
                "初始化扫描失败",
                e,
                {
                    "目标URL": start_url,
                    "代理配置": "已启用" if PROXIES else "未启用",
                    "当前配置": config,
                },
            )
            return

    if not config["action_id"]:
        print_error(
            "关键配置缺失",
            details={
                "错误": "未找到 Action ID",
                "site_key": config.get("site_key", "未设置"),
                "state_tree": config.get("state_tree", "未设置")[:50] + "..."
                if config.get("state_tree")
                else "未设置",
                "已扫描JS文件数": len(js_urls) if "js_urls" in dir() else "未知",
            },
        )
        return

    # 2. 启动
    try:
        t = int(input("\n并发数 (默认1): ").strip() or 1)
    except:
        t = 1

    try:
        total = int(input("注册数量 (默认2): ").strip() or 2)
    except:
        total = 2

    global target_count, output_file
    target_count = max(1, total)

    from datetime import datetime

    os.makedirs("keys", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"keys/grok_{timestamp}_{target_count}.txt"

    print(f"[*] 启动 {t} 个线程，目标 {target_count} 个")
    print(f"[*] 输出: {output_file}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=t) as executor:
        futures = [executor.submit(register_single_thread) for _ in range(t)]
        concurrent.futures.wait(futures)


if __name__ == "__main__":
    main()
