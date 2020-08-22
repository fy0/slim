from multidict import istr

SET_COOKIE = istr('Set-Cookie')
CONTENT_TYPE = istr('Content-Type')
X_FORWARDED_FOR = istr('X-Forwarded-For')
X_FORWARDED_HOST = istr('X-Forwarded-Host')

ACCESS_CONTROL_ALLOW_CREDENTIALS = istr('Access-Control-Allow-Credentials')
ACCESS_CONTROL_ALLOW_HEADERS = istr('Access-Control-Allow-Headers')
ACCESS_CONTROL_ALLOW_METHODS = istr('Access-Control-Allow-Methods')
ACCESS_CONTROL_ALLOW_ORIGIN = istr('Access-Control-Allow-Origin')
ACCESS_CONTROL_EXPOSE_HEADERS = istr('Access-Control-Expose-Headers')
ACCESS_CONTROL_MAX_AGE = istr('Access-Control-Max-Age')
ACCESS_CONTROL_REQUEST_HEADERS = istr('Access-Control-Request-Headers')
ACCESS_CONTROL_REQUEST_METHOD = istr('Access-Control-Request-Method')

ERR_TEXT_ROGUE_FIELD = 'Rogue field'
ERR_TEXT_COLUMN_IS_NOT_FOREIGN_KEY = 'This column is not a foreign key'
