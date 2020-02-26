from slim import Application, CORSOptions, ALL_PERMISSION, EMPTY_PERMISSION, ApplicationDocInfo
import config


app = Application(
    log_level=config.DEBUG_LEVEL,
    cookies_secret=config.COOKIE_SECRET,
    permission=EMPTY_PERMISSION,
    doc_enable=config.DOC_ENABLE,
    doc_info=ApplicationDocInfo(title=config.PROJECT_NAME, description=config.DESC, version=config.VERSION),
    cors_options=CORSOptions('*', allow_credentials=True, expose_headers="*", allow_headers="*")
)
