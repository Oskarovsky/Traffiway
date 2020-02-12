import base64
import io
import json
import os
import tempfile
import googlemaps

#import tkinter
import numpy
import matplotlib.pyplot as plt
from markupsafe import Markup
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

import herepy
from datetime import datetime
from sqlalchemy import text

import requests

from flask import render_template, session, redirect, url_for, current_app, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from wtforms import ValidationError
from werkzeug.utils import secure_filename

from . import main
from .forms import NameForm, EditProfileForm, EditProfileAdminForm, PostForm, MapForm, ItemForm, CarForm

from .. import db
from ..decorators import admin_required
from ..models import User, Role, Post, Danger, Item, Journey, Car
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
        position_json = json.loads(position.as_json_string())['Response']['View'][0]['Result'][0]['Location'][
            'DisplayPosition']

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


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['UPLOAD_FOLDER']


def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('add_item'))


@main.route('/route/<int:journey_id>/package', methods=['GET', 'POST'])
@login_required
def add_item(journey_id):
    form = ItemForm()
    points = []
    route = Journey.query.filter_by(id=journey_id).first_or_404()
    items_number = Item.query.filter(Item.journey_id == journey_id).count()
    car = Car.query.filter(Car.id == route.car_id).first_or_404()

    end_point = Journey.query.filter_by(id=journey_id).first().end_localization
    if end_point is not None:
        points.append([0, end_point])
    point1 = Journey.query.filter_by(id=journey_id).first().next_localization1
    if point1 != 'null' and point1 is not None:
        points.append([1, point1])
    point2 = Journey.query.filter_by(id=journey_id).first().next_localization2
    if point2 != 'null' and point2 is not None:
        points.append([2, point2])
    point3 = Journey.query.filter_by(id=journey_id).first().next_localization3
    if point3 != 'null' and point3 is not None:
        points.append([3, point3])
    point4 = Journey.query.filter_by(id=journey_id).first().next_localization4
    if point4 != 'null' and point4 is not None:
        points.append([4, point4])
    point5 = Journey.query.filter_by(id=journey_id).first().next_localization5
    if point5 != 'null' and point5 is not None:
        points.append([5, point5])
    available_points = points
    points_list = [(j[0], j[1]) for j in available_points]
    form.target.choices = points_list
    journey = Journey.query.filter_by(id=journey_id).first()
    used_space_x = journey.used_capacity_width
    used_space_y = journey.used_capacity_height
    used_space_z = journey.used_capacity_length

    if form.validate_on_submit():
        result = placement_algorithm(form.width.data, form.height.data, form.length.data,
                                     journey.free_capacity_width, journey.free_capacity_height,
                                     journey.free_capacity_length,
                                     car.capacity_width, car.capacity_height, car.capacity_length,
                                     used_space_x, used_space_y, used_space_z)
        print(result)

        item1_position_x = result[6]
        item1_position_y = result[7]
        item1_position_z = result[8]

        journey.free_capacity_weight -= form.weight.data
        journey.free_capacity_width = car.capacity_width - result[9]
        journey.free_capacity_height = car.capacity_height - result[10]
        journey.free_capacity_length = car.capacity_length - result[11]

        journey.used_capacity_weight += form.weight.data
        journey.used_capacity_width = result[9]
        journey.used_capacity_height = result[10]
        journey.used_capacity_length = result[11]

        item = Item(name=form.name.data, info=form.info.data, weight=form.weight.data, length=form.length.data,
                    width=form.width.data, height=form.height.data, journey_id=journey_id,
                    position_x=item1_position_x, position_y=item1_position_y, position_z=item1_position_z,
                    target=points_list[form.target.data][1], author_id=current_user.id)

        if not result[12]:
            flash('There are no free space enough for that item in the vehicle')
        else:
            db.session.add(item)
            db.session.commit()
        return redirect(url_for('.show_route', id=journey_id))

    return render_template('add_item.html', form=form)


@main.route('/car', methods=['GET', 'POST'])
@login_required
def add_car():
    form = CarForm()
    if form.validate_on_submit():
        car = Car(name=form.name.data, capacity_height=form.capacity_height.data,
                  capacity_length=form.capacity_length.data, capacity_weight=form.capacity_weight.data,
                  capacity_width=form.capacity_width.data, author_id=current_user.id)
        db.session.add(car)
        db.session.commit()
        return redirect(url_for('.show_cars', ))
    return render_template('add_car.html', form=form)


