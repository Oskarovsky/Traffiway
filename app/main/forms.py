from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, BooleanField, SelectField, FloatField, DateTimeField
from wtforms.validators import DataRequired, Length, Email, Regexp, ValidationError

from app.models import Role, User


class NameForm(FlaskForm):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')


class EditProfileForm(FlaskForm):
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    company = StringField('Company', validators=[Length(0, 64)])
    submit = SubmitField('Submit')


class EditProfileAdminForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(1, 64), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(1, 64),
                                                   Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                                          'Usernames must have only letters, numbers, dots or '
                                                          'underscores')])
    confirmed = BooleanField('Confirmed')
    role = SelectField('Role', coerce=int)
    company = StringField('Company', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name) for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if field.data != self.user.username and User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already in use.')


class PostForm(FlaskForm):
    body = TextAreaField("What's happened on the street?", validators=[DataRequired()])
    localization = StringField("Place (localization)", validators=[DataRequired()])
    submit = SubmitField('Submit')


class ItemForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(0, 64)])
    info = TextAreaField('Additional info')
    weight = FloatField('Weight [kg]')
    length = FloatField('Length [m]')
    width = FloatField('Width [m]')
    height = FloatField('Height [m]')
    journey_id = SelectField(u'Journey', coerce=int)
    submit = SubmitField('Submit')


class MapForm(FlaskForm):
    start_place = StringField('Start place', validators=[DataRequired(), Length(0, 64)])
    next_place1 = StringField('Next place', validators=[DataRequired(), Length(0, 64)])
    next_place2 = StringField('Next place2', validators=[Length(0, 64)])
    next_place3 = StringField('Next place3', validators=[Length(0, 64)])
    next_place4 = StringField('Next place4', validators=[Length(0, 64)])
    next_place5 = StringField('Next place5', validators=[Length(0, 64)])
    next_place6 = StringField('End place', validators=[Length(0, 64)])
    start_time = DateTimeField('Start time',  format='%Y-%m-%d %H:%M')
    title = StringField('Title')
    submit = SubmitField('Show')
