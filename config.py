import logging


class Application:
    num_of_trends = 10
    time_between_UI_updates_seconds = 1


class TwitterAPICredential:
    ckey = ""
    csecret = ""
    atoken = ""
    asecret = ""


class Logger:
    log_msg_format = "%(asctime)s: %(message)s"
    log_level = logging.INFO
    Log_date_format = "%H:%M:%S"
