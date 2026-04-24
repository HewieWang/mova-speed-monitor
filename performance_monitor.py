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
    # 手动构造一个漂亮的纯文本报告
    report_lines = [
        "🚀 【MOVA 性能监控日报】",
        "--------------------------------"
    ]
    
    # 排序：慢的在前
    valid_results = sorted([r for r in results if 'lcp' in r], key=lambda x: x['lcp'], reverse=True)
    
    for r in valid_results:
        icon = "🔴" if r['category'] == "SLOW" else "🟢"
        report_lines.append(f"{icon} 项目: {r['name']}")
        report_lines.append(f"   LCP: {r['lcp']}s ({r['category']})")
        report_lines.append(f"   URL: {r['url']}")
        report_lines.append("")

    errors = [r for r in results if 'lcp' not in r]
    if errors:
        report_lines.append("⚠️ 以下页面检测失败:")
        for e in errors:
            report_lines.append(f"   - {e['name']}: {e['status']}")

    # 构造飞书最基础的 text 类型消息
    payload = {
        "msg_type": "text",
        "content": {
            "text": "\n".join(report_lines) # 将列表合并为带换行的长字符串
        }
    }
    
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
