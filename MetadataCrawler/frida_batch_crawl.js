'use strict';

setTimeout(function () {
    const options = globalThis.__MC_OPTIONS || {};
    const queries = Array.isArray(options.queries) ? options.queries.map(String) : [];
    const delayMs = Number(options.delay_ms || 1500);
    const maxPages = Number(options.max_pages || 5);

    Java.perform(function () {
        const Callback = Java.registerClass({
            name: 'org.minicrawler.BatchPollCallback' + Date.now(),
            implements: [Java.use('android.webkit.ValueCallback')],
            methods: {
                onReceiveValue(value) {
                    send({kind: 'batch-poll', value: String(value)});
                }
            }
        });
        const views = [];
        Java.choose('com.tencent.mm.ui.widget.MMWebView', {
            onMatch(instance) {
                views.push(Java.retain(instance));
            },
            onComplete() {
                Java.scheduleOnMainThread(function () {
                    const view = views.find(function (candidate) {
                        return String(candidate.getUrl()).includes('websearch');
                    });
                    if (!view) {
                        send({kind: 'batch-fatal', error: 'WebSearch WebView non trovata'});
                        return;
                    }
                    const expression = `(function () {
                        var queries = ${JSON.stringify(queries)};
                        var delayMs = ${JSON.stringify(delayMs)};
                        var maxPages = ${JSON.stringify(maxPages)};
                        var previous = window.__MC_BATCH;
                        if (previous && typeof previous.restore === 'function') previous.restore();
                        var oldReady = window.onSearchDataReady;
                        var state = {
                            queries: queries,
                            queryIndex: 0,
                            active: null,
                            output: [],
                            done: false,
                            oldReady: oldReady
                        };
                        window.__MC_BATCH = state;
                        state.restore = function () {
                            if (window.onSearchDataReady === state.onReady) {
                                window.onSearchDataReady = state.oldReady;
                            }
                        };
                        state.take = function () {
                            var output = state.output.splice(0, state.output.length);
                            return JSON.stringify({results: output, done: state.done, queryIndex: state.queryIndex, total: state.queries.length});
                        };
                        function uuid() {
                            if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
                            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
                                var r = Math.random() * 16 | 0;
                                return (c === 'x' ? r : (r & 3 | 8)).toString(16);
                            });
                        }
                        function stableExt() {
                            try {
                                var vm = document.querySelector('#app').__vue__;
                                return (vm.$store.getters.getExtReqParams || []).filter(function (item) {
                                    return ![
                                        'currentPage', 'requestId', 'cookies', 'firstSearchRequest',
                                        'notFirstSearchAction', 'firstSearchQuery', 'diffRequestId',
                                        'realH5Version', 'netType'
                                    ].includes(item.key);
                                });
                            } catch (_) {
                                return [];
                            }
                        }
                        function submit(query, offset, cookies, searchId, page) {
                            var requestId = uuid();
                            var params = new URLSearchParams(location.search);
                            var base = window.Global && typeof window.Global.getBase === 'function'
                                ? window.Global.getBase()
                                : {};
                            var ext = stableExt().concat([
                                {key: 'netType', textValue: params.get('netType') || 'wifi'},
                                {key: 'currentPage', uintValue: page},
                                {key: 'requestId', textValue: requestId},
                                {key: 'cookies', textValue: cookies || ''},
                                {key: 'widgetVersion', uintValue: 1023022},
                                {key: 'windowWidth', uintValue: window.screen.availWidth},
                                {key: 'fontRatio', uintValue: 100},
                                {key: 'TemplateNightModeType', uintValue: window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 1 : 0},
                                {key: 'firstSearchRequest', uintValue: offset === 0 ? 1 : 0},
                                {key: 'notFirstSearchAction', uintValue: offset === 0 ? 0 : 1},
                                {key: 'firstSearchQuery', textValue: query},
                                {key: 'diffRequestId', textValue: requestId},
                                {key: 'realH5Version', uintValue: 80214109}
                            ]);
                            var request = Object.assign({}, base, {
                                query: query,
                                offset: offset,
                                type: 262208,
                                reqBusinessType: 262208,
                                isHomePage: 0,
                                subType: 0,
                                scene: 14,
                                sceneActionType: 0,
                                requestId: requestId,
                                searchId: searchId || '',
                                tagInfo: {},
                                matchUser: {},
                                numConditions: [],
                                extReqParams: ext
                            });
                            var active = {query: query, offset: offset, page: page, requestId: requestId, timeoutId: null};
                            state.active = active;
                            window.webSearchJSApi.getSearchData(JSON.stringify(request));
                            active.timeoutId = setTimeout(function () {
                                if (state.active !== active) return;
                                state.output.push({query: query, offset: offset, page: page, result: null, error: 'timeout risposta WeChat'});
                                state.active = null;
                                state.queryIndex += 1;
                                setTimeout(nextQuery, delayMs);
                            }, 20000);
                        }
                        function nextQuery() {
                            if (state.queryIndex >= state.queries.length) {
                                state.done = true;
                                state.restore();
                                return;
                            }
                            submit(state.queries[state.queryIndex], 0, '', '', 1);
                        }
                        state.onReady = function (data) {
                            var active = state.active;
                            if (!active || !data || data.requestId !== active.requestId) return;
                            if (active.timeoutId) clearTimeout(active.timeoutId);
                            state.active = null;
                            var body = null;
                            var error = '';
                            try {
                                body = typeof data.json === 'string' ? JSON.parse(data.json) : data.json;
                            } catch (e) {
                                error = String(e);
                            }
                            state.output.push({query: active.query, offset: active.offset, page: active.page, result: data, error: error});
                            if (!body || body.ret && body.ret !== 0) {
                                state.queryIndex += 1;
                                setTimeout(nextQuery, delayMs);
                                return;
                            }
                            var nextOffset = Number(body.offset || 0);
                            if (body.continueFlag && active.page < maxPages && nextOffset > active.offset) {
                                setTimeout(function () {
                                    submit(
                                        active.query,
                                        nextOffset,
                                        typeof body.cookies === 'string' ? body.cookies : JSON.stringify(body.cookies || {}),
                                        String(body.searchID || body.searchId || ''),
                                        active.page + 1
                                    );
                                }, delayMs);
                            } else {
                                state.queryIndex += 1;
                                setTimeout(nextQuery, delayMs);
                            }
                        };
                        window.onSearchDataReady = state.onReady;
                        setTimeout(nextQuery, 100);
                        return JSON.stringify({armed: true, queries: queries.length});
                    })()`;
                    view.evaluateJavascript(expression, Callback.$new());
                    const poller = setInterval(function () {
                        Java.scheduleOnMainThread(function () {
                            view.evaluateJavascript(
                                `window.__MC_BATCH && typeof window.__MC_BATCH.take === 'function' ? window.__MC_BATCH.take() : JSON.stringify({results: [], done: false})`,
                                Callback.$new()
                            );
                        });
                    }, 750);
                    setTimeout(function () {
                        clearInterval(poller);
                    }, Math.max(60000, queries.length * maxPages * (delayMs + 10000)));
                });
            }
        });
    });
}, 500);
