from slim import Application
import config


app = Application(cookies_secret=config.COOKIE_SECRET, enable_log=config.DEBUG)
