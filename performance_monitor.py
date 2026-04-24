import requests
import os

# 配置区 (从环境变量读取)
GOOGLE_API_KEY = os.getenv("PSI_API_KEY")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

CONFIG = {
    "targets": [
        {"name": "US-Home", "url": "https://us.mova.tech/"},
        {"name": "US-Product", "url": "https://us.mova.tech/products/mova-lidax-ultra-3000-awd-robotic-lawn-mower"},
        {"name": "CA-Home", "url": "https://ca.mova.tech/"}
    ]
}

def fetch_real_user_data(url):
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={GOOGLE_API_KEY}&strategy=mobile"
    try:
        # 延长到 90 秒防止超时
        response = requests.get(api_url, timeout=90).json()
        field_data = response.get('loadingExperience', {})
        
        if not field_data or 'metrics' not in field_data:
            return {"url": url, "status": "无真实用户数据"}

        lcp_ms = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']['percentile']
        lcp_sec = round(lcp_ms / 1000, 2)
        category = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']['category']
        
        return {"url": url, "lcp": lcp_sec, "category": category, "status": "Success"}
    except Exception as e:
        return {"url": url, "status": "请求超时"}

def send_feishu_text(results):
    # 构造纯文本内容（保持不变）
    report_lines = [
        "🚀 【MOVA 性能监控日报】",
        "--------------------------------"
    ]
    
    valid_results = sorted([r for r in results if 'lcp' in r], key=lambda x: x['lcp'], reverse=True)
    for r in valid_results:
        icon = "🔴" if r['category'] == "SLOW" else "🟢"
        report_lines.append(f"{icon} 项目: {r['name']}\n   LCP: {r['lcp']}s ({r['category']})\n   URL: {r['url']}\n")

    errors = [r for r in results if 'lcp' not in r]
    if errors:
        report_lines.append("⚠️ 以下页面检测失败:")
        for e in errors:
            report_lines.append(f"   - {e['name']}: {e['status']}")

    # ================= 关键改动 =================
    # 某些机器人只需要 text 字段，不需要嵌套在 content 里
    text_content = "\n".join(report_lines)
    
    # 尝试这种最简洁的发送方式
    payload = {
        "text": text_content
    }
    
    # 如果上面的不行，飞书标准的自定义机器人其实是这样的：
    # payload = {"msg_type": "text", "content": {"text": text_content}}
    # 但由于你那边一直返回源码，说明它没识别出 msg_type
    
    print(f"正在发送至飞书...")
    requests.post(FEISHU_WEBHOOK, json=payload)

def main():
    results = []
    for target in CONFIG['targets']:
        data = fetch_real_user_data(target['url'])
        data['name'] = target['name']
        results.append(data)
    
    send_feishu_text(results)

if __name__ == "__main__":
    main()
