import requests
import os
import time
import json

# 配置区
GOOGLE_API_KEY = os.getenv("PSI_API_KEY")
CACHE_FILE = "last_results.json"  # 缓存文件名

# 新增：从 GitHub Actions 环境中获取的变量
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
        if r.get('status') == "Success" and r.get('lcp'):
            cache_data[r['url']] = r
            
    if cache_data:
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

    if not result:
        if url in cache:
            result = cache[url].copy()
            result["is_cache"] = True
            result["status"] = "Success (来自历史)"
        else:
            result = {"url": url, "status": "请求失败且无缓存", "lcp": None, "is_cache": False}
            
    return result

def build_markdown_body(results):
    """构造适合 GitHub Issues 展示的 Markdown 内容"""
    any_slow = any(r.get('category') == "SLOW" for r in results if r.get('lcp'))
    
    # 状态概览横幅
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

def create_github_issue(body):
    """调用 GitHub API 创建 Issue"""
    if not GITHUB_REPOSITORY or not GITHUB_TOKEN:
        print("缺少 GITHUB_REPOSITORY 或 GITHUB_TOKEN 环境变量，跳过 Issue 创建")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 标题带上当前日期
    title = f"🚀 MOVA 性能监控日报 - {time.strftime('%Y-%m-%d')}"
    
    payload = {
        "title": title,
        "body": body,
        "labels": ["performance-report"] # 自动加上标签，方便外部人过滤筛选
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 201:
            print("GitHub Issue 创建成功！")
        else:
            print(f"创建 Issue 失败，状态码: {response.status_code}, 返回: {response.text}")
    except Exception as e:
        print(f"发送 GitHub API 请求异常: {str(e)}")

def main():
    cache = load_cache()
    results = []
    for target in CONFIG['targets']:
        data = fetch_real_user_data(target['url'], cache)
        data['name'] = target['name']
        results.append(data)
    
    save_cache(results) # 保存最新的成功数据
    
    # 生成 Markdown 报告并发布到 GitHub Issues
    md_body = build_markdown_body(results)
    create_github_issue(md_body)

if __name__ == "__main__":
    main()
