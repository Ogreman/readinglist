# app.py

import datetime, os

from flask import request, url_for, render_template, escape, Markup
from flask.ext.api import FlaskAPI, status, exceptions
from flask.ext.api.decorators import set_renderers
from flask.ext.api.renderers import HTMLRenderer
from flask.ext.api.exceptions import APIException
from flask.ext.sqlalchemy import SQLAlchemy

from sqlalchemy import Column, Integer, String, DateTime, Boolean, desc
from unipath import Path
import bleach

TEMPLATE_DIR = Path(__file__).ancestor(1).child("templates")

app = FlaskAPI(__name__, template_folder=TEMPLATE_DIR)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)


class Book(db.Model):

    __tablename__ = "book"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String)
    author = Column(String)
    create_date = Column(DateTime, default=datetime.datetime.now())
    start_date = Column(DateTime)
    finish_date = Column(DateTime)
    deleted = Column(Boolean, default=False)

    def __repr__(self):
        return "{title} by {author}".format(
            title=self.title,
            author=self.author
        )

    def to_json(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'start': self.start_date,
            'finish': self.finish_date,
            'created': self.create_date,
            'time': self.reading_time.total_seconds(),
            'url': request.host_url.rstrip('/') + url_for(
                'book_detail',
                key=self.id
            ),
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

    @classmethod
    def get_books(self):
        return [
            book.to_json() for book in Book.query.filter(
                Book.deleted == False
            ).order_by(
                desc(Book.id),
            )
        ]


@app.route("/", methods=['GET'])
@set_renderers([HTMLRenderer])
def index():
    return render_template('index.html', books=Book.get_books())


@app.route("/api/", methods=['GET', 'POST'])
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
        title, author = bleach.clean(text).replace(" ", "").split('by')
        book = Book(
            title=title,
            author=author,
        )
        db.session.add(book)
        db.session.commit()
        return book.to_json(), status.HTTP_201_CREATED

    # request.method == 'GET'
    return Book.get_books(), status.HTTP_200_OK


@app.route("/api/latest/", methods=['GET'])
def latest():
    try:
        return Book.get_books()[0]
    except IndexError:
        return { "message": "No books" }, status.HTTP_204_NO_CONTENT


@app.route("/api/<int:key>/", methods=['GET', 'PUT', 'DELETE'])
def book_detail(key):
    """
    Retrieve, update or delete book instances.
    """
    book = Book.query.get(key)

    if request.method == 'PUT':
        text = str(request.data.get('text', ''))
        title, author = bleach.clean(text).replace(
            " ",
            ""
        ).split('by') if text else '', ''
        if book:
            book.title, book.author = title, author
        else:
            book = Book(
                title=title,
                author=author,
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
def book_start(key):
    book = Book.query.get(key)

    if book:
        if not book.start_date:
            book.start_date = datetime.datetime.now()
            db.session.add(book)
            db.session.commit()
    else:
        raise exceptions.NotFound()
    return book.to_json(), status.HTTP_202_ACCEPTED


@app.route("/api/<int:key>/finish/", methods=['PUT'])
def book_finish(key):
    book = Book.query.get(key)

    if book:
        if not book.finish_date and book.start_date:
            book.finish_date = datetime.datetime.now()
            db.session.add(book)
            db.session.commit()
    else:
        raise exceptions.NotFound()
    return book.to_json(), status.HTTP_202_ACCEPTED


if __name__ == "__main__":
    app.run(debug=True)