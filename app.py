import os
import re
import hmac
import jinja2
import webapp2
from model import db, post_key, users_key, User, Post


secret = 'secret'


# Jinja initialization
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

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
            self.render('mainPage.html', error = msg)




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
            self.render('signUpPage.html', error_message = error_message)
        elif not valid_password(self.password):
            error_message = "That wasn't a valid password."
            self.render('signUpPage.html', error_message = error_message)
        elif self.password != self.verify:
            error_message = "Your passwords didn't match."
            self.render('signUpPage.html', error_message = error_message)
        else:
            self.done()

    def done(self, *a, **kw):
        raise NotImplementedError



class Register(SignUpPage):
    def done(self):
        #make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signUpPage.html', error_username = msg)
        else:
            u = User.register(self.username, self.password)
            u.put()

            self.login(u)
            self.redirect('/blog')



class BlogFront(Register):
    def get(self):
        posts = Post.all().order('-created')
        params = dict(username = self.user.name, posts = posts)
        self.render('blogPage.html', **params)



# New Post Creation
class NewPost(BlogHandler):
    def get(self):
        if self.user:
            self.render("newPostPage.html", username = self.user.name)
        else:
            self.redirect("/")

    def post(self):
        if not self.user:
            self.redirect('/blog')

        title = self.request.get('title')
        content = self.request.get('content')

        if title and content:
            p = Post(parent = post_key(), title = title, content = content, author = self.user.name)
            p.put()
            self.redirect('/blog')
            # self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "Both subject and content are required!"
            self.render("newPostPage.html", title = title, content = content, error = error)



class PostPage(BlogHandler):
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=post_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        if post.author != self.user.name:
            self.redirect('/')

        params = dict(title = post.title, content = post.content, username = self.user.name)

        self.render('editPostPage.html', **params)

    def post(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=post_key())
        post = db.get(key)
        title = self.request.get('title')
        content = self.request.get('content')

        if title and content:
            post.title = title
            post.content = content
            post.put()
            self.redirect('/blog')
        else:
            error = "Both subject and content are required!"
            self.render("newPostPage.html", title = title, content = content, error = error)



class Logout(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/')



app = webapp2.WSGIApplication([('/', MainPage),
                               ('/signup', Register),
                               ('/blog', BlogFront),
                               ('/blog/edit/([0-9]+)', PostPage),
                               ('/blog/newpost', NewPost),
                               ('/signup', Register),
                               ('/logout', Logout)
                               ],
                              debug=True)