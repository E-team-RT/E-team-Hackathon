from flask import Flask, request, redirect, render_template, session, flash, abort, url_for
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import uuid
import re
import os
import time

from models import User , Post, Comment



# 定数定義
EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
SESSION_DAYS = 1 #ログイン状態の保存日数
LOCK_START_TIME = "21:00:00"  #ロック開始時刻
LOCK_END_TIME = "06:00:00" #ロック解除時刻
LOCK_LIMIT_SECONDS = 3600 #ログインからロックまでの時間（秒）


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', uuid.uuid4().hex)
app.permanent_session_lifetime = timedelta(days=SESSION_DAYS) #ここでログイン状態の期限設定

csrf = CSRFProtect(app)

jst = ZoneInfo("Asia/Tokyo")


#ページ移動や操作時のガード処理（21時以降は直接アクセスも防ぐ）
@app.before_request
def check_lock_time():
  #下記にアクセスしてきたら、なにもせずに次の処理へ
  allowed_endpoints = [
      "lock_view", #ロック時間外には直接アクセスできないように設定済
      "static",
      "time_api" #URLからは直接アクセスできないように設定済
  ]
  if request.endpoint in allowed_endpoints:
    return
  
  if check_is_locked() == True:
    return redirect(url_for("lock_view"))


#ロック時間かどうかを判定 True=ロック時間
def check_is_locked():
    time_datetime = datetime.now(jst)
    current_time = time_datetime.strftime("%H:%M:%S")

    #21:00:00〜翌05:59:59の間かチェック
    if LOCK_START_TIME <= current_time or current_time < LOCK_END_TIME:
    # if LOCK_START_TIME <= current_time < LOCK_END_TIME: #テスト用
        return True

    #ログイン経過時間チェック
    if session.get('login_time'):
        login_time = datetime.fromisoformat(session['login_time'])
        elapsed_time = time_datetime - login_time
        if elapsed_time.total_seconds() >= LOCK_LIMIT_SECONDS:
            return True
    return False
  

# ルートページのリダイレクト処理
@app.route('/', methods=['GET'])
def index():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    return redirect(url_for('home_view'))


# サインアップページの表示
@app.route('/signup', methods=['GET'])
def signup_view():
    if session.get('user_id') is not None:
        return redirect(url_for('home_view'))
    return render_template('auth/signup.html')


# サインアップ処理
@app.route('/signup', methods=['POST'])
def signup_process():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    password_confirmation = request.form.get('password_confirmation', '')

    # 空チェック
    if not name or not email or not password or not password_confirmation:
        flash("空のフォームがあります" , 'error')
        return redirect(url_for('signup_view'))

    # パスワード一致チェック
    if password != password_confirmation:
        flash('二つのパスワードの値が違っています','error')
        return redirect(url_for('signup_view'))

    # メール形式チェック
    if re.match(EMAIL_PATTERN, email) is None:
        flash('正しいメールアドレスの形式ではありません','error')
        return redirect(url_for('signup_view'))

    # 既存ユーザーチェック
    registered_user = User.find_by_email(email)
    if registered_user is not None:
        flash('既に登録されているメールアドレスです','error')
        return redirect(url_for('signup_view'))

    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    user_id = User.create(name, email, hashed_password)

    session['user_id'] = user_id

    return redirect(url_for('home_view'))


# ログインページの表示
@app.route('/login', methods=['GET'])
def login_view():
    if session.get('user_id') is not None:
        return redirect(url_for('home_view'))
    return render_template('auth/login.html')


# ログイン処理
@app.route('/login', methods=['POST'])
def login_process():
    email = request.form.get('email')
    password = request.form.get('password')

    if email =='' or password == '':
        flash('メールアドレスorパスワードが空です','error')
    else:
        user = User.find_by_email(email)
        if user is None:
            flash('メールアドレスorパスワードが違います','error')
        else:
            hashPassword = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if hashPassword != user["password"]:
                flash('メールアドレスorパスワードが違います','error')
            else:
                session['user_id'] = user["id"]
                 # ログインした時刻を保存
                session['login_time'] = datetime.now().isoformat()

                return redirect(url_for('home_view'))
    return redirect(url_for('login_view'))


# ログアウト
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_view'))


# カテゴリ選択で投稿作成画面を表示
@app.route('/posts', methods=['GET'])
@app.route('/posts/<category>', methods=['GET'])
def posts_view(category=None):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    else:
        posts = Post.get_all()
        for post in posts:
            post['created_at'] = post['created_at'].strftime('%Y-%m-%d %H:%M')
            # 登校時間がいるか？要検討
            post['user_name'] = User.get_name_by_id(post['user_id'])

        return render_template('post/posts.html',category=category, posts=posts, user_id=user_id)

# カテゴリ選択 投稿処理
@app.route('/posts/<category>', methods=['POST'])
def create_post(category):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    content = request.form.get('content', '').strip()
    
    if content == '':
        flash('投稿内容が空です','error')
        return redirect(url_for('posts_view'))
    Post.create(user_id, content, category)
    flash('投稿が完了しました','success')
    return redirect(url_for('posts_view'))

