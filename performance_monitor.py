import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header

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
    """从 PSI API 抓取真实用户 (Field Data) 数据"""
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={CONFIG['google_api_key']}&strategy=mobile"
    try:
        response = requests.get(api_url, timeout=30).json()
        field_data = response.get('loadingExperience', {})
        
        if not field_data or 'metrics' not in field_data:
            return {"url": url, "status": "No Field Data (流量不足或新站)"}

        # 提取 LCP (真实用户 75 分位值)
        lcp_ms = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']['percentile']
        lcp_sec = round(lcp_ms / 1000, 2)
        
        # 判定状态
        category = field_data['metrics']['LARGEST_CONTENTFUL_PAINT_MS']['category'] # FAST, AVERAGE, SLOW
        return {
            "url": url,
            "lcp": f"{lcp_sec}s",
            "lcp_val": lcp_sec,
            "category": category,
            "status": "Success"
        }
    except Exception as e:
        return {"url": url, "status": f"Error: {str(e)}"}

def send_feishu(msg_content):
    if not CONFIG['notifications']['feishu']['enabled']: return
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "📊 真实用户访问速度报告 (Field Data)",
                    "content": [[{"tag": "text", "text": msg_content}]]
                }
            }
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