@main.route('/all-items', methods=['GET'])
@login_required
def show_items():
    available_journeys = Journey.query.filter(Journey.author_id == current_user.id)
    available_items = Item.query.filter(Item.author_id == current_user.id)
    return render_template('all_items.html', available_items=available_items, available_journeys=available_journeys)


@main.route('/all-routes', methods=['GET'])
@login_required
def show_routes():
    available_journeys = Journey.query.filter(Journey.author_id == current_user.id)
    available_items = Item.query.filter(Item.author_id == current_user.id)
    return render_template('all_routes.html', available_items=available_items, available_journeys=available_journeys)


@main.route('/all-cars', methods=['GET'])
@login_required
def show_cars():
    cars = Car.query.filter(Car.author_id == current_user.id)
    return render_template('all_cars.html', cars=cars)


@main.route('/car/<int:id>', methods=['GET', 'POST'])
@login_required
def show_car(id):
    car = Car.query.filter_by(id=id).first_or_404()
    return render_template('car.html', car=car)


@main.route('/3d/<int:id>', methods=['GET', 'POST'])
def cargo(id):
    route = Journey.query.filter_by(id=id).first_or_404()
    car = Car.query.filter(Car.id == route.car_id).first_or_404()
    return render_template('cargo.html', route=route, car=car)


def placement_algorithm(item_x, item_y, item_z, free_space_x, free_space_y, free_space_z,
                        capacity_x, capacity_y, capacity_z, used_x, used_y, used_z):
    if item_x < free_space_x and item_y < free_space_y and item_z < free_space_z:
        position_x = 0 - capacity_x/2 + item_x/2 + used_x
        position_y = 0 - capacity_y/2 + item_y/2
        position_z = 0 - capacity_z/2 + item_z/2
        used_x += item_x
        used_y += item_y
        used_z += 0
        return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
               position_x, position_y, position_z, used_x, used_y, used_z, True
    elif item_x < free_space_x and item_y < free_space_y and item_z > free_space_z:
        if item_z < free_space_y and item_y < free_space_z:
            temp = item_y
            item_y = item_z
            item_z = temp
            position_x = 0 - capacity_x / 2 + item_x / 2 + used_x
            position_y = 0 - capacity_y / 2 + item_y / 2
            position_z = 0 - capacity_z / 2 + item_z / 2
            used_x += item_x
            used_y += item_y
            used_z += 0
            return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
                   position_x, position_y, position_z, used_x, used_y, used_z, True
        elif item_z < free_space_x and item_x < free_space_z:
            temp = item_x
            item_x = item_z
            item_z = temp
            position_x = 0 - capacity_x / 2 + item_x / 2 + used_x
            position_y = 0 - capacity_y / 2 + item_y / 2
            position_z = 0 - capacity_z / 2 + item_z / 2
            used_x += item_x
            used_y += item_y
            used_z += 0
            return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
                   position_x, position_y, position_z, used_x, used_y, used_z, True
    elif item_x < free_space_x and item_y > free_space_y and item_z < free_space_z:
        if item_y < free_space_z and item_z < free_space_y:
            temp = item_z
            item_z = item_y
            item_y = temp
            position_x = 0 - capacity_x / 2 + item_x / 2 + used_x
            position_y = 0 - capacity_y / 2 + item_y / 2
            position_z = 0 - capacity_z / 2 + item_z / 2
            used_x += item_x
            used_y += free_space_y - item_y
            used_z += 0
            return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
                   position_x, position_y, position_z, used_x, used_y, used_z, True
        elif item_y < free_space_x and item_x < free_space_y:
            temp = item_x
            item_x = item_y
            item_y = temp
            position_x = 0 - capacity_x / 2 + item_x / 2 + used_x
            position_y = 0 - capacity_y / 2 + item_y / 2
            position_z = 0 - capacity_z / 2 + item_z / 2
            used_x += item_x
            used_y += free_space_y - item_y
            used_z += 0
            return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
                   position_x, position_y, position_z, used_x, used_y, used_z, True
    elif item_x > free_space_x and item_y < free_space_y and item_z < free_space_z:
        if item_x < free_space_z and item_z < free_space_x:
            temp = item_z
            item_z = item_x
            item_x = temp
            position_x = 0 - capacity_x / 2 + item_x / 2 + used_x
            position_y = 0 - capacity_y / 2 + item_y / 2
            position_z = 0 - capacity_z / 2 + item_z / 2
            used_x += item_x
            used_y += item_y
            used_z += 0
            return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
                   position_x, position_y, position_z, used_x, used_y, used_z, True
        elif item_x < free_space_y and item_y < free_space_x:
            temp = item_y
            item_y = item_x
            item_x = temp
            position_x = 0 - capacity_x / 2 + item_x / 2 + used_x
            position_y = 0 - capacity_y / 2 + item_y / 2
            position_z = 0 - capacity_z / 2 + item_z / 2
            used_x += item_x
            used_y += item_y
            used_z += 0
            return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
                   position_x, position_y, position_z, used_x, used_y, used_z, True
    else:
        flash('The are no enough available space')
        #return redirect(url_for('main.index'))
        position_x = 0
        position_y = 0
        position_z = 0
        return item_x, item_y, item_z, free_space_x, free_space_y, free_space_z, \
               position_x, position_y, position_z, used_x, used_y, used_z, True



