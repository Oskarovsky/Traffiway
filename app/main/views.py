import json
import tempfile

import herepy
from datetime import datetime

import requests

from flask import render_template, session, redirect, url_for, current_app, flash, request, jsonify
from flask_login import login_required, current_user

from . import main
from .forms import NameForm, EditProfileForm, EditProfileAdminForm, PostForm, MapForm

from .. import db
from ..decorators import admin_required
from ..models import User, Role, Post
from ..email import send_email

geocoderApi = herepy.GeocoderApi('Wtz4pThMbs_tIMzmaBfNlIIB39uWirtBfi55snakm-M')
routingApi = herepy.RoutingApi('Wtz4pThMbs_tIMzmaBfNlIIB39uWirtBfi55snakm-M')
response = geocoderApi.free_form('200 S Mathilda Sunnyvale CA')


@main.route('/', methods=['GET', 'POST'])
@main.route('/index', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.body.data, localization=form.localization.data, author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['TRAFFIWAY_POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts, current_time=datetime.utcnow(), pagination=pagination)


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['TRAFFIWAY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('user.html', user=user, posts=posts, pagination=pagination)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.company = form.company.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.company.data = current_user.company
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.company = form.company.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        db.session.commit()
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.company.data = user.company
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/map', methods=['GET', 'POST'])
def map():
    form = MapForm()
    if form.validate_on_submit():
        start_place = form.start_place.data
        start_point = geocoderApi.free_form(start_place)
        start_dict = json.loads(start_point.as_json_string())
        start_dict1 = start_dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']

        next_place = form.next_place.data
        next_point = geocoderApi.free_form(next_place)
        next_dict = json.loads(next_point.as_json_string())
        next_dict1 = next_dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']

        start_point_positions = str(start_dict1['Latitude']) + ',' + str(start_dict1['Longitude'])
        next_point_positions = str(next_dict1['Latitude']) + ',' + str(next_dict1['Longitude'])

        # response = routingApi.car_route(start_dict1,
        #                                 next_dict1)
        response = routingApi.car_route([start_dict1['Latitude'], start_dict1['Longitude']],
                                        [next_dict1['Latitude'], next_dict1['Longitude']],
                                        [herepy.RouteMode.car, herepy.RouteMode.fastest])
        return render_template('map.html', form=form, start_point=start_dict1, next_point=next_dict1, response=response,
                               start_point_positions=json.dumps(start_point_positions),
                               next_point_positions=json.dumps(next_point_positions))
    return render_template('map.html', form=form)


@main.route('/geocode', methods=['GET'])
def handle_geocode():
    geocoderApi = herepy.GeocoderApi(current_app.config['HERE_API_KEY'])
    response = geocoderApi.free_form('200 S Mathilda Sunnyvale CA')
    return response.as_json_string()

