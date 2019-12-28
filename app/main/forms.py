from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class NameForm(FlaskForm):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')


class EditProfileForm(FlaskForm):
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    company = StringField('Company', validators=[Length(0, 64)])
    submit = SubmitField('Submit')
