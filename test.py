import asyncio
import aiohttp


limit = 15000
async def send():
    async with aiohttp.ClientSession(connector=aiohttp.connector.TCPConnector(limit=limit)) as session:

        conns = []
        print('send')
        for i in range(limit):
            try:
                ws = await session.ws_connect('ws://127.0.0.1:8080/')
                conns.append(ws)
                ws.send_json({'order_id': str(i)})
            except:
                import traceback
                traceback.print_exc()

        print('sleep')
        await asyncio.sleep(10)

        print('close')
        for ws in conns:
            ws.close()

        print('clear')
        conns.clear()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send())