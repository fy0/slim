from slim import Application, CORSOptions, ALL_PERMISSION, NO_PERMISSION
import config


app = Application(
    log_level=config.DEBUG,
    cookies_secret=config.COOKIE_SECRET,
    permission=ALL_PERMISSION,
    cors_options=CORSOptions('*', allow_credentials=True, expose_headers="*", allow_headers="*")
)
