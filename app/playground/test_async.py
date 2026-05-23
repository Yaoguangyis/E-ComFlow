import asyncio


async def task1():

    await asyncio.sleep(2)

    return "task1 done"


async def task2():

    await asyncio.sleep(3)

    return "task2 done"


async def main():

    results = await asyncio.gather(
        task1(),
        task2()
    )

    print(results)


asyncio.run(main())