"""
工具函数 - 所有可被 AI 调用的工具
"""

import os
import json
import requests
import base64
from datetime import datetime
from bs4 import BeautifulSoup
from git_manager import GitManager
from config import DATA_DIR

# ========== 基础工具 ==========
def get_time():
    """获取当前时间"""
    return datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')

def apply_code_patch(patch_text, commit_message="Self-modify"):
    """应用代码补丁"""
    try:
        gm = GitManager(repo_path=os.getcwd())
        if gm.apply_patch(patch_text, commit_message):
            return "✅ 代码已修改并推送"
        return "❌ 修改失败"
    except Exception as e:
        return f"❌ 错误：{e}"

def read_file(filepath):
    """读取文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 1900:
                content = content[:1900] + "\n... (截断)"
            return f"📄 {filepath}：\n```python\n{content}\n```"
    except FileNotFoundError:
        return f"❌ 文件不存在: {filepath}"
    except Exception as e:
        return f"❌ 读取失败: {e}"

def search_web(query):
    """联网搜索"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__a')[:5]:
            title = a.get_text()
            link = a.get('href')
            if link and link.startswith('/'):
                link = 'https://duckduckgo.com' + link
            results.append(f"🔗 {title}\n   {link}")
        return "🔍 搜索结果：\n\n" + "\n\n".join(results) if results else "❌ 无结果"
    except Exception as e:
        return f"❌ 搜索失败: {e}"

# ========== 定时任务工具 ==========
def set_daily_message(channel_id, message, hour, minute):
    from vector_store import scheduled_tasks
    task_id = f"daily_{channel_id}_{hour}_{minute}"
    scheduled_tasks[task_id] = {"channel_id": channel_id, "message": message, "hour": hour, "minute": minute}
    return f"✅ 已设置每日 {hour:02d}:{minute:02d} 在此频道发送消息"

def set_one_time_reminder(channel_id, message, seconds):
    from vector_store import one_time_tasks
    task_id = f"once_{channel_id}_{int(datetime.now().timestamp())}"
    one_time_tasks[task_id] = {"channel_id": channel_id, "message": message, "seconds": seconds}
    if seconds < 60:
        return f"✅ 已设置 {seconds} 秒后提醒：{message}"
    elif seconds < 3600:
        return f"✅ 已设置 {seconds//60} 分钟后提醒：{message}"
    else:
        return f"✅ 已设置 {seconds//3600} 小时后提醒：{message}"

def delete_task(task_description):
    from vector_store import scheduled_tasks, one_time_tasks
    if "每天" in task_description or "每日" in task_description:
        for task_id in list(scheduled_tasks.keys()):
            task = scheduled_tasks[task_id]
            if task_description in task["message"]:
                del scheduled_tasks[task_id]
                return f"✅ 已删除：{task['message']}"
        return "❌ 未找到"
    else:
        count = len(one_time_tasks)
        one_time_tasks.clear()
        return f"✅ 已删除 {count} 个一次性提醒"

def list_tasks():
    from vector_store import scheduled_tasks, one_time_tasks
    result = []
    if scheduled_tasks:
        result.append("📋 每日任务：")
        for t in scheduled_tasks.values():
            result.append(f"  - {t['hour']:02d}:{t['minute']:02d}: {t['message'][:50]}")
    if one_time_tasks:
        result.append("\n⏰ 一次性：")
        for t in one_time_tasks.values():
            sec = t["seconds"]
            if sec < 60:
                result.append(f"  - {sec}秒后: {t['message'][:50]}")
            elif sec < 3600:
                result.append(f"  - {sec//60}分钟后: {t['message'][:50]}")
            else:
                result.append(f"  - {sec//3600}小时后: {t['message'][:50]}")
    return "\n".join(result) if result else "📭 无任务"

# ========== GitHub 建站工具 ==========
def create_github_repo(repo_name: str, description: str = "", private: bool = False):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "❌ 未设置 GITHUB_TOKEN"

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {
        "name": repo_name,
        "description": description,
        "private": private,
        "auto_init": True
    }
    resp = requests.post("https://api.github.com/user/repos", headers=headers, json=data)
    if resp.status_code == 422:
        owner = os.getenv("GITHUB_OWNER")
        if not owner:
            user_resp = requests.get("https://api.github.com/user", headers=headers)
            if user_resp.status_code == 200:
                owner = user_resp.json()["login"]
            else:
                return "❌ 无法确定用户名，请设置 GITHUB_OWNER"
        repo_check = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}", headers=headers)
        if repo_check.status_code == 200:
            return f"ℹ️ 仓库已存在：{owner}/{repo_name}"
        else:
            return f"❌ 创建仓库失败：{resp.json().get('message', '未知错误')}"
    if resp.status_code not in (200, 201):
        return f"❌ 创建仓库失败：{resp.status_code} - {resp.json().get('message', '')}"

    repo = resp.json()
    full_name = repo["full_name"]
    return f"✅ 已创建仓库：{full_name}"

def deploy_website(html_code: str, filename: str = "index.html", commit_message: str = "Deploy website", repo: str = None):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "❌ 未设置 GITHUB_TOKEN"

    if repo:
        if '/' in repo:
            owner, repo_name = repo.split('/', 1)
        else:
            owner = os.getenv("GITHUB_OWNER")
            if not owner:
                headers = {"Authorization": f"token {token}"}
                user_resp = requests.get("https://api.github.com/user", headers=headers)
                if user_resp.status_code == 200:
                    owner = user_resp.json()["login"]
                else:
                    return "❌ 无法确定 GitHub 用户名，请设置 GITHUB_OWNER"
            repo_name = repo
    else:
        env_repo = os.getenv("GITHUB_REPO")
        if not env_repo:
            return "❌ 未设置 GITHUB_REPO 且未指定仓库名"
        if '/' in env_repo:
            owner, repo_name = env_repo.split('/', 1)
        else:
            owner = os.getenv("GITHUB_OWNER")
            if not owner:
                return "❌ 未设置 GITHUB_OWNER 且 GITHUB_REPO 格式不正确"
            repo_name = env_repo

    headers = {"Authorization": f"token {token}"}
    repo_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    resp = requests.get(repo_url, headers=headers)
    if resp.status_code != 200:
        return f"❌ 无法获取仓库信息: {resp.status_code} - {resp.json().get('message', '')}"
    default_branch = resp.json().get("default_branch", "main")

    file_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{filename}"
    sha = None
    resp = requests.get(file_url, headers=headers)
    if resp.status_code == 200:
        sha = resp.json()["sha"]

    data = {
        "message": commit_message,
        "content": base64.b64encode(html_code.encode()).decode(),
        "branch": default_branch
    }
    if sha:
        data["sha"] = sha
    resp = requests.put(file_url, headers=headers, json=data)
    if resp.status_code not in (200, 201):
        return f"❌ 提交文件失败: {resp.status_code} - {resp.json().get('message', '')}"

    pages_url = f"https://api.github.com/repos/{owner}/{repo_name}/pages"
    pages_resp = requests.get(pages_url, headers=headers)
    if pages_resp.status_code == 404:
        pages_data = {"source": {"branch": default_branch, "path": "/"}}
        pages_resp = requests.post(pages_url, headers=headers, json=pages_data)
        if pages_resp.status_code not in (200, 201):
            return f"❌ 启用 GitHub Pages 失败: {pages_resp.status_code} - {pages_resp.json().get('message', '')}"

    site_url = f"https://{owner}.github.io/{repo_name}/"
    return f"✅ 网站已部署！访问地址：{site_url}"
