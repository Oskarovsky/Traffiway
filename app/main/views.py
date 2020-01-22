import json
import tempfile
import googlemaps

import herepy
from datetime import datetime
from sqlalchemy import text

import requests

from flask import render_template, session, redirect, url_for, current_app, flash, request, jsonify
from flask_login import login_required, current_user
from wtforms import ValidationError

from . import main
from .forms import NameForm, EditProfileForm, EditProfileAdminForm, PostForm, MapForm, ItemForm

from .. import db
from ..decorators import admin_required
from ..models import User, Role, Post, Danger, Item, Journey
from ..email import send_email

geocoderApi = herepy.GeocoderApi('Wtz4pThMbs_tIMzmaBfNlIIB39uWirtBfi55snakm-M')
routingApi = herepy.RoutingApi('Wtz4pThMbs_tIMzmaBfNlIIB39uWirtBfi55snakm-M')
gmaps = googlemaps.Client(key='AIzaSyDIhA2HHd3CCdIQjkSWqFUH3Tw-KFzfz-A')


@main.route('/', methods=['GET', 'POST'])
@main.route('/index', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.body.data, localization=form.localization.data,
                    author=current_user._get_current_object())
        position = geocoderApi.free_form(form.localization.data)
        position_json = json.loads(position.as_json_string())['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']

        latitude_int = float(position_json['Latitude'])
        longitude_int = float(position_json['Longitude'])

        latitude_up = latitude_int + 0.0100
        longitude_up = longitude_int + 0.0100
        latitude_down = latitude_int - 0.0100
        longitude_down = longitude_int - 0.0100
        position_point = str(latitude_int) + ',' + str(longitude_int)
        position_geo = str(latitude_up) + ',' + str(longitude_up) + ';' + str(latitude_down) + ',' + str(longitude_down)
        print(position_geo)

        danger = Danger(place=form.localization.data, position=position_geo, position_center=position_point)

        db.session.add(danger, post)
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


def calculate_route(first_lat, first_lon, second_lat, second_lon):
    distance_request = routingApi.car_route([first_lat, first_lon],
                                             [second_lat, second_lon],
                                             [herepy.RouteMode.car, herepy.RouteMode.fastest])
    response_json = json.loads(distance_request.as_json_string())
    response = response_json['response']['route'][0]['summary']
    return response['travelTime'], response['distance'], response


@main.route('/package', methods=['GET', 'POST'])
@login_required
def add_item():
    form = ItemForm()
    available_journeys = Journey.query.filter(Journey.author_id == current_user.id)
    journey_list = [(j.id, j.title) for j in available_journeys]
    form.journey_id.choices = journey_list
    if form.validate_on_submit():
        item = Item(name=form.name.data, info=form.info.data, weight=form.weight.data, length=form.length.data,
                    width=form.width.data, height=form.height.data, journey_id=form.journey_id.data,
                    author_id=current_user.id)
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('.index'))
    return render_template('add_item.html', form=form)


@main.route('/all-items', methods=['GET'])
@login_required
def show_items():
    available_journeys = Journey.query.filter(Journey.author_id == current_user.id)
    available_items = Item.query.filter(Item.author_id == current_user.id)
    return render_template('all_items.html', available_items=available_items, available_journeys=available_journeys)


