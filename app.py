from flask import Flask, session, redirect, request, jsonify, render_template, flash, url_for
import os
from dotenv import load_dotenv
import requests
from models import db, Paste, CardDistribution, User, Comment
from functools import wraps
import random
from sqlalchemy import and_, func
from datetime import datetime

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.update(
    SESSION_COOKIE_SECURE=False,  # 如果使用 HTTPS 则设为 True
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800,  # session 过期时间，单位秒
)

db.init_app(app)

# OAuth2 配置从环境变量获取
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
AUTHORIZATION_ENDPOINT = os.getenv('AUTHORIZATION_ENDPOINT')
TOKEN_ENDPOINT = os.getenv('TOKEN_ENDPOINT')
USER_ENDPOINT = os.getenv('USER_ENDPOINT')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_info' not in session and not request.args.get('anonymous'):
            return redirect('/oauth2/initiate')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_info' not in session:
            return redirect('/oauth2/initiate')
        user = User.query.get(session['user_info']['id'])
        if not user or not user.is_admin:
            return "需要管理员权限", 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_info' in session:
        # 登录用户可以看到公开的和自己的 pastes
        public_pastes = Paste.query.filter_by(is_public=True).all()
        own_pastes = Paste.query.filter_by(creator_id=session['user_info']['id'], is_public=False).all()
        all_pastes = public_pastes + own_pastes
        allowed_pastes = [paste for paste in all_pastes if can_view_paste(paste, session['user_info'])]
    else:
        # 匿名用户只能看到公开的 pastes
        allowed_pastes = Paste.query.filter_by(is_public=True).all()
    
    return render_template('index.html', 
        pastes=allowed_pastes, 
        user=session.get('user_info'),
        is_anonymous='anonymous' in request.args
    )

def can_view_paste(paste, user_info=None):
    # 如果是匿名访问且 paste 是公开的
    if user_info is None and paste.is_public:
        return True
        
    # 如果是登录用户
    if user_info:
        # 创建者可以查看
        if paste.creator_id == user_info['id']:
            return True
        
        # 检查信任等级
        if int(user_info['trust_level']) >= paste.min_trust_level:
            return True
            
        # 检查允许的用户名单
        if paste.allowed_users:
            allowed_users = paste.allowed_users.split(',')
            if user_info['username'] in allowed_users:
                return True
                
    return False

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_paste():
    if request.method == 'POST':
        paste = Paste(
            content=request.form.get('content'),
            title=request.form.get('title'),
            description=request.form.get('description'),
            language=request.form.get('language'),
            creator_id=session['user_info']['id'],
            creator_username=session['user_info']['username'],
            is_public='is_public' in request.form,
            min_trust_level=int(request.form.get('min_trust_level', 0)),
            allowed_users=request.form.get('allowed_users', ''),
            is_card_distribution='is_card_distribution' in request.form,
            allow_repeat='allow_repeat' in request.form,
            show_progress='show_progress' in request.form
        )
        
        db.session.add(paste)
        db.session.commit()
        return redirect(url_for('view_paste', paste_id=paste.id))
        
    return render_template('create.html')

@app.route('/edit/<int:paste_id>', methods=['GET', 'POST'])
@login_required
def edit_paste(paste_id):
    paste = Paste.query.get_or_404(paste_id)
    if paste.creator_id != session['user_info']['id']:
        return "没有权限编辑此 Paste", 403
        
    if request.method == 'POST':
        paste.content = request.form.get('content')
        paste.title = request.form.get('title')
        paste.language = request.form.get('language')
        paste.min_trust_level = int(request.form.get('min_trust_level', 0))
        paste.allowed_users = request.form.get('allowed_users', '')
        paste.is_card_distribution = 'is_card_distribution' in request.form
        paste.allow_repeat = 'allow_repeat' in request.form
        paste.show_progress = 'show_progress' in request.form
        
        db.session.commit()
        return redirect(url_for('view_paste', paste_id=paste_id))
        
    return render_template('edit.html', paste=paste)

@app.route('/view/<int:paste_id>')
def view_paste(paste_id):
    paste = Paste.query.get_or_404(paste_id)
    user_info = session.get('user_info')
    
    if not can_view_paste(paste, user_info):
        if 'user_info' not in session:
            return redirect(url_for('initiate_auth'))
        return "没有权限查看此 Paste", 403
    
    user_card = None
    progress = None
    if paste.is_card_distribution and user_info:  # 只有登录用户才能获取卡密
        user_card = get_user_card(paste, user_info['id'])
        if paste.show_progress and not paste.allow_repeat:
            total_lines = len(paste.content.splitlines())
            used_lines = CardDistribution.query.filter_by(paste_id=paste.id).count()
            progress = {
                'used': used_lines,
                'total': total_lines,
                'percent': (used_lines / total_lines * 100) if total_lines > 0 else 0
            }
    
    return render_template('view.html',
        paste=paste,
        user_card=user_card,
        progress=progress,
        comments=paste.comments,
        user=user_info,
        is_anonymous='anonymous' in request.args
    )

