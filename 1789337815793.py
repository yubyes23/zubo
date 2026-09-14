import json
from playwright.sync_api import sync_playwright

def get_all_categories_m3u():
    # 定义 8 个分类及其对应的 URL（以 4_101 开始依次递增）
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

        # 递归提取函数
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

        # 依次循环抓取 8 个分类
        for cat_name, cat_url in categories.items():
            print(f"\n----------------------------------------")
            print(f"[*] 正在抓取分类: 【{cat_name}】 -> {cat_url}")
            print(f"----------------------------------------")
            
            category_rooms = []
            seen_ids = set()

            # 监听当前页面的网络接口响应
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
                # 滚动页面以触发接口加载，直到攒够 15 个房间或超时
                for _ in range(4):
                    if len(category_rooms) >= 15:
                        break
                    page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    page.wait_for_timeout(2000)
            except Exception as e:
                print(f"[!] 访问分类 {cat_name} 时发生异常: {e}")

            # 移除当前页面的监听，避免影响下一个分类
            page.remove_listener("response", handle_response)

            # 严格截取前 20 个房间
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

    # ==========================================
    # ⚙️ 生成带 group-title 分组的聚合 M3U 文件
    # ==========================================
    output_file = "douyin_all.m3u"
    FIXED_PREFIX = "http://192.168.0.109/TV/douyin.php?type=rid&rid="
    
    m3u_content = "#EXTM3U\n"
    print(f"\n========================================")
    print(f"[✓] 全部抓取完毕！正在生成聚合 M3U 文件，总计 {len(all_rooms_data)} 个房间：")
    print(f"========================================")
    
    for r in all_rooms_data:
        stream_url = f"{FIXED_PREFIX}{r['room_id']}"
        display_name = f"{r['nickname']} - {r['title']}" if r['nickname'] != "未知主播" else r['title']
        clean_name = display_name.encode('utf-8', 'ignore').decode('utf-8')
        cat_tag = r['category']
        
        # 🔑 核心：写入标准的 group-title 分组标记属性
        m3u_content += f'#EXTINF:-1 tvg-name="{r["nickname"]}" group-title="{cat_tag}", {clean_name}\n{stream_url}\n'

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(m3u_content)
        
    print(f"\n[✓] 完美搞定！聚合 M3U 文件已成功保存到: {output_file}")
    print(f"提示：你可以直接把 {output_file} 拖入 PotPlayer 等支持分组的播放器中播放！")

if __name__ == "__main__":
    get_all_categories_m3u()
