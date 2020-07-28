from .utils.state_obj import StateObject


class RETCODE(StateObject):
    SUCCESS = 0  # 成功
    FAILED = -255  # 失败
    TIMEOUT = -254  # 超时
    UNKNOWN = -253  # 未知错误
    TOO_FREQUENT = -252  # 请求过于频繁
    DEPRECATED = -251  # 已废弃

    NOT_FOUND = -249  # 未找到
    ALREADY_EXISTS = -248  # 已存在

    PERMISSION_DENIED = -239  # 无权访问
    INVALID_ROLE = -238  # 无法获得此权限角色
    INVALID_TOKEN = -237  # 无效token

    CHECK_FAILURE = -229  # 校验失败（文件上传等）
    PARAM_REQUIRED = -228  # 需要参数
    POSTDATA_REQUIRED = -227  # 需要参数

    INVALID_PARAMS = -219  # 非法参数
    INVALID_POSTDATA = -218  # 非法提交内容
    INVALID_HEADERS = -217  # 非法请求头

    WS_DONE = 1  # Websocket 请求完成

    txt_cn = {
        SUCCESS: '成功',
        FAILED: '失败',
        TIMEOUT: '超时',
        UNKNOWN: '未知错误',
        TOO_FREQUENT: '请求过于频繁',
        DEPRECATED: '此接口已被弃用',

        NOT_FOUND: '未找到',
        ALREADY_EXISTS: '已存在',

        PERMISSION_DENIED: '无权访问',
        INVALID_ROLE: '无法获得此权限角色',
        INVALID_TOKEN: '无效的 token',

        CHECK_FAILURE: '校验失败',
        PARAM_REQUIRED: '缺少参数',
        POSTDATA_REQUIRED: '缺少提交内容',

        INVALID_PARAMS: '非法参数',
        INVALID_POSTDATA: '非法提交内容',
        INVALID_HEADERS: '非法请求头',

        WS_DONE: 'Websocket 请求完成'
    }

    txt_en = {
        SUCCESS: 'success',
        FAILED: 'failed',
        TIMEOUT: 'timeout',
        UNKNOWN: 'unknown',
        TOO_FREQUENT: 'request too frequent',
        DEPRECATED: 'interface deprecated',

        NOT_FOUND: 'not found',
        ALREADY_EXISTS: 'already exists',

        PERMISSION_DENIED: 'permission denied',
        INVALID_ROLE: 'acquire role failed',
        INVALID_TOKEN: 'invalid access token',

        CHECK_FAILURE: 'check failure',
        PARAM_REQUIRED: 'parameter(s) required',
        POSTDATA_REQUIRED: 'post data item(s) required',

        INVALID_PARAMS: 'invalid parameters',
        INVALID_POSTDATA: 'invalid post',
        INVALID_HEADERS: 'invalid headers',

        WS_DONE: 'websocket request done'
    }
