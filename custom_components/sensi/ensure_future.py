import asyncio


async def tweet(article):
    # Simulate an I/O operation (e.g., calling a social media API)
    while True:
        print(f"Tweeting: {article}")
        await asyncio.sleep(1)
        # print("Tweeted!")


def task_done(task) -> None:
    print(f"done {task}")


async def main():
    articles = ["Article 1", "Article 2"]

    # Use ensure_future to run the tweet coroutines in the background
    # without awaiting them in main()
    background_tasks = set()
    for article in articles:
        task = asyncio.ensure_future(tweet(article))  # Schedules the task
        background_tasks.add(task)
        task.add_done_callback(task_done)

    # asyncio.ensure_future(tweet(article))  # Schedules the task

    print("Main function continues execution while tweets are pending...")
    # Keep loop running long enough for tasks to complete
    await asyncio.sleep(3)

    print("Cancelling tweets.")
    for task in background_tasks:
        task.cancel()

    # Keep loop running long enough for tasks to complete
    await asyncio.sleep(2)

    print("Main function done.")


if __name__ == "__main__":
    # Use asyncio.run() for a clean entry point in Python 3.7+
    asyncio.run(main())