def get_user_card(paste, user_id):
    # 检查用户是否已经分配了卡密
    distribution = CardDistribution.query.filter_by(
        paste_id=paste.id,
        user_id=user_id
    ).first()
    
    if distribution:
        # 用户已有分配的卡密，返回对应行
        lines = paste.content.splitlines()
        if distribution.card_line < len(lines):
            return lines[distribution.card_line]
        return None
        
    # 用户还没有分配卡密
    if not paste.allow_repeat:
        # 获取已分配的行号
        used_lines = {d.card_line for d in CardDistribution.query.filter_by(paste_id=paste.id).all()}
        lines = paste.content.splitlines()
        available_lines = set(range(len(lines))) - used_lines
        
        if not available_lines:
            return None
            
        # 分配新行
        new_line = min(available_lines)
    else:
        # 允许重复分发，随机选择一行
        lines = paste.content.splitlines()
        if not lines:
            return None
        new_line = random.randint(0, len(lines) - 1)
    
    # 创建分配记录
    distribution = CardDistribution(
        paste_id=paste.id,
        user_id=user_id,
        card_line=new_line
    )
    db.session.add(distribution)
    db.session.commit()
    
    return lines[new_line]

# OAuth 相关路由
@app.route('/oauth2/initiate')
def initiate_auth():
    session.clear()  # 清除旧的 session 数据
    session['oauth_state'] = os.urandom(32).hex()
    session.modified = True  # 确保 session 被保存
    
    authorization_url = (
        f"{AUTHORIZATION_ENDPOINT}"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={session['oauth_state']}"
    )
    return redirect(authorization_url)

@app.route('/oauth2/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    stored_state = session.get('oauth_state')

    # 添加调试信息
    print(f"Received state: {state}")
    print(f"Stored state: {stored_state}")

    if not state or not stored_state or state != stored_state:
        flash('状态值不匹配，请重新登录', 'error')
        return redirect('/oauth2/initiate')

    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Accept': 'application/json'}
    
    try:
        response = requests.post(TOKEN_ENDPOINT, auth=auth, data=data, headers=headers)
        response.raise_for_status()  # 抛出非 200 响应的异常
        
        access_token = response.json()['access_token']
        user_response = requests.get(
            USER_ENDPOINT, 
            headers={'Authorization': f'Bearer {access_token}'}
        )
        user_response.raise_for_status()
        
        user_data = user_response.json()
        session['user_info'] = user_data
        
        # 更新或创建用户记录
        user = User.query.get(user_data['id'])
        if not user:
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                trust_level=user_data['trust_level']
            )
            db.session.add(user)
        else:
            user.username = user_data['username']
            user.trust_level = user_data['trust_level']
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return redirect('/')
        
    except requests.exceptions.RequestException as e:
        print(f"OAuth error: {str(e)}")
        flash('登录过程发生错误，请重试', 'error')
        return redirect('/oauth2/initiate')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/paste/<int:paste_id>/comment', methods=['POST'])
@login_required
def add_comment(paste_id):
    paste = Paste.query.get_or_404(paste_id)
    if not can_view_paste(paste, session['user_info']):
        return "没有权限评论", 403
        
    content = request.form.get('content')
    if not content:
        return "评论内容不能为空", 400
        
    comment = Comment(
        paste_id=paste_id,
        user_id=session['user_info']['id'],
        username=session['user_info']['username'],
        content=content
    )
    db.session.add(comment)
    db.session.commit()
    
    return redirect(url_for('view_paste', paste_id=paste_id))

@app.route('/admin')
@admin_required
def admin_dashboard():
    # 统计数据
    total_pastes = Paste.query.count()
    total_users = User.query.count()
    total_comments = Comment.query.count()
    total_distributions = CardDistribution.query.count()
    
    # 最近的 Pastes
    recent_pastes = Paste.query.order_by(Paste.created_at.desc()).limit(10).all()
    
    # 最活跃用户
    active_users = db.session.query(
        User,
        func.count(Paste.id).label('paste_count')
    ).outerjoin(Paste, User.id == Paste.creator_id)\
     .group_by(User.id)\
     .order_by(func.count(Paste.id).desc())\
     .limit(10).all()
    
    return render_template('admin/dashboard.html',
        total_pastes=total_pastes,
        total_users=total_users,
        total_comments=total_comments,
        total_distributions=total_distributions,
        recent_pastes=recent_pastes,
        active_users=active_users
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, port=int(os.getenv('FLASK_PORT', 8181)), host="0.0.0.0")
