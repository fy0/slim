from .utils.state_obj import StateObject


class RETCODE(StateObject):
    SUCCESS = 0  # 成功
    FAILED = -255  # 失败
    TIMEOUT = -254  # 超时
    UNKNOWN = -253  # 未知错误

    NOT_FOUND = -249  # 未找到
    ALREADY_EXISTS = -248  # 已存在

    PERMISSION_DENIED = -239  # 无权访问
    INVALID_ROLE = -238  # 权限申请失败

    CHECK_FAILURE = -229  # 校验失败（文件上传等）
    PARAM_REQUIRED = -228  # 需要参数
    POSTDATA_REQUIRED = -227  # 需要参数

    INVALID_HTTP_PARAMS = -219  # 非法参数
    INVALID_HTTP_POSTDATA = -218  # 非法提交内容

    txt_cn = {
        SUCCESS: '成功',
        FAILED: '失败',
        TIMEOUT: '超时',
        UNKNOWN: '未知错误',

        NOT_FOUND: '未找到',
        ALREADY_EXISTS: '已存在',

        PERMISSION_DENIED: '无权访问',
        INVALID_ROLE: '权限申请失败',

        CHECK_FAILURE: '校验失败',
        PARAM_REQUIRED: '缺少参数',
        POSTDATA_REQUIRED: '缺少提交内容',

        INVALID_HTTP_PARAMS: '非法参数',
        INVALID_HTTP_POSTDATA: '非法提交内容',
    }

    txt_en = {
        SUCCESS: 'success',
        FAILED: 'failed',
        TIMEOUT: 'timeout',
        UNKNOWN: 'unknown',

        NOT_FOUND: 'not found',
        ALREADY_EXISTS: 'already exists',

        PERMISSION_DENIED: 'permission denied',
        INVALID_ROLE: 'acquire role failed',

        CHECK_FAILURE: 'check failure',
        PARAM_REQUIRED: 'parameter(s) required',
        POSTDATA_REQUIRED: 'post data item(s) required',

        INVALID_HTTP_PARAMS: 'invalid parameter(s)',
        INVALID_HTTP_POSTDATA: 'invalid post',
    }
