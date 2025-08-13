# douyin.py
import time
import re
import html
from playwright.sync_api import sync_playwright

def get_stream_info(douyin_id: str, chrome_path: str, proxy_config: dict, wait_time: int) -> tuple[str | None, str | None]:
    """
    使用 Playwright 访问抖音直播间，获取 FLV 直播流地址和直播标题。

    Args:
        douyin_id (str): 抖音主播的房间ID。
        chrome_path (str): 浏览器可执行档路径。
        proxy_config (dict): 代理设定字典，包含 'server' 和 'username', 'password' (可选)。
        wait_time (int): 页面加载后的等待时间（秒）。

    Returns:
        tuple[str | None, str | None]: (flv_url, title) 或 (None, None)
    """
    url = f"https://live.douyin.com/{douyin_id}"
    
    try:
        with sync_playwright() as p:
            launch_options = {
                "headless": True,
                "executable_path": chrome_path
            }
            # 如果提供了代理伺服器地址，则加入代理设定
            if proxy_config and proxy_config.get("server"):
                launch_options["proxy"] = proxy_config
                print(f"LOG:INFO:抓流模组将使用代理: {proxy_config.get('server')}")

            browser = p.chromium.launch(**launch_options)
            page = browser.new_page()

            print(f"LOG:INFO:正在导航至抖音直播页: {url}")
            page.goto(url, timeout=60000)
            
            print(f"LOG:INFO:页面初步加载完成，等待 {wait_time} 秒以确保动态内容渲染...")
            time.sleep(wait_time)
            
            html_content = page.content()
            
            # 从 HTML 中正则匹配 FLV 流地址
            flv_match = re.search(r'(https://[^\s"]+\.flv[^\s"]+)', html_content)
            flv_url = None
            if flv_match:
                # 进行 HTML 反转义，并去除可能的引号污染
                flv_url = html.unescape(flv_match.group(1).split('"')[0])

            # 获取页面标题
            page_title_full = page.title()
            title = page_title_full.split(" - 抖音")[0] if " - 抖音" in page_title_full else page_title_full
            
            browser.close()
            
            if flv_url:
                print(f"LOG:INFO:成功获取到直播流地址。")
            else:
                print("LOG:WARN:未能在页面中找到 FLV 直播流地址。")
                
            if title:
                print(f"LOG:INFO:成功获取到直播标题: {title}")
            else:
                 print("LOG:WARN:未能获取到有效的直播标题。")

            return flv_url, title
            
    except Exception as e:
        print(f"LOG:ERROR:抖音抓流过程中发生严重错误: {e}")
        return None, None
