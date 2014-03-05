# app.py

import datetime, os

from flask import flash, request, url_for, render_template, escape, Markup, g, redirect

from flask.ext.api import FlaskAPI, status, exceptions
from flask.ext.api.decorators import set_renderers
from flask.ext.api.renderers import HTMLRenderer
from flask.ext.api.exceptions import APIException
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required
from flask.ext.wtf import Form

from wtforms import TextField, BooleanField
from wtforms.validators import Required
from sqlalchemy import Column, Integer, String, DateTime, Boolean, desc, ForeignKey
from unipath import Path
import bleach
import filters

TEMPLATE_DIR = Path(__file__).ancestor(1).child("templates")

app = FlaskAPI(__name__, template_folder=TEMPLATE_DIR)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SECRET_KEY'] = 'you-will-never-guess'
db = SQLAlchemy(app)

lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'

filters.init_app(app)


class LoginForm(Form):
    username = TextField('username', validators = [Required()])


class User(db.Model):

    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True)
    books = db.relationship('Book', backref='owner', lazy='dynamic')

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def to_json(self):
        return {
            'id': self.id,
            'username': self.username,
            'url': self.url,
            'books': [
                {
                    'id': book.id,
                    'url': book.url,
                }
                for book in self.books.filter_by(deleted=False)
            ],
            'parent_url': request.host_url.rstrip('/') + url_for(
                'users'
            ),
        }

    def __repr__(self):
        return '<User {user}>'.format(user=self.username)

    @property
    def url(self):
        return request.host_url.rstrip('/') + url_for(
            'user_detail',
            key=self.id
        )

    @classmethod
    def get_users(self):
        return [
            user.to_json() for user in User.query.all()
        ]


class Book(db.Model):

    __tablename__ = "book"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String)
    author = Column(String)
    create_date = Column(DateTime, default=datetime.datetime.now())
    start_date = Column(DateTime)
    finish_date = Column(DateTime)
    deleted = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey('user.id'))

    def __repr__(self):
        return "{title} by {author}".format(
            title=self.title,
            author=self.author
        )

    @property
    def url(self):
        return request.host_url.rstrip('/') + url_for(
            'book_detail',
            key=self.id
        )

    def to_json(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'start': self.start_date,
            'finish': self.finish_date,
            'has_finished': self.has_finished,
            'created': self.create_date,
            'owner': self.owner.to_json(),
            'time': self.reading_time.total_seconds(),
            'url': self.url,
            'parent_url': request.host_url.rstrip('/') + url_for(
                'book_list'
            ),
        }

    @property
    def reading_time(self):
        if self.finish_date:
            return self.finish_date - self.start_date
        elif self.start_date:
            return datetime.datetime.now() - self.start_date
        else:
            return datetime.timedelta(0)

    @property
    def has_finished(self):
        return self.start_date and self.finish_date

    @classmethod
    def get_books(self):
        if g.user.is_authenticated():
            return [
                book.to_json() for book in g.user.books.filter_by(
                    deleted=False
                ).order_by(
                    desc(Book.id),
                )
            ]
        else:
            return [
                book.to_json() for book in Book.query.filter_by(
                    deleted=False
                ).order_by(
                    desc(Book.id),
                )
            ]


@app.route("/", methods=['GET'])
@set_renderers([HTMLRenderer])
@login_required
def index():
    return render_template('index.html', books=Book.get_books())


@app.route("/book/<int:key>/", methods=['GET'])
@set_renderers([HTMLRenderer])
@login_required
def book(key):
    book = g.user.books.filter_by(id=key).first()
    if not book:
        raise exceptions.NotFound()
    return render_template('book.html', book=book.to_json())


@app.route("/api/", methods=['GET', 'POST'])
@login_required
def book_list():
    """
    List or create books.
    """
    if request.method == 'POST':
        text = request.data.get('text', '')
        if not text:
            return {
                "message": "Please enter text."
            }, status.HTTP_204_NO_CONTENT
        if "by" not in text:
            return {
                "message": "Expected: {title} by {author}."
            }, status.HTTP_204_NO_CONTENT
        title, author = bleach.clean(text).split('by')
        book = Book(
            title=title.strip(),
            author=author.strip(),
            owner=g.user,
        )
        db.session.add(book)
        db.session.commit()
        return book.to_json(), status.HTTP_201_CREATED

    # request.method == 'GET'
    return Book.get_books(), status.HTTP_200_OK


@app.route("/api/users/", methods=['GET'])
@login_required
def users():
    return User.get_users(), status.HTTP_200_OK


@app.route("/api/users/<int:key>/", methods=['GET'])
@login_required
def user_detail(key):
    user = User.query.get(key)
    if not user:
        raise exceptions.NotFound()
    return user.to_json(), status.HTTP_200_OK


@app.route("/api/latest/", methods=['GET'])
@login_required
def latest():
    try:
        return Book.get_books()[0]
    except IndexError:
        return { "message": "No books" }, status.HTTP_204_NO_CONTENT


@app.route("/api/<int:key>/", methods=['GET', 'PUT', 'DELETE'])
@login_required
def book_detail(key):
    """
    Retrieve, update or delete book instances.
    """
    book = g.user.books.filter_by(id=key).first()

    if request.method == 'PUT':
        text = str(request.data.get('text', ''))
        title, author = bleach.clean(text).split('by') if text else '', ''
        if book:
            book.title, book.author = title.strip(), author.strip()
        else:
            book = Book(
                title=title,
                author=author,
                user=g.user,
            )
        db.session.add(book)
        db.session.commit()
        return book.to_json(), status.HTTP_202_ACCEPTED

    elif request.method == 'DELETE':
        if book:
            book.deleted = True
            db.session.add(book)
            db.session.commit()
        return '', status.HTTP_204_NO_CONTENT

    # request.method == 'GET'
    if not book:
        raise exceptions.NotFound()
    return book.to_json(), status.HTTP_200_OK


@app.route("/api/<int:key>/start/", methods=['PUT'])
@login_required
def book_start(key):
    book = g.user.books.filter_by(id=key).first()
    if book:
        if not book.start_date:
            book.start_date = datetime.datetime.now()
            db.session.add(book)
            db.session.commit()
    else:
        raise exceptions.NotFound()
    return book.to_json(), status.HTTP_202_ACCEPTED


@app.route("/api/<int:key>/finish/", methods=['PUT'])
@login_required
def book_finish(key):
    book = g.user.books.filter_by(id=key).first()
    if book:
        if not book.finish_date and book.start_date:
            book.finish_date = datetime.datetime.now()
            db.session.add(book)
            db.session.commit()
    else:
        raise exceptions.NotFound()
    return book.to_json(), status.HTTP_202_ACCEPTED


@lm.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.before_request
def before_request():
    g.user = current_user


@app.route('/login/', methods = ['GET', 'POST'])
@set_renderers([HTMLRenderer])
def login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            user = User(username=form.username.data)
            db.session.add(user)
            db.session.commit()
        login_user(user)
        flash("Logged in successfully.")
        return redirect(request.args.get("next") or url_for("index"))
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)