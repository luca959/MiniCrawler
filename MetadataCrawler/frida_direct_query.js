'use strict';

setTimeout(function () {
const options = globalThis.__MC_OPTIONS || Script.parameters || {};
const query = String(options.query || 'weather');
const offset = Number(options.offset || 0);
const pageSize = Number(options.page_size || 20);
const waitMs = Number(options.wait_ms || 6500);
const cookies = String(options.cookies || '');
const searchId = String(options.search_id || '');
const currentPage = Number(options.current_page || (Math.floor(offset / pageSize) + 1));
let tagInfo = options.tag_info || {};

if (typeof tagInfo === 'string') {
    try {
        tagInfo = JSON.parse(tagInfo);
    } catch (_) {
        tagInfo = {};
    }
}

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.DirectQueryValueCallback' + Date.now(),
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) {
                send({kind: 'direct-query-result', query: query, offset: offset, value: String(value)});
            }
        }
    });
    const instances = [];
    Java.choose('com.tencent.mm.ui.widget.MMWebView', {
        onMatch(instance) {
            instances.push(Java.retain(instance));
        },
        onComplete() {
            Java.scheduleOnMainThread(function () {
                instances.forEach(function (instance) {
                    const webViewUrl = String(instance.getUrl());
                    if (!webViewUrl.includes('websearch')) return;
                    const expression = `(function () {
                        var requestedQuery = ${JSON.stringify(query)};
                        var requestedOffset = ${JSON.stringify(offset)};
                        var requestedTagInfo = ${JSON.stringify(tagInfo)};
                        var requestedCookies = ${JSON.stringify(cookies)};
                        var requestedSearchId = ${JSON.stringify(searchId)};
                        var requestedCurrentPage = ${JSON.stringify(currentPage)};
                        var pageSize = ${JSON.stringify(pageSize)};
                        var old = window.onSearchDataReady;
                        window.__MC_DIRECT_RESULT = null;
                        window.onSearchDataReady = function (data) {
                            if (data && data.requestId === requestId) {
                                window.__MC_DIRECT_RESULT = data;
                            }
                            return typeof old === 'function' ? old.apply(this, arguments) : undefined;
                        };
                        var params = new URLSearchParams(location.search);
                        var requestId = typeof crypto.randomUUID === 'function'
                            ? crypto.randomUUID()
                            : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
                                var r = Math.random() * 16 | 0;
                                return (c === 'x' ? r : (r & 3 | 8)).toString(16);
                            });
                        var base = window.Global && typeof window.Global.getBase === 'function'
                            ? window.Global.getBase()
                            : {};
                        var existingExt = [];
                        try {
                            var rootVm = document.querySelector('#app').__vue__;
                            existingExt = (rootVm.$store.getters.getExtReqParams || []).filter(function (item) {
                                return ![
                                    'currentPage', 'requestId', 'cookies', 'firstSearchRequest',
                                    'notFirstSearchAction', 'firstSearchQuery', 'diffRequestId',
                                    'realH5Version', 'netType'
                                ].includes(item.key);
                            });
                        } catch (_) {}
                        var requestExt = existingExt.concat([
                            {key: 'netType', textValue: params.get('netType') || 'wifi'},
                            {key: 'currentPage', uintValue: requestedCurrentPage},
                            {key: 'requestId', textValue: requestId},
                            {key: 'cookies', textValue: requestedCookies},
                            {key: 'widgetVersion', uintValue: 1023022},
                            {key: 'windowWidth', uintValue: window.screen.availWidth},
                            {key: 'fontRatio', uintValue: 100},
                            {key: 'TemplateNightModeType', uintValue: window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 1 : 0},
                            {key: 'firstSearchRequest', uintValue: requestedOffset === 0 ? 1 : 0},
                            {key: 'notFirstSearchAction', uintValue: requestedOffset === 0 ? 0 : 1},
                            {key: 'firstSearchQuery', textValue: requestedQuery},
                            {key: 'diffRequestId', textValue: requestId},
                            {key: 'realH5Version', uintValue: 80214109}
                        ]);
                        var request = Object.assign({}, base, {
                            query: requestedQuery,
                            offset: requestedOffset,
                            type: 262208,
                            reqBusinessType: 262208,
                            isHomePage: 0,
                            subType: 0,
                            scene: 14,
                            sceneActionType: 0,
                            lang: params.get('lang') || 'en',
                            platform: 'android',
                            requestId: requestId,
                            searchId: requestedSearchId,
                            tagInfo: requestedTagInfo,
                            matchUser: {},
                            numConditions: [],
                            extReqParams: requestExt
                        });
                        window.__MC_DIRECT_REQUEST = request;
                        window.__MC_DIRECT_RETURN = window.webSearchJSApi.getSearchData(JSON.stringify(request));
                        return JSON.stringify({phase: 'submitted', request: request, nativeReturn: window.__MC_DIRECT_RETURN});
                    })()`;
                    instance.evaluateJavascript(expression, Callback.$new());
                    setTimeout(function () {
                        Java.scheduleOnMainThread(function () {
                            instance.evaluateJavascript(
                                `JSON.stringify({phase: 'completed', webViewUrl: location.href, request: window.__MC_DIRECT_REQUEST, result: window.__MC_DIRECT_RESULT})`,
                                Callback.$new()
                            );
                        });
                    }, waitMs);
                });
            });
        }
    });
});
}, 500);