@main.route('/route/<int:id>', methods=['GET', 'POST'])
@login_required
def show_route(id):
    route = Journey.query.filter_by(id=id).first_or_404()
    items = Item.query.filter(Item.journey_id == id).all()
    items_number = Item.query.filter(Item.journey_id == id).count()
    car = Car.query.filter(Car.id == route.car_id).first_or_404()
    all_dangers = [Danger.position for Danger in Danger.query.all()]
    danger_list = '!'.join(all_dangers)
    item1_dimension = None
    item1_position = None
    if items_number >= 1:
        item1_dimension = [items[0].width, items[0].height, items[0].length]
        item1_position = [items[0].position_x, items[0].position_y, items[0].position_z]

    item2_dimension = None
    item2_position = None
    if items_number >= 2:
        item2_dimension = [items[1].width, items[1].height, items[1].length]
        item2_position = [items[1].position_x, items[1].position_y, items[1].position_z]


    item3_dimension = None
    item3_position = None
    if items_number >= 3:
        item3_dimension = [items[2].width, items[2].height, items[2].length]
        item3_position = [items[2].position_x, items[2].position_y, items[2].position_z]

    item4_dimension = None
    item4_position = None
    if items_number >= 4:
        item4_dimension = [items[3].width, items[3].height, items[3].length]
        item4_position = [items[3].position_x, items[3].position_y, items[3].position_z]

    item5_dimension = None
    item5_position = None
    if items_number >= 5:
        item5_dimension = [items[4].width, items[4].height, items[4].length]
        item5_position = [items[4].position_x, items[4].position_y, items[4].position_z]

    return render_template('route.html', journey=route, items=items, car=car, id=id,
                           danger_list=json.dumps(danger_list), items_number=items_number,
                           item1_position=item1_position, item1_dimension=item1_dimension,
                           item2_position=item2_position, item2_dimension=item2_dimension,
                           item3_position=item3_position, item3_dimension=item3_dimension,
                           item4_position=item4_position, item4_dimension=item4_dimension,
                           item5_position=item5_position, item5_dimension=item5_dimension)


