from .utils.state_obj import StateObject


class RETCODE(StateObject):
    SUCCESS = 0  # 成功
    TIMEOUT = -244  # 超时
    CHECK_FAILURE = -245  # 校验失败（文件上传等）
    PARAM_REQUIRED = -246  # 需要参数
    FAILED = -247  # 失败
    TOO_LONG = -248  # 过长（用户名或其他参数）
    TOO_SHORT = -249  # 过短（用户名或其他参数）
    INVALID_POSTDATA = -243  # 非法提交内容
    INVALID_PARAMS = -250  # 非法参数
    ALREADY_EXISTS = -251  # 已存在
    NOT_FOUND = -252  # 未找到
    UNKNOWN = -253  # 未知错误
    NOT_USER = -254  # 未登录
    INVALID_ROLE = -246  # 权限申请失败
    PERMISSION_DENIED = -255  # 无权访问

    txt_cn = {
        SUCCESS: '成功',
        TIMEOUT: '超时',
        CHECK_FAILURE: '校验失败',
        PARAM_REQUIRED: '需要参数',
        FAILED: '失败',
        TOO_LONG: '过长（用户名或其他参数）',
        TOO_SHORT: '过短（用户名或其他参数）',
        INVALID_POSTDATA: '非法提交内容',
        INVALID_PARAMS: '非法参数',
        ALREADY_EXISTS: '已存在',
        NOT_FOUND: '未找到',
        UNKNOWN: '未知错误',
        NOT_USER: '未登录',
        INVALID_ROLE: '权限申请失败',
        PERMISSION_DENIED: '无权访问'
    }

    txt_en = {
        SUCCESS: 'success',
        TIMEOUT: 'timeout',
        CHECK_FAILURE: 'check failure',
        PARAM_REQUIRED: 'parameter(s) required',
        FAILED: 'failed',
        TOO_LONG: '(username or sth.) too long',
        TOO_SHORT: '(username or sth.) too short',
        INVALID_POSTDATA: 'invalid post',
        INVALID_PARAMS: 'invalid parameter(s)',
        ALREADY_EXISTS: 'already exists',
        NOT_FOUND: 'not found',
        UNKNOWN: 'unknown',
        NOT_USER: 'not login',
        INVALID_ROLE: 'acquire role failed',
        PERMISSION_DENIED: 'permission denied'
    }
