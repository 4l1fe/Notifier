import asyncio
import aiohttp


async def send(i):
    session = aiohttp.ClientSession()
    ws = await session.ws_connect('ws://127.0.0.1:8080/')
    print('connected %s' % i)
    await ws.send_json([1,2,3,4,5,6])
    # conns.append(ws)
    print('wait for data %s' % i)
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data:
                print('got data %s' % i)
            else:
                print('error %s' % i)
        elif msg.type == aiohttp.WSMsgType.CLOSED:
            break
        elif msg.type == aiohttp.WSMsgType.ERROR:
            break

    session.close()


async def run(n):
    tasks = []
    for i in range(n):
        task = asyncio.ensure_future(send(i))
        tasks.append(task)
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(2))