@main.route('/map', methods=['GET', 'POST'])
def map():
    form = MapForm()
    temp_counter = 0

    if form.validate_on_submit():
        start_place = form.start_place.data
        start_point = geocoderApi.free_form(start_place)
        start_dict = json.loads(start_point.as_json_string())
        start_dict_json = start_dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
        start_point_positions = str(start_dict_json['Latitude']) + ',' + str(start_dict_json['Longitude'])

        end_place = form.next_place1.data
        end_point = geocoderApi.free_form(end_place)
        end_dict = json.loads(end_point.as_json_string())
        end_dict_json = end_dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
        end_point_positions = str(end_dict_json['Latitude']) + ',' + str(end_dict_json['Longitude'])
        temp_counter += 1

        route_between_start_and_point1 = calculate_route(start_dict_json['Latitude'], start_dict_json['Longitude'],
                        end_dict_json['Latitude'], end_dict_json['Longitude'])
        time_from_start_to_point1 = route_between_start_and_point1[0]
        distance_from_start_to_point1 = route_between_start_and_point1[1]
        response = route_between_start_and_point1[2]
        print(time_from_start_to_point1, distance_from_start_to_point1)

        next_place2 = form.next_place2.data or None
        next_point_positions2 = None
        time_from_start_to_point2 = None
        time_from_point1_to_point2 = None
        if next_place2 is not None:
            next_point2 = geocoderApi.free_form(next_place2)
            next_dict2 = json.loads(next_point2.as_json_string())
            next_dict2_json = next_dict2['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
            next_point_positions2 = str(next_dict2_json['Latitude']) + ',' + str(next_dict2_json['Longitude'])
            temp_counter += 1

            route_between_start_and_point2 = calculate_route(start_dict_json['Latitude'], start_dict_json['Longitude'],
                                                 next_dict2_json['Latitude'], next_dict2_json['Longitude'])
            time_from_start_to_point2 = route_between_start_and_point2[0]
            distance_from_start_to_point2 = route_between_start_and_point2[1]
            response2 = route_between_start_and_point2[2]
            print(time_from_start_to_point2, distance_from_start_to_point2)

            route_between_point1_and_point2 = calculate_route(end_dict_json['Latitude'], end_dict_json['Longitude'],
                        next_dict2_json['Latitude'], next_dict2_json['Longitude'])
            time_from_point1_to_point2 = route_between_point1_and_point2[0]
            distance_from_point1_to_point2 = route_between_point1_and_point2[1]
            print(time_from_point1_to_point2, distance_from_point1_to_point2)

        next_place3 = form.next_place3.data or None
        next_point_positions3 = None
        time_from_start_to_point3 = None
        time_from_point1_to_point3 = None
        time_from_point2_to_point3 = None
        if next_place3 is not None:
            next_point3 = geocoderApi.free_form(next_place3)
            next_dict3 = json.loads(next_point3.as_json_string())
            next_dict3_json = next_dict3['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
            next_point_positions3 = str(next_dict3_json['Latitude']) + ',' + str(next_dict3_json['Longitude'])
            temp_counter += 1

            route_between_start_and_point3 = calculate_route(start_dict_json['Latitude'], start_dict_json['Longitude'],
                                                  next_dict3_json['Latitude'], next_dict3_json['Longitude'])
            time_from_start_to_point3 = route_between_start_and_point3[0]
            distance_from_start_to_point3 = route_between_start_and_point3[1]
            response3 = route_between_start_and_point3[2]
            print(time_from_start_to_point3, distance_from_start_to_point3)

            route_between_point1_and_point3 = calculate_route(end_dict_json['Latitude'], end_dict_json['Longitude'],
                                                             next_dict3_json['Latitude'], next_dict3_json['Longitude'])
            time_from_point1_to_point3 = route_between_point1_and_point3[0]
            distance_from_point2_to_point3 = route_between_point1_and_point3[1]
            response2 = route_between_point1_and_point3[2]
            print(time_from_point1_to_point3, distance_from_point2_to_point3)

        next_place4 = form.next_place4.data or None
        next_point_positions4 = None
        if next_place4 is not None:
            next_point4 = geocoderApi.free_form(next_place4)
            next_dict4 = json.loads(next_point4.as_json_string())
            next_dict4_json = next_dict4['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
            next_point_positions4 = str(next_dict4_json['Latitude']) + ',' + str(next_dict4_json['Longitude'])
            temp_counter += 1

        next_place5 = form.next_place5.data or None
        next_point_positions5 = None
        if next_place5 is not None:
            next_point5 = geocoderApi.free_form(next_place5)
            next_dict5 = json.loads(next_point5.as_json_string())
            next_dict5_json = next_dict5['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
            next_point_positions5 = str(next_dict5_json['Latitude']) + ',' + str(next_dict5_json['Longitude'])
            temp_counter += 1

        next_place6 = form.next_place6.data or None
        next_point_positions6 = None
        if next_place6 is not None:
            next_point6 = geocoderApi.free_form(next_place6)
            next_dict6 = json.loads(next_point6.as_json_string())
            next_dict6_json = next_dict6['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
            next_point_positions6 = str(next_dict6_json['Latitude']) + ',' + str(next_dict6_json['Longitude'])
            temp_counter += 1


        all_dangers = [Danger.position for Danger in Danger.query.all()]
        danger_list = '!'.join(all_dangers)
        print(danger_list)

        journey = Journey(start_localization=form.start_place.data, start_time=form.start_time.data,
                          destination=form.next_place1.data, author_id=current_user.id,
                          title=form.title.data + ' [' + form.start_place.data + ' - ' + form.next_place1.data + ']')
        db.session.add(journey)
        db.session.commit()

        return render_template('map.html', form=form, start_point=start_dict_json, next_point=end_dict_json, response=response,
                               start_point_positions=json.dumps(start_point_positions), danger_list=json.dumps(danger_list),
                               all_dangers=all_dangers, localization_counter=temp_counter,
                               #danger_list_center=json.dumps(danger_list_center),
                               next_point_positions1=json.dumps(end_point_positions),
                               time_from_start_to_point1=json.dumps(time_from_start_to_point1) or None,
                               time_from_start_to_point2=json.dumps(time_from_start_to_point2) or None,
                               time_from_start_to_point3=json.dumps(time_from_start_to_point3) or None,
                               time_from_point1_to_point2=json.dumps(time_from_point1_to_point2) or None,
                               time_from_point1_to_point3=json.dumps(time_from_point1_to_point3) or None,
                               time_from_point2_to_point3=json.dumps(time_from_point2_to_point3) or None,
                               next_point_positions2=json.dumps(next_point_positions2) or None,
                               next_point_positions3=json.dumps(next_point_positions3) or None,
                               next_point_positions4=json.dumps(next_point_positions4) or None,
                               next_point_positions5=json.dumps(next_point_positions5) or None,
                               next_point_positions6=json.dumps(next_point_positions6) or None)
    return render_template('map.html', form=form)


@main.route('/geocode', methods=['GET'])
def handle_geocode():
    geocoderApi = herepy.GeocoderApi(current_app.config['HERE_API_KEY'])
    response = geocoderApi.free_form('200 S Mathilda Sunnyvale CA')
    return response.as_json_string()

