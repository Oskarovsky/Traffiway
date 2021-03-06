import json
import json
import os
from datetime import datetime

import googlemaps
import herepy
from flask import render_template, redirect, url_for, current_app, flash, request
from flask_login import login_required, current_user
# import tkinter
from markupsafe import Markup
from werkzeug.utils import secure_filename

from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, MapForm, ItemForm, CarForm
from .. import db
from ..decorators import admin_required
from ..models import User, Role, Post, Danger, Item, Journey, Car

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
        page, per_page=current_app.config['TRAFFIWAY_POSTS_PER_PAGE'], error_out=False)
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
    item_parameters = []
    localizations = []
    localizations.insert(0, [route.start_point_positions, route.start_localization])
    localizations.insert(1, [route.end_point_positions, route.end_localization])
    if route.next_point_positions1 is not None:
        localizations.append([route.next_point_positions1, route.next_localization1])
    if route.next_point_positions2 is not None:
        localizations.append([route.next_point_positions2, route.next_localization2])
    if route.next_point_positions3 is not None:
        localizations.append([route.next_point_positions3, route.next_localization3])
    if route.next_point_positions4 is not None:
        localizations.append([route.next_point_positions4, route.next_localization4])
    if route.next_point_positions5 is not None:
        localizations.append([route.next_point_positions5, route.next_localization5])

    iterator = 0
    for item in items:
        item_parameters.append([items[iterator].width, items[iterator].height, items[iterator].length,
                                items[iterator].position_x, items[iterator].position_y, items[iterator].position_z])
        iterator += 1

    return render_template('route.html', journey=route, items=items, car=car, id=id,
                           danger_list=json.dumps(danger_list), items_number=items_number,
                           item_parameters=item_parameters, localizations=localizations,
                           localization_amount=len(localizations))


