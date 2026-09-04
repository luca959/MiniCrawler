'use strict';

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.PageRequestCallback' + Date.now(),
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) {
                send({kind: 'page-request-capture', value: String(value)});
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
                views.forEach(function (view) {
                    if (!String(view.getUrl()).includes('websearch')) return;
                    view.evaluateJavascript(`(function () {
                        window.__MC_PAGE_REQUESTS = [];
                        if (!window.webSearchJSApi.__mcOriginalGetSearchData) {
                            var original = window.webSearchJSApi.getSearchData.bind(window.webSearchJSApi);
                            window.webSearchJSApi.__mcOriginalGetSearchData = original;
                            window.webSearchJSApi.getSearchData = function (request) {
                                window.__MC_PAGE_REQUESTS.push(request);
                                return original(request);
                            };
                        }
                        window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));
                        window.dispatchEvent(new Event('scroll'));
                        document.dispatchEvent(new Event('scroll'));
                        return JSON.stringify({phase: 'armed', height: document.body.scrollHeight, y: window.scrollY});
                    })()`, Callback.$new());
                    setTimeout(function () {
                        Java.scheduleOnMainThread(function () {
                            view.evaluateJavascript(
                                `JSON.stringify({phase: 'captured', requests: window.__MC_PAGE_REQUESTS || [], y: window.scrollY, height: document.body.scrollHeight})`,
                                Callback.$new()
                            );
                        });
                    }, 9000);
                });
            });
        }
    });
});
