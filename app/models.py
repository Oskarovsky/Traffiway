import hashlib, urllib
from urllib.parse import urlencode

from flask import current_app, request
from flask_login import UserMixin, AnonymousUserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

from . import db, login_manager


class Role(db.Model):
    __tablename__ = 'roles'     # defines the name of the table in the database
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permissions(self):
        self.permissions = 0

    # checking if combined permissions value includes the given basic permission
    def has_permission(self, perm):
        return self.permissions & perm == perm

    # function which is trying find existing role by name and update those
    # new role object is creating only for roles that aren't in the database already
    @staticmethod
    def insert_roles():
        # TODO READ TEXT BELOW THAT CODE INTO PDF
        roles = {
            'Guest': [Permission.FIND],
            'User': [Permission.FIND, Permission.OPTIMIZE],
            'Admin': [Permission.FIND, Permission.OPTIMIZE, Permission.ADMIN]
        }
        default_role='User'
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.reset_permissions()
            for perm in roles[r]:
                role.add_permission(perm)
            role.default = (role.name == default_role)
            db.session.add(role)
        db.session.commit()

    def __init__(self, **kwargs):
        super(Role, self).__init__(**kwargs)
        if self.permissions is None:
            self.permissions = 0

    def __repr__(self):
        return '<Role %r>' % self.name


class Permission:
    FIND = 1
    OPTIMIZE = 2
    ADMIN = 4


class User(UserMixin, db.Model):
    __tablename__ = 'users'     # defines the name of the table in the database
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(64))
    company = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    avatar_link = db.Column(db.String(64))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    journeys = db.relationship('Journey', backref='author', lazy='dynamic')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    # generate token with a default validity time of one hour
    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id}).decode('utf-8')    # generating cryptographic signature for the data

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))    # decode the token
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id}).decode('utf-8')

    @staticmethod
    def reset_password(token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        user = User.query.get(data.get('reset'))
        if user is None:
            return False
        user.password = new_password
        db.session.add(user)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email}).decode('utf-8')

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = self.gravatar_hash()
        db.session.add(self)
        return True

    # evaluating whether a user has a given permission
    def can(self, perm):
        return self.role is not None and self.role.has_permission(perm)

    def is_administrator(self):
        return self.can(Permission.ADMIN)

    # refreshing a user's last visit time
    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    # gravatar URL generation
    def gravatar(self, size=100, default='retro', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://secure.gravatar.com/avatar'
        hash = self.avatar_hash or self.gravatar_hash()
        return '{url}/{hash}?d={default}&r={rating}&s={size}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def gravatar_hash(self):
        return hashlib.md5(self.email.lower().encode('utf-8')).hexdigest()

    def __repr__(self):
        return '<User %r>' % self.username

    # User constructor
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['TRAFFIWAY_ADMIN']:
                self.role = Role.query.filter_by(name='Administrator').first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = self.gravatar_hash()



class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    localization = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class Danger(db.Model):
    __tablename__ = 'dangers'
    id = db.Column(db.Integer, primary_key=True)
    place = db.Column(db.String(64))
    position = db.Column(db.String(64))
    position_center = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


class Journey(db.Model):
    __tablename__ = 'journeys'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64))
    start_localization = db.Column(db.String(64))
    start_time = db.Column(db.DateTime, index=True)
    destination = db.Column(db.String(64))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class Car(db.Model):
    __tablename__ = "cars"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    capacity_length = db.Column(db.Float)
    capacity_weight = db.Column(db.Float)
    capacity_width = db.Column(db.Float)
    capacity_height = db.Column(db.Float)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    info = db.Column(db.Text)
    weight = db.Column(db.Float)
    length = db.Column(db.Float)
    width = db.Column(db.Float)
    height = db.Column(db.Float)
    journey_id = db.Column(db.Integer, db.ForeignKey('journeys.id'))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

