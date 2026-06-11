import requests
import os
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# 配置区
GOOGLE_API_KEY = os.getenv("PSI_API_KEY")
CACHE_FILE = "last_results.json"  # 缓存文件名

# 从 GitHub Actions 环境中获取的变量
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY") # 格式如 "owner/repo"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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
        {"name": "US-X10", "url": "https://us.mova.tech/products/mova-rover-x10-robotic-pool-cleaner"},
        {"name": "US-1000", "url": "https://us.mova.tech/products/mova-lidax-ultra-1000-robot-lawn-mower"},
        {"name": "CA-X10", "url": "https://ca.mova.tech/products/mova-rover-x10-robotic-pool-cleaner"},
        {"name": "CA-1000", "url": "https://ca.mova.tech/products/mova-lidax-ultra-1000-robot-lawn-mower"},
        {"name": "US-V50", "url": "https://us.mova.tech/products/mova-v50-ultra-complete-robot-vacuum"},
        {"name": "US-Z60", "url": "https://us.mova.tech/products/mova-z60-ultra-roller-complete"},
        {"name": "US-Mobius", "url": "https://us.mova.tech/products/mova-mobius-60-robot-vacuum"},
        {"name": "US-P10PU", "url": "https://us.mova.tech/products/p10-pro-ultra-robot-vacuum"},
        {"name": "US-X4Pro", "url": "https://us.mova.tech/products/mova-wet-dry-vacuum-x4-pro"},
        {"name": "US-M10", "url": "https://us.mova.tech/products/mova-wet-dry-vacuum-m10"},
        {"name": "CA-V50", "url": "https://ca.mova.tech/products/mova-v50-ultra-complete-robot-vacuum"},
        {"name": "CA-Z60", "url": "https://ca.mova.tech/products/mova-z60-ultra-roller-complete"},
        {"name": "CA-Mobius", "url": "https://ca.mova.tech/products/mova-mobius-60-robot-vacuum"},
        {"name": "CA-P10PU", "url": "https://ca.mova.tech/products/p10-pro-ultra-robot-vacuum"},
        {"name": "CA-X4Pro", "url": "https://ca.mova.tech/products/mova-wet-dry-vacuum-x4-pro"},
        {"name": "CA-M10", "url": "https://ca.mova.tech/products/mova-wet-dry-vacuum-m10"}
    ]
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(results):
    cache_data = {}
    for r in results:
        if r.get('status') == "Success" and r.get('lcp'):
            cache_data[r['url']] = r
            
    if cache_data:
        old_cache = load_cache()
        old_cache.update(cache_data)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(old_cache, f, ensure_ascii=False, indent=2)

def fetch_real_user_data(url, cache):
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

    if not result:
        if url in cache:
            result = cache[url].copy()
            result["is_cache"] = True
            result["status"] = "Success (来自历史)"
        else:
            result = {"url": url, "status": "请求失败且无缓存", "lcp": None, "is_cache": False}
            
    return result

def build_markdown_body(results):
    any_slow = any(r.get('category') == "SLOW" for r in results if r.get('lcp'))
    status_summary = "🚨 **检测到部分页面加载缓慢，请注意优化！**" if any_slow else "✅ **所有页面性能表现良好。**"
    
    markdown = f"### 📊 性能监控结果概览\n{status_summary}\n\n"
    markdown += "| 页面名称 | LCP 指标 | 状态分类 | 访问链接 |\n"
    markdown += "| :--- | :--- | :--- | :--- |\n"
    
    for r in results:
        if r['lcp']:
            icon = "🔴" if r['category'] == "SLOW" else "🟡" if r['category'] == "AVERAGE" else "🟢"
            cache_tag = " ⚠️(历史数据)" if r.get('is_cache') else ""
            lcp_text = f"**{r['lcp']}s**"
            category_text = f"{icon} {r['category']}{cache_tag}"
        else:
            lcp_text = "`-`"
            category_text = f"⚪ *{r['status']}*"
            
        markdown += f"| **{r['name']}** | {lcp_text} | {category_text} | [点击访问]({r['url']}) |\n"
        
    markdown += f"\n---\n*统计时间: {time.strftime('%Y-%m-%d %H:%M:%S')} (UTC)*"
    return markdown

