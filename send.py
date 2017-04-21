import asyncio
import aiohttp


async def send():
    async with aiohttp.ClientSession() as session:

        async with session.ws_connect('ws://127.0.0.1:8080/') as ws:
            print(ws)
            ws.send_str('order,1')

            async for msg in ws:
                print(msg)
                if not msg.type == aiohttp.WSMsgType.TEXT:
                    break

                elif msg.type == aiohttp.WSMsgType.TEXT:
                    print(msg.data)
                    if msg.data.startswith('state'):
                        state = msg.data.split(',')[1]
                        print('refresh state')
                    elif msg.data == 'close':
                        await ws.close()
                        break

loop = asyncio.get_event_loop()
loop.run_until_complete(send())