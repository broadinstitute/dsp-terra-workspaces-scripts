import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)


def poll_predicate(
    name: str, max_wait_time_seconds: int, poll_interval_seconds: int, poll_fn
) -> (any, any):
    """
    Polls on the given polling fn for max_wait_time_seconds, every poll_interval_seconds, until the job is reported
    completed or we time out.
    """
    time_waited = 0

    while time_waited < max_wait_time_seconds:
        logging.info(f"Polling on {name}...")
        (status, result) = poll_fn()

        if status:
            logging.info(f"{name} is successful")
            return status, result

        logging.info(f"{name} not complete, scheduling retry...")
        time.sleep(poll_interval_seconds)
        time_waited += poll_interval_seconds

    raise Exception(
        f"Exceeded max wait time of {max_wait_time_seconds} polling for status of {name}"
    )
