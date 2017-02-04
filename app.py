import os
import re
import hmac
import time
import jinja2
import webapp2
from models import db, post_key, users_key, User, Post, Comment


secret = 'secret'


# Jinja initialization
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir), autoescape=True)


def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)


class BlogHandler(webapp2.RequestHandler):

    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))


# Security Layer
def user_owns_post(self, post):
    if post:
        return self.user.name == post.author.name

def user_logged_in(self):
    return self.user


def comment_belongs_to_post(comment, post_id):
    return comment.parent_post == post_id



# Hashing Methods
def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())


def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


# Input verification methods
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")


def valid_password(password):
    return password and PASS_RE.match(password)



# Home Page (Login)
class MainPage(BlogHandler):

    def get(self):
        self.render('mainPage.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            self.redirect('/blog')
        else:
            msg = 'Invalid login'
            self.render('mainPage.html', error=msg)


# Sign Up Page
class SignUpPage(BlogHandler):

    def get(self):
        self.render("signUpPage.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')

        error_message = ''

        if not valid_username(self.username):
            error_message = "That's not a valid username."
            self.render('signUpPage.html', error_message=error_message)
        elif not valid_password(self.password):
            error_message = "That wasn't a valid password."
            self.render('signUpPage.html', error_message=error_message)
        elif self.password != self.verify:
            error_message = "Your passwords didn't match."
            self.render('signUpPage.html', error_message=error_message)
        else:
            self.done()

    def done(self, *a, **kw):
        raise NotImplementedError


class Register(SignUpPage):
    def done(self):
        # make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signUpPage.html', error_message=msg)
        else:
            u = User.register(self.username, self.password)
            u.put()
            self.login(u)
            self.redirect('/blog')




# Blog Page
class BlogFront(BlogHandler):

    def get(self):
        # checks if user is logged in before showing blog entries
        if user_logged_in(self):
            posts = Post.all().order('-created')
            params = dict(username=self.user.name, posts=posts)
            time.sleep(0.1)
            self.render('blogPage.html', **params)
        else:
            self.redirect('/')



# New Post Creation
class NewPost(BlogHandler):

    def get(self):
        # checks if user is logged in
        if not user_logged_in(self):
            self.redirect('/')
        else:
            self.render("newPostPage.html", username=self.user.name)

    def post(self):
        if not user_logged_in(self):
            self.redirect('/')

        title = self.request.get('title')
        content = self.request.get('content')

        if title and content:
            p = Post(parent=post_key(), title=title,
                     content=content, author=self.user)
            p.put()
            self.redirect('/blog')
            # self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "Both subject and content are required!"
            self.render("newPostPage.html", title=title,
                        content=content, error=error)




# Edit Post Page
class EditPost(BlogHandler):

    def get(self, post_id):
        if not user_logged_in(self):
            return self.redirect('/')

        key = db.Key.from_path('Post', int(post_id), parent=post_key())
        post = db.get(key)
        if not post:
            return self.error(404)
        if user_owns_post(self, post):
            params = dict(title=post.title, content=post.content,
                      username=self.user.name)
            self.render('editPostPage.html', **params)
        else:
            return self.redirect('/')

    def post(self, post_id):
        # checks if user is logged in
        if not user_logged_in(self):
            return self.redirect('/')

        key = db.Key.from_path('Post', int(post_id), parent=post_key())
        post = db.get(key)
        if not post:
            return self.error(404)

        # checks if the user owns the post
        if not user_owns_post(self, post):
            return self.redirect('/')

        title = self.request.get('title')
        content = self.request.get('content')

        if title and content:
            post.title = title
            post.content = content
            post.put()
            self.redirect('/blog')
        else:
            error = "Both subject and content are required!"
            self.render("newPostPage.html", title=title,
                        content=content, error=error)



# Logout
class Logout(BlogHandler):

    def get(self):
        self.logout()
        self.redirect('/')



# Delete Post
class DeletePost(BlogHandler):

    def get(self, post_id):
        if user_logged_in(self):
            key = db.Key.from_path('Post', int(post_id), parent=post_key())
            post = db.get(key)
            if not post:
                return self.error(404)

            if user_owns_post(self, post):
                post.delete()
                self.redirect('/blog')
        else:
            self.redirect('/')



# Posts comments
class CommentPost(BlogHandler):
    def get(self, post_id):
        if user_logged_in(self):
            key = db.Key.from_path('Post', int(post_id), parent=post_key())
            post = db.get(key)
            if not post:
                return self.error(404)

            comments = db.GqlQuery("SELECT * FROM Comment WHERE parent_post = :post", post=post)
            self.render('postComments.html', post=post, comments = comments, username = self.user.name)
        else:
            return self.redirect('/')

    def post(self, post_id):
        if user_logged_in(self):
            key = db.Key.from_path('Post', int(post_id), parent=post_key())
            post = db.get(key)
            if not post:
                return self.error(404)
            # Only posts non-owners can comment
            if not user_owns_post(self, post):
                content = self.request.get('content')
                comment = Comment(parent=comment_key(), content=content, author = self.user, parent_post = post)
                comment.put()
                time.sleep(0.1)
                self.redirect('/blog/comment/%s' % str(post_id))
            else:
                return self.redirect('/blog')



# Edit Comments
class EditComment(BlogHandler):
    pass




# Delete Comments
class DeleteComment(BlogHandler):
    pass


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/signup', Register),
                               ('/logout', Logout),
                               ('/blog', BlogFront),
                               ('/blog/newpost', NewPost),
                               ('/blog/([0-9]+)/edit', EditPost),
                               ('/blog/([0-9]+)/remove', DeletePost),
                               ('/blog/([0-9]+)/comment', CommentPost),
                               ('/blog/([0-9]+)/comment/([0-9]+)/edit', EditComment),
                               ('/blog/([0-9]+)/comment/([0-9]+)/delete', DeleteComment)
                               ],
                              debug=True)


