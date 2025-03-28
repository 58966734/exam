from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from flask_restful import Api, Resource
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
api = Api(app)


# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


# 任务模型
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('tasks', lazy=True))
    tags = db.relationship('Tag', secondary='task_tag', backref=db.backref('tasks', lazy='dynamic'))


# 标签模型
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)


# 任务 - 标签关联表
task_tag = db.Table('task_tag',
                    db.Column('task_id', db.Integer, db.ForeignKey('task.id')),
                    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
                    )


# 用户加载回调
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# 任务提醒功能
def task_reminder():
    from datetime import datetime
    current_time = datetime.now()
    tasks = Task.query.filter(Task.due_date <= current_time, Task.completed == False).all()
    for task in tasks:
        print(f"提醒: 任务 '{task.title}' 已到期!")


# 启动任务提醒调度器
scheduler = BackgroundScheduler()
scheduler.add_job(func=task_reminder, trigger='interval', minutes=1)
scheduler.start()


# 主页
@app.route('/')
@login_required
def index():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    tags = Tag.query.all()
    return render_template('index.html', tasks=tasks, tags=tags)


# 添加任务页面
@app.route('/add_task_page')
@login_required
def add_task_page():
    return render_template('add_task.html')


# 添加任务
@app.route('/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
    else:
        due_date = None
    tag_names = request.form.getlist('tags')
    new_task = Task(title=title, description=description, due_date=due_date, user=current_user)
    for tag_name in tag_names:
        tag = Tag.query.filter_by(name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            db.session.add(tag)
        new_task.tags.append(tag)
    db.session.add(new_task)
    db.session.commit()
    flash('任务添加成功!')
    return redirect(url_for('index'))


# 完成任务
@app.route('/complete/<int:id>')
@login_required
def complete(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first()
    if task:
        task.completed = not task.completed
        db.session.commit()
    return redirect(url_for('index'))


# 删除任务
@app.route('/delete/<int:id>')
@login_required
def delete(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first()
    if task:
        db.session.delete(task)
        db.session.commit()
    return redirect(url_for('index'))


# 编辑任务页面
@app.route('/edit/<int:id>', methods=['GET'])
@login_required
def edit(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first()
    if task:
        return render_template('edit.html', task=task)
    return redirect(url_for('index'))


# 保存编辑后的任务
@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def save_edit(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first()
    if task:
        task.title = request.form.get('title')
        task.description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        if due_date_str:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        else:
            task.due_date = None
        tag_names = request.form.getlist('tags')
        task.tags = []
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            task.tags.append(tag)
        db.session.commit()
        flash('任务修改成功!')
    return redirect(url_for('index'))


# 注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('用户注册成功!')
        return redirect(url_for('login'))
    return render_template('register.html')


# 登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('用户名或密码无效')
    return render_template('login.html')


# 注销
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# 数据导出
@app.route('/export/<string:format>')
@login_required
def export(format):
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    data = [{'标题': task.title, '描述': task.description, '截止日期': task.due_date, '完成状态': task.completed} for
            task in tasks]
    df = pd.DataFrame(data)
    if format == 'csv':
        df.to_csv('tasks.csv', index=False)
        return 'CSV 导出成功!'
    elif format == 'excel':
        df.to_excel('tasks.xlsx', index=False)
        return 'Excel 导出成功!'
    return '无效的格式'


# 团队协作 API（简单示例）
class TeamTask(Resource):
    def get(self):
        return {'message': '团队任务 API'}


api.add_resource(TeamTask, '/team/tasks')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
