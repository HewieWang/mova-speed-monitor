import requests
import os
import time
import json

# 配置区
GOOGLE_API_KEY = os.getenv("PSI_API_KEY")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
CACHE_FILE = "last_results.json" # 缓存文件名

CONFIG = {
    "targets": [
        {"name": "US-Home", "url": "https://us.mova.tech/"},
        {"name": "US-EasterEgg", "url": "https://us.mova.tech/pages/easter-egg-hunt"},
        {"name": "CA-EasterEgg", "url": "https://ca.mova.tech/pages/easter-egg-hunt"},
        {"name": "US-GroupBuy", "url": "https://us.mova.tech/pages/group-buying"},
        {"name": "CA-GroupBuy", "url": "https://ca.mova.tech/pages/group-buying"},
        {"name": "US-BestOffer", "url": "https://us.mova.tech/pages/deals"},
        {"name": "CA-BestOffer", "url": "https://ca.mova.tech/pages/deals"},
        {"name": "US-Blog", "url": "https://us.mova.tech/blogs/cleaning-tips"},
        {"name": "CA-Blog", "url": "https://ca.mova.tech/blogs/cleaning-tips"},
        {"name": "CA-Home", "url": "https://ca.mova.tech/"},
        {"name": "US-V50", "url": "https://us.mova.tech/products/mova-v50-ultra-complete-robot-vacuum"},
        {"name": "US-X10", "url": "https://us.mova.tech/products/mova-rover-x10-robotic-pool-cleaner"},
        {"name": "US-1000", "url": "https://us.mova.tech/products/mova-lidax-ultra-1000-robot-lawn-mower"},
        {"name": "CA-V50", "url": "https://ca.mova.tech/products/mova-v50-ultra-complete-robot-vacuum"},
        {"name": "CA-X10", "url": "https://ca.mova.tech/products/mova-rover-x10-robotic-pool-cleaner"},
        {"name": "CA-1000", "url": "https://ca.mova.tech/products/mova-lidax-ultra-1000-robot-lawn-mower"}
    ]
}

def load_cache():
    """读取上一次的运行结果"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(results):
    """保存本次成功的结果到缓存"""
    cache_data = {}
    for r in results:
        # 只有真正获取到 LCP 的才存入缓存
        if r.get('status') == "Success" and r.get('lcp'):
            cache_data[r['url']] = r
            
    if cache_data:
        # 合并旧缓存，确保这次没跑成功的 URL 还能保留上上次的数据
        old_cache = load_cache()
        old_cache.update(cache_data)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(old_cache, f, ensure_ascii=False, indent=2)

def fetch_real_user_data(url, cache):
    """抓取数据，失败则回退到 cache"""
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={GOOGLE_API_KEY}&strategy=mobile"
    
    result = None
    try:
        response = requests.get(api_url, timeout=120)
        if response.status_code == 200:
            data = response.json()
            field_data = data.get('loadingExperience', {})
            if field_data and 'metrics' in field_data:
                metrics = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']
                result = {
                    "url": url, 
                    "lcp": round(metrics['percentile'] / 1000, 2), 
                    "category": metrics['category'], 
                    "status": "Success",
                    "is_cache": False
                }
    except Exception as e:
        print(f"请求 {url} 异常: {str(e)[:30]}")

    # 如果请求失败或没数据，尝试使用缓存
    if not result:
        if url in cache:
            result = cache[url].copy()
            result["is_cache"] = True # 标记这是缓存数据
            result["status"] = "Success (来自历史)"
        else:
            result = {"url": url, "status": "请求失败且无缓存", "lcp": None, "is_cache": False}
            
    return result

def build_card_payload(results):
    """构造飞书卡片"""
    any_slow = any(r.get('category') == "SLOW" for r in results if r.get('lcp'))
    header_color = "red" if any_slow else "blue"
    
    elements = []
    for r in results:
        if r['lcp']:
            icon = "🔴" if r['category'] == "SLOW" else "🟡" if r['category'] == "AVERAGE" else "🟢"
            cache_tag = " ⚠️(历史数据)" if r.get('is_cache') else ""
            status_text = f"**{r['lcp']}s** ({r['category']}){cache_tag}"
        else:
            icon = "⚪"
            status_text = f"*{r['status']}*"
            
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"{icon} **{r['name']}**\n指标: {status_text}\n链接: [点击访问]({r['url']})"
            }
        })
        elements.append({"tag": "hr"})

    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"统计时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"}]
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "template": header_color,
                "title": {"content": "🚀 MOVA 性能监控日报", "tag": "plain_text"}
            },
            "elements": elements
        }
    }

def send_to_feishu(payload):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        requests.post(FEISHU_WEBHOOK, data=json.dumps(payload), headers=headers, timeout=10)
    except:
        pass

def main():
    cache = load_cache()
    results = []
    for target in CONFIG['targets']:
        data = fetch_real_user_data(target['url'], cache)
        data['name'] = target['name']
        results.append(data)
    
    save_cache(results) # 保存最新的成功数据
    payload = build_card_payload(results)
    send_to_feishu(payload)

if __name__ == "__main__":
    main()
