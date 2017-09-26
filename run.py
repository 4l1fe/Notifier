import logging
import asyncio
import json
import aiohttp
from logging.config import dictConfig
from collections import defaultdict
from functools import partial
from aiohttp import web


LOGGER_NAME = 'notifier'
REGISTER = 'register'
ORD_STATE_DONE = 'done'
ORD_STATE_RELOAD = 'reload'
HEARTBEAT = 3
CHECK_CONN_DELAY = 2 * HEARTBEAT


logger = logging.getLogger(LOGGER_NAME)


class ChannelsRegister:

    def __init__(self):
        self._connection_channels_type = set #todo изменить на list? где-то упростит/усложнит код
        self._channel_connections_type = set
        self.connection_channels = defaultdict(self._connection_channels_type)
        self.channel_connections = defaultdict(self._channel_connections_type)

    def add_channels(self, channels, ws_conn):
        if not isinstance(channels, (list, tuple, set)):
            channels = [channels, ]
        for channel in channels:
            self.channel_connections[channel].add(ws_conn)
        self.connection_channels[ws_conn].update(channels)
        logger.info('add the channels {} to the connection {}'.format(channels, ws_conn))

    def remove_channels(self, channels, ws_conn):
        if not isinstance(channels, (list, tuple, set)):
            channels = [channels, ]
        logger.info('remove the channels from the connection {}'.format(channels, ws_conn))
        for channel in channels:
            self.channel_connections[channel].remove(ws_conn)
            if not self.channel_connections[channel]:
                logger.info('remove channel {} from the register'.format(channel))
                del self.channel_connections[channel]

        self.connection_channels[ws_conn].difference_update(channels)
        if not self.connection_channels[ws_conn]:
            logger.info('remove connection {} from the register'.format(ws_conn))
            del self.connection_channels[ws_conn]

    def get_connections(self, channel=None):
        if channel:
            return self.channel_connections[channel] if channel in self.channel_connections\
                                                     else self._channel_connections_type()
        return self.connection_channels.keys()

    def get_channels(self, ws_conn=None):
        if ws_conn:
            return self.connection_channels[ws_conn] if ws_conn in self.connection_channels\
                                                     else self._connection_channels_type()
        return self.channel_connections.keys()

    @property
    def channels_count(self):
        return len(self.channel_connections.keys())

    @property
    def connections_count(self):
        return len(self.connection_channels.keys())

    def __str__(self):
        return '<{} channels_count={}, connections_count={}>'.format(self.__class__.__name__, self.channels_count,
                                                                   self.connections_count)


def check_connections(register, loop):
    logger.info('check the closed connections')
    logger.debug(register)

    closed = []
    for ws in register.get_connections():
        if ws.closed or ws.close_code == 1006:
            logger.debug('{}'.format((ws.closed, ws.close_code, ws.exception())))
            closed.append(ws)

    for ws in closed:
        channels = register.get_channels(ws)
        register.remove_channels(channels, ws)

    loop.call_later(CHECK_CONN_DELAY, check_connections, register, loop)


async def notify(register, channel, data):
    ws_list = register.get_connections(channel).copy()  # работаем с копией, чтобы оригинал регистра не изменялся по лету(in place)
    logger.info('send data {} to channel {}'.format(data, channel))

    state = data.get('state', None)
    if state != ORD_STATE_DONE:
        for ws in ws_list:
            ws.send_json(data)
    else:
        for ws in ws_list:
            ws.send_json(data)
            register.remove_channels(channel, ws)
            if not register.get_channels(ws):
                await ws.close()


async def notify2(register, order_id, state):  #todo выпилить
    ws_list = register.get_connections(order_id).copy()  # работаем с копией, чтобы оригинал регистра не изменялся по лету(in place)
    logger.info('send state {} to order {}'.format(state, order_id))

    data = {'state': state, 'order_id': order_id}
    if state == ORD_STATE_RELOAD:
        for ws in ws_list:
            ws.send_json(data)
    elif state == ORD_STATE_DONE:
        for ws in ws_list:
            ws.send_json(data)
            register.remove_channels(order_id, ws)
            if not register.get_channels(ws):
                await ws.close()


async def publish_notification(request):
    logger.info('publish notification')
    response = dict(success=True)
    params = await request.json()
    logger.debug('channel {}, data {}'.format(params['channel'], params['data']))

    if not request.app[REGISTER].get_connections(params['channel']):
        e_text = 'no such channel'
        logger.error(e_text)
        response['success'] = False
        response['error'] = e_text
        return web.json_response(response)

    pnotify = partial(notify, request.app[REGISTER], params['channel'], params['data'])
    asyncio.ensure_future(pnotify())
    logger.info('notification is published')

    return web.json_response(response)


async def registrate_notification(request):  #todo выпилить
    logger.info('registrate notification')
    response = dict(success=True)
    params = await request.json()
    logger.debug('order {}, state {}'.format(params['order_id'], params['state']))

    e_text = ''
    if not request.app[REGISTER].get_connections(params['order_id']):
        e_text = 'no such ws connection'
    elif not any(params['state'] == state for state in (ORD_STATE_DONE, ORD_STATE_RELOAD)):
        e_text = 'invalid state {}'.format(params['state'])

    if e_text:
        logger.error(e_text)
        response['success'] = False
        response['error'] = e_text
        return web.json_response(response)

    pnotify = partial(notify2, request.app[REGISTER], params['order_id'], params['state'])
    asyncio.ensure_future(pnotify())
    logger.info('notification is registered')


async def registrate_connection(request):
    ws = web.WebSocketResponse(heartbeat=HEARTBEAT)
    await ws.prepare(request)
    logger.info('connection is opened')

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug('message data: {}'.format(msg.data))
                data = json.loads(msg.data)
                if not isinstance(data, list): # todo убрать
                    channel = data.get('order_id', '')
                    request.app[REGISTER].add_channels(channel, ws)
                elif data: # множественная вставка
                    request.app[REGISTER].add_channels(data, ws)
                else:
                    logger.error('undefined action')
                    ws.close()

            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error('connection error {}'.format(ws.exception()))
            else:
                logger.warning('another msg.type {}'.format(msg))

        logger.info('connection is closed')
    except:
        logger.exception('')

    return ws


if __name__ == '__main__':
    dictConfig({'version': 1,
              'formatters': {
                  'common': {
                      'class': 'logging.Formatter',
                      'format': '[%(asctime)s %(name)s %(levelname)s] %(message)s'
                  },
              },
              'handlers': {
                  'common': {
                      'class': 'logging.StreamHandler',
                      'level': 'DEBUG',
                      'formatter': 'common',
                      'stream': 'ext://sys.stdout',
                  },
              },
              'loggers': {
                  LOGGER_NAME: {
                      'handlers': ['common'],
                      'level': 'DEBUG'
                  }
              }
          }
    )

    app = web.Application()
    app[REGISTER] = ChannelsRegister()
    app.router.add_post('/publish', publish_notification)
    app.router.add_post('/order', registrate_notification)
    app.router.add_get('/', registrate_connection)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.call_later(CHECK_CONN_DELAY, check_connections, app[REGISTER], loop)
    web.run_app(app, host='0.0.0.0', port=8080, loop=loop)
