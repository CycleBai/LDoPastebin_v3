from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    username = db.Column(db.String(100), unique=True)
    is_admin = db.Column(db.Boolean, default=False)
    trust_level = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Paste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator_id = db.Column(db.String(100), nullable=False)
    creator_username = db.Column(db.String(100))
    language = db.Column(db.String(50))  # 添加语言字段
    
    # 访问控制
    is_public = db.Column(db.Boolean, default=True)
    min_trust_level = db.Column(db.Integer, default=0)
    allowed_users = db.Column(db.Text)
    
    # 卡密分发设置
    is_card_distribution = db.Column(db.Boolean, default=False)
    allow_repeat = db.Column(db.Boolean, default=False)
    show_progress = db.Column(db.Boolean, default=False)  # 是否显示分发进度
    
    # 关联
    comments = db.relationship('Comment', backref='paste', lazy=True)
    distributions = db.relationship('CardDistribution', backref='paste', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paste_id = db.Column(db.Integer, db.ForeignKey('paste.id'), nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CardDistribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paste_id = db.Column(db.Integer, db.ForeignKey('paste.id'), nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    card_line = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)