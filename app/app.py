# set async_mode to 'threading', 'eventlet', 'gevent' or 'gevent_uwsgi' to
# force a mode else, the best mode is selected automatically from what's
# installed
async_mode = 'eventlet'

import time
from flask import Flask, render_template, request
# from flask_cors import CORS, cross_origin
import socketio
import json
import eventlet

sio = socketio.Server(logger=True, async_mode=async_mode)
app = Flask(__name__)
# app.wsgi_app = socketio.Middleware(sio, app.wsgi_app)
app.config['SECRET_KEY'] = 'secretkey'
thread = None


@app.route('/order/state', methods=['GET', 'POST'])
def order_state():
    j = request.get_json()
    order_id = j.get('order_id')
    state = j.get('state')
    r = dict(
        target=order_id,
        state=state)
    sio.emit('my response', {'data': json.dumps(r)}, room=order_id,
             namespace='/test')
    return str(order_id)


@sio.on('my event', namespace='/test')
def test_message(sid, message):
    sio.emit('my response', {'data': message['data']}, room=sid,
             namespace='/test')


@sio.on('my broadcast event', namespace='/test')
def test_broadcast_message(sid, message):
    sio.emit('my response', {'data': message['data']}, namespace='/test')


@sio.on('join', namespace='/test')
def join(sid, message):
    sio.enter_room(sid, message['room'], namespace='/test')
    # sio.emit('my response', {'data': 'Entered room: ' + message['room']},
             # room=sid, namespace='/test')


@sio.on('leave', namespace='/test')
def leave(sid, message):
    sio.leave_room(sid, message['room'], namespace='/test')
    sio.emit('my response', {'data': 'Left room: ' + message['room']},
             room=sid, namespace='/test')


@sio.on('close room', namespace='/test')
def close(sid, message):
    sio.emit('my response',
             {'data': 'Room ' + message['room'] + ' is closing.'},
             room=message['room'], namespace='/test')
    sio.close_room(message['room'], namespace='/test')


@sio.on('my room event', namespace='/test')
def send_room_message(sid, message):
    sio.emit('my response', {'data': message['data']}, room=message['room'],
             namespace='/test')


@sio.on('disconnect request', namespace='/test')
def disconnect_request(sid):
    sio.disconnect(sid, namespace='/test')


@sio.on('connect', namespace='/test')
def test_connect(sid, environ):
    sio.emit('my response', {'data': 'Connected', 'count': 0}, room=sid,
             namespace='/test')


@sio.on('disconnect', namespace='/test')
def test_disconnect(sid):
    print('Client disconnected')


if __name__ == '__main__':
    # deploy with eventlet
    import eventlet
    import eventlet.wsgi
    eventlet.wsgi.server(eventlet.listen(('', 8000)), app)
