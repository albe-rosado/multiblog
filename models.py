import random
import hashlib
from string import letters
from google.appengine.ext import db


def make_salt(length=5):
    return ''.join(random.choice(letters) for x in xrange(length))


def make_pw_hash(name, pw, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)


def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)


# Users
def users_key(group='default'):
    return db.Key.from_path('users', group)


class User(db.Model):
    name = db.StringProperty(required=True)
    pw_hash = db.StringProperty(required=True)
    registered = db.DateTimeProperty(auto_now_add=True)

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent=users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw):
        pw_hash = make_pw_hash(name, pw)
        return User(parent=users_key(),
                    name=name,
                    pw_hash=pw_hash)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u




# Posts
def post_key(name='default'):
    return db.Key.from_path('blogs', name)


class Post(db.Model):
    title = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    author = db.ReferenceProperty(User, collection_name='posts')
    score = db.IntegerProperty(default=0)
    created = db.DateTimeProperty(auto_now_add=True)

    def likes(post):
        likes = db.GqlQuery("SELECT * FROM Like WHERE parent_post=:post", post=post).count()
        return likes

    def liked(post, user):
        liked = db.GqlQuery("SELECT * FROM Like WHERE parent_post=:post AND author=:user", post=post, user=user).get()
        return liked



# Comments
def comment_key(group='default'):
    return db.Key.from_path('comments', group)


class Comment(db.Model):
    content = db.TextProperty(required=True)
    author = db.ReferenceProperty(User, collection_name='comments')
    parent_post = db.ReferenceProperty(Post, collection_name='comments')
    created = db.DateTimeProperty(auto_now_add=True)



# Likes
def like_key(group='default'):
    return db.Key.from_path('likes', group)


class Like(db.Model):
    author = db.ReferenceProperty(User, collection_name='like')
    parent_post = db.ReferenceProperty(Post, collection_name='like')
