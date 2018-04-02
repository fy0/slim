from slim import Application
import config


app = Application(
    cookies_secret=config.COOKIE_SECRET,
    log_level=config.DEBUG
)
