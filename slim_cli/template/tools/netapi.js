import axios from 'axios'
import config from './config.js'

axios.defaults.retry = 2
axios.defaults.retryDelay = 300

let remote = config.remote
const backend = axios.create({
    baseURL: remote.API_SERVER,
    timeout: 5000,
    withCredentials: true,
    headers: {
        'Accept': 'application/json'
    }
})

backend.interceptors.response.use(function (response) {
    // Do something with response data
    return response.data
}, function (error) {
    // Do something with response error
    return Promise.reject(error)
})

function paramSerialize (obj) {
    let str = []
    for (let i of Object.keys(obj)) {
        str.push(encodeURIComponent(i) + '=' + encodeURIComponent(obj[i]))
    }
    return str.join('&')
}

function buildFormData (obj) {
    if (!obj) return
    let formData = new FormData()
    for (let [k, v] of Object.entries(obj)) {
        formData.append(k, v)
    }
    return formData
}

function filterValues (filter, data) {
    let keys = null
    if (_.isArray(filter)) keys = new Set(filter)
    else if (_.isSet(filter)) keys = filter
    else if (_.isFunction(filter)) return filter(data)

    let ret = {}
    for (let i of Object.keys(data)) {
        if (keys.has(i)) {
            ret[i] = data[i]
        }
    }
    return ret
}

export function createAPIRequester (ctx) {
    function getAccessToken () {
        if (!ctx) {
            return localStorage.getItem('t')
        }
        return ctx.app.$storage.getUniversal('t')
    }

    function saveAccessToken (token) {
        if (!ctx) {
            localStorage.setItem('t', token)
            return
        }
        return ctx.app.$storage.setUniversal('t', token)
    }

    async function doRequest (url, method, params, data = null, role = null) {
        let headers = {}
        let token = getAccessToken()

        if (token) {
            // 设置 access token
            headers['AccessToken'] = token
        }

        if (role) {
            headers['Role'] = role
        }

        if (params) url += `?${paramSerialize(params)}`
        return backend.request({
            url,
            method,
            headers,
            data: buildFormData(data)
        })
        // if (method === 'POST') reqParams.body = JSON.stringify(data)
    }

    async function doGet (url, params, role = null) { return doRequest(url, 'GET', params, null, role) }
    async function doPost (url, params, data, role = null) { return doRequest(url, 'POST', params, data, role) }

    class SlimViewRequest {
        constructor (path) {
            this.path = path
            this.urlPrefix = `/api/${path}`
        }

        async get (params, role = null) {
            if (params && params.loadfk) {
                params.loadfk = JSON.stringify(params.loadfk)
            }
            return doGet(`${this.urlPrefix}/get`, params, role)
        }

        async list (params, page = 1, size = null, role = null) {
            if (params && params.loadfk) {
                params.loadfk = JSON.stringify(params.loadfk)
            }
            let url = `${this.urlPrefix}/list/${page}`
            if (size) url += `/${size}`
            return doGet(url, params, role)
        }

        async set (params, data, role = null, filter = null) {
            if (filter) data = filterValues(filter, data)
            return doPost(`${this.urlPrefix}/update`, params, data, role)
        }

        async update (params, data, role = null, filter = null) {
            if (filter) data = filterValues(filter, data)
            return doPost(`${this.urlPrefix}/update`, params, data, role)
        }

        async new (data, role = null, filter = null) {
            if (filter) data = filterValues(filter, data)
            return doPost(`${this.urlPrefix}/new`, null, data, role)
        }

        async delete (params, role = null) {
            return doPost(`${this.urlPrefix}/delete`, params, null, role)
        }
    }

    class UserViewRequest extends SlimViewRequest {
        async signin (data) {
            let ret = await doPost(`${this.urlPrefix}/signin`, null, data)
            if (ret.code === retcode.SUCCESS) {
                saveAccessToken(ret.data.access_token)
            }
            return ret
        }

        async signup (data) {
            return doPost(`${this.urlPrefix}/signup`, null, data)
        }

        /* eslint-disable camelcase */
        async changePassword ({ old_password, password }) {
            return doPost(`${this.urlPrefix}/change_password`, null, { old_password, password })
        }

        async signout () {
            return doPost(`${this.urlPrefix}/signout`)
        }
    }

    let retcode = {
        SUCCESS: 0,
        FAILED: -255
    }

    let retinfo = {
        [retcode.SUCCESS]: '操作已成功完成'
    }

    return {
        retcode,
        retinfo,
        saveAccessToken,
        accessToken: null, // 需在初始化时进行设置

        /** 获取综合信息 */
        misc: async function () {
            return doGet(`/api/misc/info`)
        },

        /** 周期请求 */
        tick: async function (auid) {
            return doGet(`/api/misc/tick`, { auid })
        },

        user: new UserViewRequest('user'),
        example: new SlimViewRequest('example')
    }
}
