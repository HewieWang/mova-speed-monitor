import requests
import os,time,json

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
    # 尝试 2 次
    for i in range(2):
        try:
            api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={GOOGLE_API_KEY}&strategy=mobile"
            response = requests.get(api_url, timeout=120).json() # 增加到 120 秒
            
            field_data = response.get('loadingExperience', {})
            if field_data and 'metrics' in field_data:
                # 成功拿到了数据，直接返回
                metrics = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']
                return {
                    "url": url, 
                    "lcp": round(metrics['percentile'] / 1000, 2), 
                    "category": metrics['category'], 
                    "status": "Success"
                }
        except:
            if i == 0: 
                print(f"首次请求 {url} 超时，5秒后重试...")
                time.sleep(5)
            continue
            
    return {"url": url, "status": "请求超时"}

def send_feishu_text(results):
    # 1. 构造纯文本
    report_lines = [
        "🚀 【MOVA 性能监控日报】",
        "--------------------------------"
    ]
    
    valid_results = sorted([r for r in results if 'lcp' in r], key=lambda x: x['lcp'], reverse=True)
    for r in valid_results:
        icon = "🔴" if r['category'] == "SLOW" else "🟡" if r['category'] == "AVERAGE" else "🟢"
        report_lines.append(f"{icon} 项目: {r['name']}")
        report_lines.append(f"   LCP: {r['lcp']}s ({r['category']})")
        report_lines.append(f"   URL: {r['url']}\n")

    errors = [r for r in results if 'lcp' not in r]
    if errors:
        report_lines.append("⚠️ 以下页面检测失败:")
        for e in errors:
            report_lines.append(f"   - {e['name']}: {e['status']}")

    text_content = "\n".join(report_lines)

    # 2. 针对“机器人助手”应用的特殊 Payload
    # 应用类机器人有时需要将 content 转义为字符串
    payload = {
        "msg_type": "text",
        "content": json.dumps({"text": text_content}) # 关键点：这里做二次转义
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        response = requests.post(
            FEISHU_WEBHOOK, 
            data=json.dumps(payload), # 整体再序列化一次
            headers=headers,
            timeout=10
        )
        # 调试：在 GitHub Actions 日志里看这个输出
        print(f"飞书返回: {response.text}") 
    except Exception as e:
        print(f"发送失败: {e}")

def main():
    results = []
    for target in CONFIG['targets']:
        data = fetch_real_user_data(target['url'])
        data['name'] = target['name']
        results.append(data)
    
    send_feishu_text(results)

if __name__ == "__main__":
    main()
