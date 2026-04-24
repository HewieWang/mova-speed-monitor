import requests
import os
import time
import json

# 配置区 (建议继续使用环境变量)
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
    """抓取 PSI 数据，增强了错误处理"""
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={GOOGLE_API_KEY}&strategy=mobile"
    
    for i in range(2): # 尝试 2 次
        try:
            response = requests.get(api_url, timeout=120)
            response.raise_for_status() # 检查 HTTP 状态码
            data = response.json()
            
            # 提取真实用户体验数据 (CrUX)
            field_data = data.get('loadingExperience', {})
            if field_data and 'metrics' in field_data:
                metrics = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']
                return {
                    "url": url, 
                    "lcp": round(metrics['percentile'] / 1000, 2), 
                    "category": metrics['category'], 
                    "status": "Success"
                }
            else:
                return {"url": url, "status": "暂无真实用户数据", "lcp": None}
                
        except requests.exceptions.Timeout:
            if i == 0:
                print(f"首次请求 {url} 超时，5秒后重试...")
                time.sleep(5)
                continue
            return {"url": url, "status": "请求超时", "lcp": None}
        except Exception as e:
            # 捕获其他异常（如接口改版或 API Key 失效），返回简洁提示
            return {"url": url, "status": f"接口异常: {str(e)[:20]}", "lcp": None}
            
    return {"url": url, "status": "请求失败", "lcp": None}

def build_card_payload(results):
    """构造飞书交互式卡片 JSON"""
    
    # 统计是否有页面状态不佳
    any_slow = any(r.get('category') == "SLOW" for r in results if r.get('lcp'))
    header_color = "red" if any_slow else "blue"
    
    # 构建数据列表行
    elements = []
    for r in results:
        if r['lcp']:
            icon = "🔴" if r['category'] == "SLOW" else "🟡" if r['category'] == "AVERAGE" else "🟢"
            status_text = f"**{r['lcp']}s** ({r['category']})"
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
        elements.append({"tag": "hr"}) # 添加分割线

    # 结尾备注
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
    """发送请求"""
    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        response = requests.post(FEISHU_WEBHOOK, data=json.dumps(payload), headers=headers, timeout=10)
        print(f"飞书推送状态: {response.status_code}, 返回: {response.text}")
    except Exception as e:
        print(f"网络层错误: {e}")

def main():
    print("开始执行性能监测...")
    results = []
    for target in CONFIG['targets']:
        print(f"正在分析: {target['name']}...")
        data = fetch_real_user_data(target['url'])
        data['name'] = target['name']
        results.append(data)
    
    payload = build_card_payload(results)
    send_to_feishu(payload)

if __name__ == "__main__":
    main()
