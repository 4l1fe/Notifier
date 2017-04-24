import logging
import asyncio
import json
import aiohttp
from logging.config import dictConfig
from collections import defaultdict
from functools import partial
from itertools import chain
from aiohttp import web


LOGGER_NAME = 'notify'
WS_REGISTER = 'ws_register'
ORD_STATE_READY = 'ready'
ORD_STATE_DONE = 'done'
HEARTBEAT = 4
CHECK_CONN_DELAY = 2 * HEARTBEAT
MAX_ORD_CONN_COUNT = 10

logger = logging.getLogger(LOGGER_NAME)


def _clear_register(register, order_id, conn):
    """Соединение conn ДОЛЖНО быть закрытым"""

    logger.info('remove connection of the order {}'.format(order_id))
    register[order_id].remove(conn)
    if not register[order_id]:
        logger.info('remove order {} from the register'.format(order_id))
        del register[order_id]


def check_connections(register, loop):
    logger.info('check closed connections')
    #todo сделать методом регистра изменение кол-ва соединений при регистрации/очистке
    ords_count = len(list(register.keys()))
    conns_count = len(list(chain.from_iterable(register.values())))
    logger.debug('orders count {}, connections count is {}'.format(ords_count, conns_count))

    closed = []
    for order_id, connections in register.items():
        for conn in connections:
            if conn.closed or conn.close_code == 1006:
                logger.debug('{}'.format((order_id, conn.closed, conn.close_code, conn.exception())))
                closed.append( (order_id, conn) )

    for order_id, conn in closed:
        _clear_register(register, order_id, conn)

    loop.call_later(CHECK_CONN_DELAY, check_connections, register, loop)


async def register_notification(request):
    logger.info('register notification')
    response = dict(success=True)
    params = await request.json()
    logger.debug('order {}, state {}'.format(params['order_id'], params['state']))

    e_text = ''
    if params['order_id'] not in request.app[WS_REGISTER]:
        e_text = 'no such ws connection'
    elif not any(params['state'] == state for state in (ORD_STATE_DONE, ORD_STATE_READY)):
        e_text = 'invalid state {}'.format(params['state'])

    if e_text:
        logger.error(e_text)
        response['success'] = False
        response['error'] = e_text
        return web.json_response(response)

    pnotify = partial(notify, request.app[WS_REGISTER], params['order_id'], params['state'])
    asyncio.ensure_future(pnotify())
    logger.info('notification registered')

    return web.json_response(response)


async def notify(register, order_id, state):
    ws_list = register[order_id]
    logger.info('send state {} to order {}'.format(state, order_id))

    data = {'state': state}
    if state == ORD_STATE_READY:
        for ws in ws_list:
            ws.send_json(data)
    elif state == ORD_STATE_DONE:
        for ws in ws_list:
            ws.send_json(data)
            await ws.close()
            _clear_register(register, order_id, ws)


async def register_connection(request):
    ws = web.WebSocketResponse(heartbeat=HEARTBEAT)
    await ws.prepare(request)
    logger.info('connection is opened')

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug('message data: {}'.format(msg.data))
                data = json.loads(msg.data)
                order_id = data.get('order', '')
                if order_id and len(request.app[WS_REGISTER][order_id]) > MAX_ORD_CONN_COUNT:
                    logger.error('max connections count of the order {}'.format(order_id))
                    ws.close()
                elif order_id:
                    request.app[WS_REGISTER][order_id].append(ws)
                    logger.info('add connection to the order {}'.format(order_id))
                else:
                    logger.error('undefined action')

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
    app[WS_REGISTER] = defaultdict(list)
    app.router.add_post('/order', register_notification)
    app.router.add_get('/', register_connection)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.call_later(CHECK_CONN_DELAY, check_connections, app[WS_REGISTER], loop)
    web.run_app(app, host='0.0.0.0', port=8080, loop=loop)
