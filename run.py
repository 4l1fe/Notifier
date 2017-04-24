import logging
import asyncio
import aiohttp
from aiohttp import web


logger = logging.getLogger('notify')
WS_CONNECTIONS = 'ws_connections'
ORD_STATE_DONE = 3
CHECK_CONN_DELAY = 10
HEARTBEAT = 60


async def change_order_state(request):
    logger.info('change order state')
    response = dict(success=True)
    params = await request.json()
    logger.debug('order {}, state {}'.format(params['order_id'], params['state']))

    if params['order_id'] not in request.app[WS_CONNECTIONS]:
        e_text = 'No such ws connection'
        logger.error(e_text)
        response['success'] = False
        response['error'] = e_text
        return web.json_response(response, status=400)

    ws = request.app[WS_CONNECTIONS][ params['order_id'] ]
    logger.info('send state')
    ws.send_str('state,' + str(params['state']))

    if params['state'] == ORD_STATE_DONE:
        logger.info('close connection')
        ws.send_str('close')
        await ws.close()

    return web.json_response(response)


def check_connections(app, loop):
    logger.info('check closed connections')
    logger.debug('connections count {}'.format(len(app[WS_CONNECTIONS])))

    removed = []
    for order_id, conn in app[WS_CONNECTIONS].items():
        logger.debug('{}'.format( (order_id, conn.closed, conn.close_code, conn.exception()) ))
        if conn.closed or conn.close_code == 1006:
            removed.append(order_id)

    if removed:
        logger.info('remove connections for orders {}'.format(removed))
        for order_id in removed:
            del app[WS_CONNECTIONS][ order_id ]
        removed.clear()

    loop.call_later(CHECK_CONN_DELAY, check_connections, app, loop)


async def notify(request):
    ws = web.WebSocketResponse(heartbeat=HEARTBEAT)
    await ws.prepare(request)
    logger.info('connection opened')

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug('message data: {}'.format(msg.data))
                if msg.data.startswith('order'):
                    order_id = msg.data.split(',')[1]
                    if order_id in request.app[WS_CONNECTIONS]:
                        logger.warning('already exist')
                    request.app[WS_CONNECTIONS][order_id] = ws
                    logger.info('add connection to order {}'.format(order_id))
                else:
                    logger.error('undefined action')

            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error('connection error {}'.format(ws.exception()))
            else:
                logger.warning('another msg.type {}'.format(msg))

        logger.info('connection closed')
    except:
        logger.exception('')

    return ws


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    app = web.Application()
    app[WS_CONNECTIONS] = {}
    app.router.add_post('/order/state', change_order_state)
    app.router.add_get('/', notify)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.call_soon(check_connections, app, loop)
    web.run_app(app, host='0.0.0.0', port=8080, loop=loop)
