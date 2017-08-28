class RETCODE:
    SUCCESS = 0  # 成功
    TIMEOUT = -244  # 超时
    CHECK_FAILURE = -245  # 校验失败（文件上传等）
    PARAM_REQUIRED = -246  # 需要参数
    FAILED = -247  # 失败
    TOO_LONG = -248  # 过长（用户名或其他参数）
    TOO_SHORT = -249  # 过短（用户名或其他参数）
    INVALID_POSTDATA = -243  # 非法提交内容
    INVALID_PARAMS = -250  # 非法参数
    ALREADY_EXISTS = -251  # 已经存在
    NOT_FOUND = -252  # 未找到
    UNKNOWN = -253  # 未知错误
    NOT_USER = -254  # 未登录
    INVALID_ROLE = -246  # 权限申请失败
    PERMISSION_DENIED = -255  # 无权访问
