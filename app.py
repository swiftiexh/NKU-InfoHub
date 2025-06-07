from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from pymongo import MongoClient

from search.normal_search import NormalSearch
from search.personal_search import PersonalSearch
from search.page_partition import PagePartition
from elasticsearch import Elasticsearch
es = Elasticsearch(
    hosts=["http://localhost:9200"],
    basic_auth=("elastic", "ZCjtuz7ZKNWy7u5DaOId")
)

app = Flask(__name__)
app.secret_key = 'nku_infohub_secret_key'

# MongoDB连接
mongo_client = MongoClient('localhost', 27017)
db = mongo_client['nku_news']
users_col = db['users']
profiles_col = db['user_profiles']
history_col = db['search_history']

# 搜索对象
normal_search = NormalSearch()
page_partition = PagePartition(results_per_page=10)

def get_current_user():
    return session.get('user')

def get_user_profile(username):
    profile = profiles_col.find_one({'username': username})
    return profile or {}

@app.route('/', methods=['GET', 'POST'])
def index():
    user = get_current_user()
    query = ''
    mode = 'basic'
    search_in = 'all'
    sort_by = 'relevance'
    filetypes = []
    personalized = False
    page = int(request.args.get('page', 1))
    results, total, page_range = [], 0, range(1, 2)

    # 获取参数
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        mode = request.form.get('mode', 'basic')
        search_in = request.form.get('search_in', 'all')
        sort_by = request.form.get('sort_by', 'relevance')
        filetypes = request.form.getlist('filetypes')
        personalized = request.form.get('personalized') == '1'
        page = 1
    else:
        query = request.args.get('query', '').strip()
        mode = request.args.get('mode', 'basic')
        search_in = request.args.get('search_in', 'all')
        sort_by = request.args.get('sort_by', 'relevance')
        filetypes = request.args.getlist('filetypes')
        personalized = request.args.get('personalized') == '1'
        page = int(request.args.get('page', 1))

    # 查询
    if query:
        # 记录查询日志
        if user:
            history_col.insert_one({
                "username": user['username'],
                "query": query,
                "search_in": search_in,
                "sort_by": sort_by,
                "timestamp": datetime.now()
            })
        # 普通/个性化查询
        if personalized and user:
            user_profile = get_user_profile(user['username'])
            search_results = normal_search.execute_search(mode, query, search_in, sort_by, filetypes)
            results = PersonalSearch(user_profile).personalize_results(search_results, sort_by)
        else:
            results = normal_search.execute_search(mode, query, search_in, sort_by, filetypes)
        # 分页
        page_info = page_partition.process_results(results, page)
        results = page_info['results']
        total = page_info['total']
        page_range = page_info['page_range']

    return render_template(
        'index.html',
        user=user,
        query=query,
        mode=mode,
        search_in=search_in,
        sort_by=sort_by,
        filetypes=filetypes,
        personalized=personalized,
        results=results,
        total=total,
        page=page,
        page_range=page_range
    )

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    tab = request.args.get('tab', 'login')
    login_error = register_error = login_success = register_success = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'login':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            user = users_col.find_one({'username': username})
            if user and check_password_hash(user['password'], password):
                session['user'] = {
                    'username': user['username'],
                    'email': user.get('email', ''),
                    'role': get_user_profile(user['username']).get('role', '')
                }
                return redirect(url_for('index'))
            else:
                login_error = '用户名或密码错误'
                tab = 'login'
        elif action == 'register':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            password_confirm = request.form.get('password_confirm', '').strip()
            email = request.form.get('email', '').strip()
            role = request.form.get('role', '').strip()
            college = request.form.get('college', '').strip()
            if not (username and password and email and role):
                register_error = '请填写所有必填项'
                tab = 'register'
            elif password != request.form.get('password_confirm', ''):
                register_error = '两次输入的密码不一致'
                tab = 'register'
            elif users_col.find_one({'username': username}):
                register_error = '用户名已存在'
                tab = 'register'
            else:
                users_col.insert_one({
                    'username': username,
                    'email': email,
                    'password': generate_password_hash(password),
                    'created_at': datetime.now()
                })
                profiles_col.insert_one({
                    'username': username,
                    'age': '',
                    'role': role,
                    'college': college,
                    'major': '',
                    'grade': '',
                    'research': ''
                })
                register_success = '注册成功，请登录'
                tab = 'login'
    return render_template(
        'auth.html',
        tab=tab,
        login_error=login_error,
        register_error=register_error,
        login_success=login_success,
        register_success=register_success
    )

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth'))
    profile = get_user_profile(user['username'])
    update_success = update_error = None
    if request.method == 'POST':
        age = request.form.get('age', '').strip()
        email = request.form.get('email', '').strip()
        college = request.form.get('college', '').strip()
        major = request.form.get('major', '').strip()
        grade = request.form.get('grade', '').strip()
        research = request.form.get('research', '').strip()
        # 更新users表邮箱
        users_col.update_one({'username': user['username']}, {'$set': {'email': email}})
        # 更新profile表
        update_fields = {
            'age': age,
            'college': college,
            'major': major,
            'grade': grade,
            'research': research
        }
        profiles_col.update_one({'username': user['username']}, {'$set': update_fields})
        update_success = '信息已更新'
        # 刷新session中的email
        session['user']['email'] = email
        profile = get_user_profile(user['username'])
    return render_template(
        'profile.html',
        user=session['user'],
        profile=profile,
        update_success=update_success,
        update_error=update_error
    )

@app.route('/logs')
def logs():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth'))
    logs = []
    for log in history_col.find({'username': user['username']}).sort('timestamp', -1):
        logs.append({
            'query': log.get('query', ''),
            'search_in': log.get('search_in', ''),
            'sort_by': log.get('sort_by', ''),
            'time': log.get('timestamp').strftime('%Y-%m-%d %H:%M:%S') if log.get('timestamp') else ''
        })
    return render_template('logs.html', user=user, logs=logs)

@app.route('/snap/<snapshot_hash>')
def snap(snapshot_hash):
    snap_doc = db['WEB_snapshot'].find_one({'content_hash': snapshot_hash})
    if not snap_doc:
        return "快照不存在", 404
    url = snap_doc.get('url', '')
    captured_at = snap_doc.get('captured_at', '')
    source = snap_doc.get('source', '')
    raw_html = snap_doc.get('html_content', '<div style="color:red;">无快照内容</div>')
    return render_template(
        'snap.html',
        url=url,
        captured_at=captured_at,
        source=source,
        raw_html=raw_html
    )

from flask import request, jsonify

@app.route('/suggest')
def suggest():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    body = {
        "suggest": {
            "title-suggest": {
                "prefix": q,
                "completion": {
                    "field": "suggest",
                    "size": 10
                }
            }
        }
    }
    try:
        res = es.search(index="nankai_news_index", body=body)
        options = res.get('suggest', {}).get('title-suggest', [])[0].get('options', [])
        suggestions = [opt['text'] for opt in options]
        return jsonify(suggestions)
    except Exception as e:
        print("Suggest error:", e)
        return jsonify([]), 500

if __name__ == '__main__':
    app.run(debug=True)