@main.route('/map', methods=['GET', 'POST'])
def map():
    form = MapForm()
    temp_counter = 0

    available_vehicles = Car.query.filter(Car.author_id == current_user.id)
    vehicles_list = [(j.id, j.name) for j in available_vehicles]
    form.car_id.choices = vehicles_list

    if form.validate_on_submit():
        start_place = form.start_place.data
        start_point = geocoderApi.free_form(start_place)
        start_dict = json.loads(start_point.as_json_string())
        start_dict_json = start_dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
        start_point_positions = str(start_dict_json['Latitude']) + ',' + str(start_dict_json['Longitude'])

        end_place = form.end_place.data
        end_point = geocoderApi.free_form(end_place)
        end_dict = json.loads(end_point.as_json_string())
        end_dict_json = end_dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
        end_point_positions = str(end_dict_json['Latitude']) + ',' + str(end_dict_json['Longitude'])
        temp_counter += 1

        route_between_start_and_end = calculate_route(start_dict_json['Latitude'], start_dict_json['Longitude'],
                                                      end_dict_json['Latitude'], end_dict_json['Longitude'])
        time_from_start_to_end = route_between_start_and_end[0]
        distance_from_start_to_end = route_between_start_and_end[1]

        selected_car = Car.query.filter(Car.id == form.car_id.data).first()
        free_capacity_length = selected_car.capacity_length
        free_capacity_weight = selected_car.capacity_weight
        free_capacity_width = selected_car.capacity_width
        free_capacity_height = selected_car.capacity_height

        next_place1 = form.next_place1.data or None
        next_point_positions1 = None
        time_from_start_to_point1 = None
        time_from_point1_to_end = None
        if next_place1 is not None:
            next_point1 = geocoderApi.free_form(next_place1)
            next_dict1 = json.loads(next_point1.as_json_string())
            next_dict1_json = next_dict1['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
            next_point_positions1 = str(next_dict1_json['Latitude']) + ',' + str(next_dict1_json['Longitude'])
            temp_counter += 1

            route_between_start_and_point1 = calculate_route(start_dict_json['Latitude'], start_dict_json['Longitude'],
                                                             next_dict1_json['Latitude'], next_dict1_json['Longitude'])
            time_from_start_to_point1 = route_between_start_and_point1[0]
            distance_from_start_to_point1 = route_between_start_and_point1[1]

            route_between_point1_and_end = calculate_route(next_dict1_json['Latitude'], next_dict1_json['Longitude'],
                                                           end_dict_json['Latitude'], end_dict_json['Longitude'])
            time_from_point1_to_end = route_between_point1_and_end[0]
            distance_from_point1_to_end = route_between_point1_and_end[1]

        next_place2 = form.next_place2.data or None
        next_point_positions2 = None
        time_from_start_to_point2 = None
        time_from_point2_to_end = None
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

            route_between_point1_and_point2 = calculate_route(next_dict1_json['Latitude'], next_dict1_json['Longitude'],
                                                              next_dict2_json['Latitude'], next_dict2_json['Longitude'])
            time_from_point1_to_point2 = route_between_point1_and_point2[0]
            distance_from_point1_to_point2 = route_between_point1_and_point2[1]

            route_between_point2_and_end = calculate_route(next_dict2_json['Latitude'], end_dict_json['Longitude'],
                                                           end_dict_json['Latitude'], end_dict_json['Longitude'])
            time_from_point2_to_end = route_between_point2_and_end[0]
            distance_from_point2_to_end = route_between_point2_and_end[1]

        next_place3 = form.next_place3.data or None
        next_point_positions3 = None
        time_from_start_to_point3 = None
        time_from_point1_to_point3 = None
        time_from_point2_to_point3 = None
        time_from_point3_to_end = None
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

            route_between_point1_and_point3 = calculate_route(next_dict1_json['Latitude'], next_dict1_json['Longitude'],
                                                              next_dict3_json['Latitude'], next_dict3_json['Longitude'])
            time_from_point1_to_point3 = route_between_point1_and_point3[0]
            distance_from_point1_to_point3 = route_between_point1_and_point3[1]

            route_between_point2_and_point3 = calculate_route(next_dict2_json['Latitude'], next_dict2_json['Longitude'],
                                                              next_dict3_json['Latitude'], next_dict3_json['Longitude'])
            time_from_point2_to_point3 = route_between_point2_and_point3[0]
            distance_from_point2_to_point3 = route_between_point2_and_point3[1]

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

        all_dangers = [Danger.position for Danger in Danger.query.all()]
        danger_list = '!'.join(all_dangers)

        if temp_counter == 1:
            end_point_positions = end_point_positions
        elif temp_counter == 2:
            end_point_positions = end_point_positions
            if time_from_start_to_end < time_from_start_to_point1:
                next_point_positions1 = next_point_positions1
            elif time_from_start_to_end > time_from_start_to_point1:
                next_point_positions1 = next_point_positions1
        elif temp_counter == 3:
            end_point_positions = end_point_positions
            if time_from_start_to_point1 < time_from_start_to_point2:
                next_point_positions1 = next_point_positions1
                next_point_positions2 = next_point_positions2
            elif time_from_start_to_point1 > time_from_start_to_point2:
                next_point_positions1 = next_point_positions2
                next_point_positions2 = next_point_positions1
        elif temp_counter == 4:
            end_point_positions = end_point_positions
            if time_from_start_to_point1 < time_from_start_to_point2 and time_from_start_to_point1 < time_from_start_to_point3:
                next_point_positions1 = next_point_positions1
                if time_from_point1_to_point3 < time_from_point1_to_point2:
                    next_point_positions2 = next_point_positions3
                    next_point_positions3 = next_point_positions2
                else:
                    next_point_positions2 = next_point_positions2
                    next_point_positions3 = next_point_positions3
            if time_from_start_to_point2 < time_from_start_to_point1 and time_from_start_to_point2 < time_from_start_to_point3:
                next_point_positions1 = next_point_positions2
                if time_from_point1_to_point2 < time_from_point2_to_point3:
                    next_point_positions2 = next_point_positions1
                    next_point_positions3 = next_point_positions3
                else:
                    next_point_positions2 = next_point_positions3
                    next_point_positions3 = next_point_positions1
            if time_from_start_to_point3 < time_from_start_to_point1 and time_from_start_to_point3 < time_from_start_to_point2:
                next_point_positions1 = next_point_positions3
                if time_from_point1_to_point3 < time_from_point2_to_point3:
                    next_point_positions2 = next_point_positions1
                    next_point_positions3 = next_point_positions2
                else:
                    next_point_positions2 = next_point_positions2
                    next_point_positions3 = next_point_positions1

        journey = Journey(start_localization=form.start_place.data, end_localization=form.end_place.data,
                          next_localization1=form.next_place1.data or None,
                          next_localization2=form.next_place2.data or None,
                          next_localization3=form.next_place3.data or None,
                          next_localization4=form.next_place4.data or None,
                          next_localization5=form.next_place5.data or None,
                          author_id=current_user.id, start_time=form.start_time.data,
                          title=form.title.data + ' [' + form.start_place.data + ' - ' + form.end_place.data + ']',
                          start_point_positions=json.dumps(start_point_positions),
                          end_point_positions=json.dumps(end_point_positions),
                          next_point_positions1=json.dumps(next_point_positions1) or None,
                          next_point_positions2=json.dumps(next_point_positions2) or None,
                          next_point_positions3=json.dumps(next_point_positions3) or None,
                          next_point_positions4=json.dumps(next_point_positions4) or None,
                          next_point_positions5=json.dumps(next_point_positions5) or None,
                          used_capacity_height=0, used_capacity_length=0,
                          used_capacity_weight=0, used_capacity_width=0,
                          free_capacity_length=free_capacity_length,
                          free_capacity_weight=free_capacity_weight,
                          free_capacity_width=free_capacity_width,
                          free_capacity_height=free_capacity_height,
                          localization_counter=temp_counter, car_id=form.car_id.data)

        db.session.add(journey)
        db.session.commit()
        flash(Markup('This route has been added to the database - <a href="/route/'
                     + str(journey.id) + '" class="alert-link">Show the route</a>'))

        return render_template('map.html', form=form,
                               start_point=start_dict_json, next_point=end_dict_json,
                               start_point_positions=json.dumps(start_point_positions),
                               danger_list=json.dumps(danger_list),
                               all_dangers=all_dangers, localization_counter=temp_counter,
                               end_point_positions=json.dumps(end_point_positions),
                               time_from_start_to_end=json.dumps(time_from_start_to_end) or None,
                               time_from_start_to_point1=json.dumps(time_from_start_to_point1) or None,
                               time_from_start_to_point2=json.dumps(time_from_start_to_point2) or None,
                               time_from_start_to_point3=json.dumps(time_from_start_to_point3) or None,
                               time_from_point1_to_end=json.dumps(time_from_point1_to_end) or None,
                               time_from_point2_to_end=json.dumps(time_from_point2_to_end) or None,
                               time_from_point3_to_end=json.dumps(time_from_point3_to_end) or None,
                               time_from_point1_to_point2=json.dumps(time_from_point1_to_point2) or None,
                               next_point_positions1=json.dumps(next_point_positions1) or None,
                               next_point_positions2=json.dumps(next_point_positions2) or None,
                               next_point_positions3=json.dumps(next_point_positions3) or None,
                               next_point_positions4=json.dumps(next_point_positions4) or None,
                               next_point_positions5=json.dumps(next_point_positions5) or None)
    return render_template('map.html', form=form)


@main.route('/geocode', methods=['GET'])
def handle_geocode():
    geocoderApi = herepy.GeocoderApi(current_app.config['HERE_API_KEY'])
    response = geocoderApi.free_form('200 S Mathilda Sunnyvale CA')
    return response.as_json_string()
