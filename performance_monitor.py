import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= 核心配置区 (建议以后可以放进 config.json) =================
CONFIG = {
    "google_api_key": os.getenv("PSI_API_KEY"),
    "targets": [
        {"name": "US-Home", "url": "https://us.mova.tech/"},
        {"name": "US-Product", "url": "https://us.mova.tech/products/mova-lidax-ultra-3000-awd-robotic-lawn-mower"},
        {"name": "CA-Home", "url": "https://ca.mova.tech/"}
    ],
    "notifications": {
        "feishu": {
            "enabled": True,
            "webhook_url": os.getenv("FEISHU_WEBHOOK")
        },
        "email": {
            "enabled": False,  # 如需开启请设为 True
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 465,
            "sender": "your_email@gmail.com",
            "password": "your_app_password", # 注意：这里是应用专用密码
            "receiver": "boss@example.com"
        }
    }
}

def fetch_real_user_data(url):
    """增加重试机制的抓取函数"""
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={CONFIG['google_api_key']}&strategy=mobile"
    
    # 配置重试策略：重试3次，间隔时间指数增加
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)

    try:
        # 将 timeout 延长到 60 秒
        response = session.get(api_url, timeout=60).json()
        
        # 检查是否有 API 级别的错误返回
        if 'error' in response:
            return {"url": url, "status": f"API Error: {response['error']['message']}"}
            
        field_data = response.get('loadingExperience', {})
        
        if not field_data or 'metrics' not in field_data:
            return {"url": url, "status": "No Field Data (流量不足或新站)"}

        metrics = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']
        lcp_sec = round(metrics['percentile'] / 1000, 2)
        
        return {
            "url": url,
            "lcp": f"{lcp_sec}s",
            "lcp_val": lcp_sec,
            "category": metrics['category'],
            "status": "Success"
        }
    except requests.exceptions.Timeout:
        return {"url": url, "status": "Error: 请求超时，Google API 响应太慢"}
    except Exception as e:
        return {"url": url, "status": f"Error: {str(e)}"}

def send_feishu(results):
    if not CONFIG['notifications']['feishu']['enabled']: return
    
    # 按照 LCP 慢到快排序
    valid_results = sorted([r for r in results if 'lcp_val' in r], key=lambda x: x['lcp_val'], reverse=True)
    
    # 构建卡片元素
    elements = []
    for r in valid_results:
        # 根据状态选择表情和颜色
        if r['category'] == "SLOW":
            status_text = "🔴 SLOW (需要紧急优化)"
            color = "red"
        elif r['category'] == "AVERAGE":
            status_text = "🟡 AVERAGE (待改进)"
            color = "orange"
        else:
            status_text = "🟢 FAST (表现优秀)"
            color = "green"
            
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**项目: {r['name']}**\n**LCP: {r['lcp']}** | 状态: {status_text}\nURL: {r['url']}"
            }
        })
        elements.append({"tag": "hr"}) # 分隔线

    # 错误处理
    errors = [r for r in results if 'lcp_val' not in r]
    if errors:
        error_msg = "\n".join([f"⚠️ {e['name']}: {e['status']}" for e in errors])
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": error_msg}]
        })

    # 飞书交互式卡片 JSON 结构
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"enable_forward": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🚀 Shopify 站点真实用户速度日报"},
                "template": "blue" # 标题栏颜色
            },
            "elements": elements
        }
    }
    
    requests.post(CONFIG['notifications']['feishu']['webhook_url'], json=payload)

def send_email(msg_content):
    conf = CONFIG['notifications']['email']
    if not conf['enabled']: return
    message = MIMEText(msg_content, 'plain', 'utf-8')
    message['From'] = conf['sender']
    message['To'] = conf['receiver']
    message['Subject'] = Header("Shopify 站点真实用户速度日报", 'utf-8')
    
    try:
        smtp = smtplib.SMTP_SSL(conf['smtp_server'], conf['smtp_port'])
        smtp.login(conf['sender'], conf['password'])
        smtp.sendmail(conf['sender'], [conf['receiver']], message.as_string())
        smtp.quit()
    except Exception as e:
        print(f"Email Error: {e}")

def main():
    results = []
    print("开始检测各站点真实用户数据...")
    for target in CONFIG['targets']:
        data = fetch_real_user_data(target['url'])
        data['name'] = target['name']
        results.append(data)
    
    # 构造报告文本
    report = ""
    # 按 LCP 慢到快排序
    valid_results = sorted([r for r in results if 'lcp_val' in r], key=lambda x: x['lcp_val'], reverse=True)
    
    for r in valid_results:
        icon = "🔴" if r['category'] == "SLOW" else "🟡" if r['category'] == "AVERAGE" else "🟢"
        report += f"{icon} {r['name']}: LCP {r['lcp']} ({r['category']})\nURL: {r['url']}\n\n"
    
    # 错误处理展示
    errors = [r for r in results if 'lcp_val' not in r]
    if errors:
        report += "⚠️ 以下页面暂无真实用户数据或报错：\n"
        for e in errors:
            report += f"- {e['name']}: {e['status']}\n"

    # 执行发送
    send_feishu(report)
    send_email(report)
    print("报告已发送。")

if __name__ == "__main__":
    main()