""" # 投稿一覧ページの表示
@app.route('/posts', methods=['GET'])
def posts_view():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    else:
        posts = Post.get_all()
        for post in posts:
            post['created_at'] = post['created_at'].strftime('%Y-%m-%d %H:%M')
            post['user_name'] = User.get_name_by_id(post['user_id'])

        return render_template('post/posts.html', posts=posts, user_id=user_id)
 """

# 投稿処理
""" @app.route('/posts', methods=['POST'])
def create_post():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    content = request.form.get('content', '').strip()
    if content == '':
        flash('投稿内容が空です','error')
        return redirect(url_for('posts_view'))
    Post.create(user_id, content)
    flash('投稿が完了しました','success')
    return redirect(url_for('posts_view')) """

# 投稿削除処理
""" @app.route('/posts/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))

    post = Post.find_by_id(post_id)
    if post is None:
        abort(404)

    if post['user_id'] != user_id:
        flash('この投稿を削除することはできません', 'error')
        return redirect(url_for('posts_view'))

    Post.delete(post_id)
    flash('投稿が削除されました','success')
    return redirect(url_for('posts_view')) """

# 投稿詳細ページの表示
""" @app.route('/posts/<int:post_id>', methods=['GET'])
def post_detail_view(post_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    post = Post.find_by_id(post_id)
    if post is None:
        abort(404)
    post['created_at'] = post['created_at'].strftime('%Y-%m-%d %H:%M')
    post['user_name'] = User.get_name_by_id(post['user_id'])

    comments = Comment.get_by_post_id(post_id)
    for comment in comments:
        comment['created_at'] = comment['created_at'].strftime('%Y-%m-%d %H:%M')
        comment['user_name'] = User.get_name_by_id(comment['user_id'])

    return render_template('post/post_detail.html', post=post, comments = comments, user_id=user_id)
 """
""" # コメント処理
@app.route('/posts/<int:post_id>/comments', methods=['POST'])
def create_comment(post_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    content = request.form.get('content', '').strip()
    if content == '':
        flash('コメント内容が空です','error')
        return redirect(url_for('post_detail_view', post_id=post_id))
    Comment.create(user_id, post_id, content)
    flash('コメントの投稿が完了しました','success')
    return redirect(url_for('post_detail_view', post_id=post_id)) """

#時刻取得処理
@app.route('/api', methods=['GET'])
def time_api():
    #JavaScriptからの通信（合言葉）がない直接アクセスは弾く
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        if session.get('user_id'):
            return redirect(url_for('home_view'))
        return redirect(url_for('login_view'))
    is_locked = check_is_locked()
    return {"is_locked": is_locked} #ロックの判断をブラウザに渡す

#ロック画面
@app.route('/lock', methods=['GET'])
def lock_view():
    #ロック時間でないときはロック画面にアクセスできない
    if not check_is_locked():
        if session.get('user_id'):
            return redirect(url_for('home_view'))
        return redirect(url_for('login_view'))
    session.clear()
    return render_template('error_lock/lock.html')


# 動作確認用みるページの表示
@app.route('/home', methods=['GET'])
def home_view():
    return render_template('home.html')

# ユーザー名で投稿検索
@app.route('/username_search', methods=['POST'])
def posts_search_by_name():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    name = request.form.get('username_search', '').strip()
    if name == '':
        flash('ともだちのなまえが空です', 'error')
        return redirect(url_for('home_view'))
    target_user_id = User.get_id_by_name(name)
    if target_user_id is None:
        flash('ともだちがみつかりません', 'error')
        return redirect(url_for('home_view'))
    posts = Post.get_posts_by_name(name)
    if not posts:
        flash('ともだちのよりみちがありません', 'error')
        return redirect(url_for('home_view'))        
    for post in posts:
        post['created_at'] = post['created_at'].strftime('%Y-%m-%d %H:%M')
    return render_template('home.html', posts=posts, name=name)

# カテゴリボタンで投稿閲覧
@app.route('/category_search/<int:category_id>', methods=['GET'])
def posts_search_by_category(category_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_view'))
    posts = Post.get_posts_by_category(category_id)     
    for post in posts:
        post['created_at'] = post['created_at'].strftime('%Y-%m-%d %H:%M')
    return render_template('home.html', posts=posts)
    

@app.errorhandler(400)
def bad_request(error):
    return render_template('error_lock/400.html'), 400

@app.errorhandler(404)
def page_not_found(error):
    return render_template('error_lock/404.html'),404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error_lock/500.html'),500

@app.context_processor
def inject_login_duration():

    login_duration = ""

    if session.get('login_time'):

        login_time = datetime.fromisoformat(
            session['login_time']
        )

        elapsed = datetime.now() - login_time

        hours = elapsed.seconds // 3600

        minutes = (elapsed.seconds % 3600) // 60

        login_duration = f"{hours}時間{minutes}分"

    return dict(login_duration=login_duration)



if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
