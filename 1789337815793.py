import os
import json
import requests
from playwright.sync_api import sync_playwright

def upload_to_cloudflare_kv(m3u_content):
    # 使用 .strip() 自动清理掉可能存在的空格和换行符
    account_id = os.environ.get("CF_ACCOUNT_ID", "").strip()
    namespace_id = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
    api_token = os.environ.get("CF_API_TOKEN", "").strip()
    
    if not all([account_id, namespace_id, api_token]):
        print("[!] 警告: 未检测到 Cloudflare KV 环境变量，跳过 KV 上传。")
        return

    key_name = "douyin_all.m3u"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key_name}"
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    
    print(f"[*] 正在将 M3U 内容上传到 Cloudflare KV...")
    try:
        response = requests.put(url, headers=headers, data=m3u_content.encode("utf-8"))
        if response.status_code == 200:
            print("[✓] 成功：已实时同步到 Cloudflare KV！")
        else:
            print(f"[!] 上传到 KV 失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[!] 连接 Cloudflare KV API 发生异常: {e}")
def get_all_categories_m3u():
    categories = {
        "聊天": "https://live.douyin.com/categorynew/4_101",
        "音乐": "https://live.douyin.com/categorynew/4_102",
        "游戏": "https://live.douyin.com/categorynew/4_103",
        "二次元": "https://live.douyin.com/categorynew/4_104",
        "舞蹈": "https://live.douyin.com/categorynew/4_105",
        "文化": "https://live.douyin.com/categorynew/4_106",
        "生活": "https://live.douyin.com/categorynew/4_107",
        "运动": "https://live.douyin.com/categorynew/4_108",
    }

    all_rooms_data = []

    with sync_playwright() as p:
        print("[*] 正在启动浏览器...")
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def extract_rooms(data, rooms_list, seen_ids):
            if isinstance(data, dict):
                title = data.get("title")
                if title:
                    room_id = data.get("web_rid")
                    if not room_id and isinstance(data.get("owner"), dict):
                        room_id = data["owner"].get("web_rid")
                    if not room_id and isinstance(data.get("room"), dict):
                        room_id = data["room"].get("web_rid") or data["room"].get("id_str")
                    if not room_id:
                        room_id = data.get("id_str") or data.get("room_id")
                
                    if room_id and str(room_id).isdigit() and len(str(room_id)) > 4:
                        room_id_str = str(room_id)
                        if room_id_str not in seen_ids:
                            seen_ids.add(room_id_str)
                            nickname = "未知主播"
                            owner = data.get("owner") or data.get("author")
                            if isinstance(owner, dict):
                                nickname = owner.get("nickname", "未知主播")
                            elif isinstance(data.get("room"), dict):
                                sub_owner = data["room"].get("owner")
                                if isinstance(sub_owner, dict):
                                    nickname = sub_owner.get("nickname", "未知主播")
                            
                            rooms_list.append({
                                "room_id": room_id_str,
                                "title": title,
                                "nickname": nickname
                            })
                for k, v in data.items():
                    extract_rooms(v, rooms_list, seen_ids)
            elif isinstance(data, list):
                for item in data:
                    extract_rooms(item, rooms_list, seen_ids)

        for cat_name, cat_url in categories.items():
            print(f"\n----------------------------------------")
            print(f"[*] 正在抓取分类: 【{cat_name}】 -> {cat_url}")
            print(f"----------------------------------------")
            
            category_rooms = []
            seen_ids = set()

            def handle_response(response):
                if "json" in response.headers.get("content-type", ""):
                    try:
                        json_data = response.json()
                        extract_rooms(json_data, category_rooms, seen_ids)
                    except Exception:
                        pass

            page.on("response", handle_response)

            try:
                page.goto(cat_url, timeout=60000, wait_until="domcontentloaded")
                for _ in range(4):
                    if len(category_rooms) >= 15:
                        break
                    page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    page.wait_for_timeout(2000)
            except Exception as e:
                print(f"[!] 访问分类 {cat_name} 时发生异常: {e}")

            page.remove_listener("response", handle_response)

            limited_rooms = category_rooms[:15]
            print(f"[✓] 分类【{cat_name}】成功捕获 {len(limited_rooms)} 个房间：")
            
            for r in limited_rooms:
                all_rooms_data.append({
                    "category": cat_name,
                    "room_id": r["room_id"],
                    "title": r["title"],
                    "nickname": r["nickname"]
                })
                print(f"    -> 短ID: {r['room_id']} | 主播: {r['nickname']} | 标题: {r['title']}")

        browser.close()

    # 组装 M3U 文本内容
    FIXED_PREFIX = "http://192.168.0.109/TV/douyin.php?type=rid&rid="
    m3u_content = "#EXTM3U\n"
    
    print(f"\n========================================")
    print(f"[✓] 全部抓取完毕！共计 {len(all_rooms_data)} 个房间")
    print(f"========================================")
    
    for r in all_rooms_data:
        stream_url = f"{FIXED_PREFIX}{r['room_id']}"
        display_name = f"{r['nickname']} - {r['title']}" if r['nickname'] != "未知主播" else r['title']
        clean_name = display_name.encode('utf-8', 'ignore').decode('utf-8')
        cat_tag = r['category']
        
        m3u_content += f'#EXTINF:-1 tvg-name="{r["nickname"]}" group-title="{cat_tag}", {clean_name}\n{stream_url}\n'

    # 直接上传到 Cloudflare KV
    upload_to_cloudflare_kv(m3u_content)

if __name__ == "__main__":
    get_all_categories_m3u()
