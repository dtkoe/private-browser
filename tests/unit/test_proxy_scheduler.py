import threading

from backend.services.proxy_scheduler import BackgroundProxyScheduler


def test_scheduler_runs_callback_immediately_then_periodically():
    counter = {"v": 0}
    sem = threading.Event()

    def cb():
        counter["v"] += 1
        if counter["v"] >= 2:
            sem.set()

    sched = BackgroundProxyScheduler(check_callback=cb, interval_seconds=0.2)
    sched.start()
    assert sem.wait(timeout=3.0), f"only got {counter['v']} ticks"
    sched.stop()
    assert counter["v"] >= 2