@main.route('/map', methods=['GET', 'POST'])
def map():
    form = MapForm()
    temp_counter = 0
    available_vehicles = Car.query.filter(Car.author_id == current_user.id)
    vehicles_list = [(j.id, j.name) for j in available_vehicles]
    form.car_id.choices = vehicles_list
    localizations = []
    entry_localizations = []

    if form.validate_on_submit():
        for field, value in form.data.items():
            if value is "" or value is None:
                continue
            if isinstance(value, str):
                if field.startswith("start"):
                    point = geocoderApi.free_form(value)
                    dict = json.loads(point.as_json_string())
                    dict_json = dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
                    point_positions = str(dict_json['Latitude']) + ',' + str(dict_json['Longitude'])
                    localizations.insert(0, [value, dict_json, json.dumps(point_positions)])
                    entry_localizations.insert(0, [value, dict_json, json.dumps(point_positions)])
                elif field.startswith("end"):
                    point = geocoderApi.free_form(value)
                    dict = json.loads(point.as_json_string())
                    dict_json = dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
                    point_positions = str(dict_json['Latitude']) + ',' + str(dict_json['Longitude'])
                    localizations.insert(1, [value, dict_json, json.dumps(point_positions)])
                    entry_localizations.insert(1, [value, dict_json, json.dumps(point_positions)])
                    temp_counter += 1
                elif field.startswith("next"):
                    point = geocoderApi.free_form(value)
                    dict = json.loads(point.as_json_string())
                    dict_json = dict['Response']['View'][0]['Result'][0]['Location']['DisplayPosition']
                    point_positions = str(dict_json['Latitude']) + ',' + str(dict_json['Longitude'])
                    localizations.append([value, dict_json, json.dumps(point_positions)])
                    entry_localizations.append([value, dict_json, json.dumps(point_positions)])
                    temp_counter += 1
        for field, value in form.data.items():
            if value is "" or value is None:
                localizations.append([value, None, None])
        print(localizations)

        selected_car = Car.query.filter(Car.id == form.car_id.data).first()
        free_capacity_length = selected_car.capacity_length
        free_capacity_weight = selected_car.capacity_weight
        free_capacity_width = selected_car.capacity_width
        free_capacity_height = selected_car.capacity_height

        time_from_start_to_point1 = None
        time_from_point1_to_end = None

        time_from_start_to_point2 = None
        time_from_point2_to_end = None
        time_from_point1_to_point2 = None

        time_from_start_to_point3 = None
        time_from_point1_to_point3 = None
        time_from_point2_to_point3 = None
        time_from_point3_to_end = None


        route_between_start_and_end = calculate_route(localizations[0][1]['Latitude'], localizations[0][1]['Longitude'],
                                                         localizations[1][1]['Latitude'], localizations[1][1]['Longitude'])
        time_from_start_to_end = route_between_start_and_end[0]
        distance_from_start_to_end = route_between_start_and_end[1]
        print(time_from_start_to_end)
        print(distance_from_start_to_end)

        start_localization = localizations[0][0]
        start_point_positions = localizations[0][2]
        end_localization = localizations[1][0]
        end_point_positions = localizations[1][2]
        next_localization1 = localizations[2][0]
        next_point_positions1 = localizations[2][2]
        next_localization2 = localizations[3][0]
        next_point_positions2 = localizations[3][2]

        if localizations[2][1] is not None:
            route_between_point1_and_start = calculate_route(localizations[0][1]['Latitude'],
                                                          localizations[0][1]['Longitude'],
                                                          localizations[2][1]['Latitude'],
                                                          localizations[2][1]['Longitude'])
            route_between_point1_and_end = calculate_route(localizations[1][1]['Latitude'],
                                                          localizations[1][1]['Longitude'],
                                                          localizations[2][1]['Latitude'],
                                                          localizations[2][1]['Longitude'])
            print('TIME', route_between_point1_and_start[0])
            print('DISTANCE', route_between_point1_and_start[1])
            print('TIME', route_between_point1_and_end[0])
            print('DISTANCE', route_between_point1_and_end[1])
        if localizations[3][1] is not None:
            route_between_point2_and_start = calculate_route(localizations[0][1]['Latitude'],
                                                          localizations[0][1]['Longitude'],
                                                          localizations[3][1]['Latitude'],
                                                          localizations[3][1]['Longitude'])
            route_between_point2_and_end = calculate_route(localizations[0][1]['Latitude'],
                                                          localizations[0][1]['Longitude'],
                                                          localizations[3][1]['Latitude'],
                                                          localizations[3][1]['Longitude'])
            route_between_point2_and_point1 = calculate_route(localizations[2][1]['Latitude'],
                                                             localizations[2][1]['Longitude'],
                                                             localizations[3][1]['Latitude'],
                                                             localizations[3][1]['Longitude'])
            print('TIME', route_between_point2_and_start[0])
            print('DISTANCE', route_between_point2_and_start[1])
            print('TIME', route_between_point2_and_point1[0])
            print('DISTANCE', route_between_point2_and_point1[1])
            print('TIME', route_between_point2_and_end[0])
            print('DISTANCE', route_between_point2_and_end[1])
            if route_between_point2_and_start[1] < route_between_point1_and_start[1]:
                next_localization1 = localizations[3][0]
                next_point_positions1 = localizations[3][2]
                next_localization2 = localizations[2][0]
                next_point_positions2 = localizations[2][2]
            else:
                next_localization1 = localizations[2][0]
                next_point_positions1 = localizations[2][2]
                next_localization2 = localizations[3][0]
                next_point_positions2 = localizations[3][2]


        all_dangers = [Danger.position for Danger in Danger.query.all()]
        danger_list = '!'.join(all_dangers)

        journey = Journey(start_localization=start_localization,
                          end_localization=end_localization,
                          author_id=current_user.id, start_time=form.start_time.data,
                          title=form.title.data + ' [' + form.start_place.data + ' - ' + form.end_place.data + ']',
                          start_point_positions=start_point_positions,
                          end_point_positions=end_point_positions,
                          used_capacity_height=0, used_capacity_length=0,
                          used_capacity_weight=0, used_capacity_width=0,
                          free_capacity_length=free_capacity_length,
                          free_capacity_weight=free_capacity_weight,
                          free_capacity_width=free_capacity_width,
                          free_capacity_height=free_capacity_height,
                          localization_counter=temp_counter, car_id=form.car_id.data,
                          next_localization1=next_localization1 or None,
                          next_point_positions1=next_point_positions1 or None,
                          next_localization2=next_localization2 or None,
                          next_point_positions2=next_point_positions2 or None,
                          next_localization3=localizations[4][0] or None,
                          next_point_positions3=localizations[4][2] or None,
                          next_localization4=localizations[5][0] or None,
                          next_point_positions4=localizations[5][2] or None,
                          next_localization5=localizations[6][0] or None,
                          next_point_positions5=localizations[6][2] or None)

        db.session.add(journey)
        db.session.commit()
        flash(Markup('This route has been added to the database - <a href="/route/'
                     + str(journey.id) + '" class="alert-link">Show the route</a>'))
        print(localizations)
        return render_template('map.html', form=form,
                               danger_list=json.dumps(danger_list),
                               all_dangers=all_dangers, localization_counter=temp_counter,
                               time_from_start_to_point1=json.dumps(time_from_start_to_point1) or None,
                               time_from_start_to_point2=json.dumps(time_from_start_to_point2) or None,
                               time_from_start_to_point3=json.dumps(time_from_start_to_point3) or None,
                               time_from_point1_to_end=json.dumps(time_from_point1_to_end) or None,
                               time_from_point2_to_end=json.dumps(time_from_point2_to_end) or None,
                               time_from_point3_to_end=json.dumps(time_from_point3_to_end) or None,
                               time_from_point1_to_point2=json.dumps(time_from_point1_to_point2) or None,
                               start_point=start_localization, next_point=end_localization,
                               start_point_positions=start_point_positions,
                               end_point_positions=end_point_positions,
                               localizations=localizations, entry_localizations=entry_localizations)

    # localizations zawiera wszystkie punkty zamieszczone w bazie danych (również te puste Nulle)
    # entry_localizations zawiera jedynie punkty, które użytkownik wporwadził do paneli Form
    return render_template('map.html', form=form, localizations=json.dumps(localizations),
                           localization_counter=temp_counter, entry_localizations=json.dumps(entry_localizations))


@main.route('/geocode', methods=['GET'])
def handle_geocode():
    geocoderApi = herepy.GeocoderApi(current_app.config['HERE_API_KEY'])
    response = geocoderApi.free_form('200 S Mathilda Sunnyvale CA')
    return response.as_json_string()
