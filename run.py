import logging
import asyncio
import json
import aiohttp
from logging.config import dictConfig
from collections import defaultdict
from functools import partial
from aiohttp import web


LOGGER_NAME = 'notifier'
REGISTER = 'order_register'
ORD_STATE_RELOAD = 'reload'
ORD_STATE_DONE = 'done'
HEARTBEAT = 60
CHECK_CONN_DELAY = 2 * HEARTBEAT
MAX_ORD_CONN_COUNT = 10


logger = logging.getLogger(LOGGER_NAME)


class WsConnectionRegister:

    def __init__(self):
        self.connection_channels = defaultdict(set)
        self.channel_connections = defaultdict(set)

    def add(self, channel, ws_conn):
        self.connection_channels[ws_conn].add(channel)
        self.channel_connections[channel].add(ws_conn)
        logger.info('add the channel {} to the connection {}'.format(channel, ws_conn))

    def remove(self, channel, ws_conn):
        self.connection_channels[ws_conn].remove(channel)
        self.channel_connections[channel].remove(ws_conn)
        logger.info('remove the channel from the connection {}'.format(channel, ws_conn))

        if not self.channel_connections[channel]:
            logger.info('remove channel {} from the register'.format(channel))
            del self.channel_connections[channel]
        if not self.connection_channels[ws_conn]:
            logger.info('remove connection {} from the register'.format(ws_conn))
            del self.connection_channels[ws_conn]

    def get_connections(self):
        return self.connection_channels.keys()

    @property
    def channels_count(self):
        return len(self.channel_connections.keys())

    @property
    def connections_count(self):
        return len(self.connection_channels.keys())

    def __getitem__(self, channel):
        return self.channel_connections[channel]

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

    for order_id, ws in closed:
        register.remove(order_id, ws)

    loop.call_later(CHECK_CONN_DELAY, check_connections, register, loop)


async def notify(register, order_id, state):
    ws_list = register[order_id].copy()  # работаем с копией, чтобы оригинал регистра не изменялся по лету(in place)
    logger.info('send state {} to order {}'.format(state, order_id))

    data = {'state': state, 'order_id': order_id}
    if state == ORD_STATE_RELOAD:
        for ws in ws_list:
            ws.send_json(data)
    elif state == ORD_STATE_DONE:
        for ws in ws_list:
            ws.send_json(data)
            await ws.close()
            register.remove(order_id, ws)


async def registrate_notification(request):
    logger.info('registrate notification')
    response = dict(success=True)
    params = await request.json()
    logger.debug('order {}, state {}'.format(params['order_id'], params['state']))

    e_text = ''
    if params['order_id'] not in request.app[REGISTER]:
        e_text = 'no such ws connection'
    elif not any(params['state'] == state for state in (ORD_STATE_DONE, ORD_STATE_RELOAD)):
        e_text = 'invalid state {}'.format(params['state'])

    if e_text:
        logger.error(e_text)
        response['success'] = False
        response['error'] = e_text
        return web.json_response(response)

    pnotify = partial(notify, request.app[REGISTER], params['order_id'], params['state'])
    asyncio.ensure_future(pnotify())
    logger.info('notification is registered')

    return web.json_response(response)


async def registrate_connection(request):
    ws = web.WebSocketResponse(heartbeat=HEARTBEAT)
    await ws.prepare(request)
    logger.info('connection is opened')

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug('message data: {}'.format(msg.data))
                data = json.loads(msg.data)
                order_id = data.get('order_id', '')

                if order_id and len(request.app[REGISTER][order_id]) > MAX_ORD_CONN_COUNT:
                    logger.error('max connections count of the order {}'.format(order_id))
                    ws.close()
                elif order_id:
                    request.app[REGISTER][order_id].add(ws)
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
    app[REGISTER] = WsConnectionRegister()
    app.router.add_post('/order', registrate_notification)
    app.router.add_get('/', registrate_connection)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.call_later(CHECK_CONN_DELAY, check_connections, app[REGISTER], loop)
    web.run_app(app, host='0.0.0.0', port=8080, loop=loop)