def build_html_body(results):
    any_slow = any(r.get('category') == "SLOW" for r in results if r.get('lcp'))
    if any_slow:
        banner_color = "#fff2f2"
        banner_border = "#ffccc7"
        banner_text = "🚨 <strong>检测到部分页面加载缓慢，请注意优化！</strong>"
    else:
        banner_color = "#f6ffed"
        banner_border = "#b7eb8f"
        banner_text = "✅ <strong>所有页面性能表现良好。</strong>"

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; line-height: 1.6; }}
            .banner {{ padding: 12px 16px; background-color: {banner_color}; border: 1px solid {banner_border}; border-radius: 4px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #f0f0f0; }}
            th {{ background-color: #fafafa; font-weight: 600; color: #000; border-bottom: 2px solid #f0f0f0; }}
            .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; }}
            .badge-green {{ background-color: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }}
            .badge-yellow {{ background-color: #fffbe6; color: #d46b08; border: 1px solid #ffe58f; }}
            .badge-red {{ background-color: #fff2f2; color: #cf1322; border: 1px solid #ffccc7; }}
            .badge-gray {{ background-color: #f5f5f5; color: #595959; border: 1px solid #d9d9d9; }}
            .link-btn {{ color: #1890ff; text-decoration: none; }}
            .footer {{ margin-top: 25px; font-size: 12px; color: #8c8c8c; border-top: 1px solid #f0f0f0; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <h2>📊 性能监控结果概览</h2>
        <div class="banner">{banner_text}</div>
        <table>
            <thead>
                <tr>
                    <th>页面名称</th>
                    <th>LCP 指标</th>
                    <th>状态分类</th>
                    <th>访问链接</th>
                </tr>
            </thead>
            <tbody>
    """
    for r in results:
        if r['lcp']:
            if r['category'] == "SLOW":
                badge_cls = "badge-red"
                icon = "🔴"
            elif r['category'] == "AVERAGE":
                badge_cls = "badge-yellow"
                icon = "🟡"
            else:
                badge_cls = "badge-green"
                icon = "🟢"
            cache_tag = " <span style='font-size:11px;color:#999;'>(历史)</span>" if r.get('is_cache') else ""
            lcp_text = f"<strong>{r['lcp']}s</strong>"
            category_text = f"<span class='badge {badge_cls}'>{icon} {r['category']}</span>{cache_tag}"
        else:
            lcp_text = "<span style='color:#ccc;'>-</span>"
            category_text = f"<span class='badge badge-gray'>⚪ {r['status']}</span>"
            
        html += f"""
                <tr>
                    <td><strong>{r['name']}</strong></td>
                    <td>{lcp_text}</td>
                    <td>{category_text}</td>
                    <td><a class="link-btn" href="{r['url']}" target="_blank">点击访问 →</a></td>
                </tr>
        """
    html += f"""
            </tbody>
        </table>
        <div class="footer">统计时间: {time.strftime('%Y-%m-%d %H:%M:%S')} (UTC) | 来自 GitHub Actions 自动化监测</div>
    </body>
    </html>
    """
    return html

def create_github_issue(body):
    if not GITHUB_REPOSITORY or not GITHUB_TOKEN:
        print("缺少 GITHUB_REPOSITORY 或 GITHUB_TOKEN 环境变量，跳过 Issue 创建")
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    title = f"🚀 MOVA 性能监控日报 - {time.strftime('%Y-%m-%d')}"
    payload = {"title": title, "body": body, "labels": ["performance-report"]}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 201:
            print("GitHub Issue 创建成功！")
        else:
            print(f"创建 Issue 失败，状态码: {response.status_code}, 返回: {response.text}")
    except Exception as e:
        print(f"发送 GitHub API 请求异常: {str(e)}")

def send_html_email(html_content):
    """直接由 Python 发送标准 HTML 邮件，彻底避免长文本在 YML 中截断报错"""
    mail_host = "smtp.163.com"  # 如果是腾讯企业邮请改为 smtp.exmail.qq.com
    mail_user = os.getenv("MAIL_USER")
    mail_pass = os.getenv("MAIL_PASS")
    # 收件人列表
    mail_to_list = ["wanghao@adsmarch.com", "dongyawen@mova-tech.com", "na.official.site@mova-tech.com"]

    if not mail_user or not mail_pass:
        print("缺少 MAIL_USER 或 MAIL_PASS 环境变量，跳过邮件发送")
        return

    # 显式声明为 'html' 格式发送，保证客户端完美渲染
    message = MIMEText(html_content, 'html', 'utf-8')
    message['From'] = Header("MOVA 性能监控助手", 'utf-8')
    message['To'] = Header(",".join(mail_to_list), 'utf-8')
    message['Subject'] = Header(f"🚀 MOVA 性能监控日报 - {time.strftime('%Y-%m-%d')}", 'utf-8')

    try:
        smtp_obj = smtplib.SMTP_SSL(mail_host, 465, timeout=15)
        smtp_obj.login(mail_user, mail_pass)
        smtp_obj.sendmail(mail_user, mail_to_list, message.as_string())
        print("邮件提醒发送成功（HTML 格式渲染）！")
    except Exception as e:
        print(f"邮件发送失败: {str(e)}")

def main():
    cache = load_cache()
    results = []
    for target in CONFIG['targets']:
        data = fetch_real_user_data(target['url'], cache)
        data['name'] = target['name']
        results.append(data)
    
    save_cache(results)
    
    # 1. 依然创建标准的 GitHub Issue
    md_body = build_markdown_body(results)
    create_github_issue(md_body)
    
    # 2. 直接在 Python 内把精美的 HTML 内容发出去
    html_body = build_html_body(results)
    send_html_email(html_body)

if __name__ == "__main__":
    main()
