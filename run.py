import asyncio
import aiohttp
from aiohttp import web


WS_CONNECTIONS = 'ws_connections'


async def refresh_order_state(request):
    params = await request.json()
    if params['order_id'] not in request.app[WS_CONNECTIONS]:
        return web.HTTPBadRequest(text='No such subscriber')

    ws = request.app[WS_CONNECTIONS][ params['order_id'] ]
    ws.send_str('state,' + str(params['state']))
    ws.send_str('close')
    del request.app[WS_CONNECTIONS][ params['order_id'] ]
    return web.json_response(params)


def check_connections(app, loop):
    # while True:
        print('check connections')
        for order_id, conn in app[WS_CONNECTIONS].items():
            print(order_id, conn.close_code, conn.exception())
        # await asyncio.sleep(2)
        loop.call_later(2, check_connections, app, loop)

async def notify(request):
    ws = web.WebSocketResponse(heartbeat=4)
    await ws.prepare(request)
    print(ws)

    try:
        async for msg in ws:
            print(msg)
            if msg.type == aiohttp.WSMsgType.TEXT:
                print(msg.data)
                if msg.data.startswith('order'):
                    order_id = msg.data.split(',')[1]
                    if order_id in request.app[WS_CONNECTIONS]:
                        print('already exist')
                    request.app[WS_CONNECTIONS][order_id] = ws
                    print(request.app[WS_CONNECTIONS])
                else:
                    print(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print('ws connection closed with exception %s' %
                      ws.exception())
            else:
                print(msg)

        print('websocket connection closed')
    except:
        from traceback import print_exc
        print(ws.closed)
        print_exc()

    return ws


if __name__ == '__main__':
    app = web.Application()
    app[WS_CONNECTIONS] = {}
    app.router.add_post('/order/state', refresh_order_state)
    app.router.add_get('/', notify)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.call_soon(check_connections, app, loop)
    # asyncio.ensure_future(check_connections(app[WS_CONNECTIONS], loop))
    web.run_app(app, host='127.0.0.1', port=8080, loop=loop)
