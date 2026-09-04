'use strict';

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.DomValueCallback' + Date.now(),
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) {
                send({kind: 'dom-inspection', value: String(value)});
            }
        }
    });
    const expression = `(function () {
        var nodes = Array.from(document.querySelectorAll('*'));
        var vueNodes = nodes.filter(function (element) { return !!element.__vue__; });
        var root = document.querySelector('#app');
        var vm = root && root.__vue__;
        var store = vm && vm.$store;
        var state = store && store.state;
        var result = state && state.result;
        return JSON.stringify({
            url: location.href,
            bodyLength: document.body ? document.body.innerHTML.length : -1,
            bodyText: document.body ? document.body.innerText.slice(0, 1000) : '',
            frameCount: window.frames.length,
            iframeCount: document.querySelectorAll('iframe').length,
            weappCount: document.querySelectorAll('.weapp').length,
            nodeCount: nodes.length,
            rootHasVue: !!vm,
            resultState: result ? {
                state: result.state,
                selfBase: result.self && result.self.base,
                getDataParams: result.getDataParams,
                requestId: result.requestId
            } : null,
            extReqParams: store && store.getters ? store.getters.getExtReqParams : null,
            miniCrawlerBatch: window.__MC_BATCH ? {
                queryIndex: window.__MC_BATCH.queryIndex,
                total: window.__MC_BATCH.queries && window.__MC_BATCH.queries.length,
                done: window.__MC_BATCH.done,
                active: window.__MC_BATCH.active,
                outputCount: window.__MC_BATCH.output && window.__MC_BATCH.output.length
            } : null,
            nodes: vueNodes.slice(0, 100).map(function (element) {
                return {
                    tag: element.tagName,
                    className: element.className,
                    dataId: element.getAttribute('data-id'),
                    text: (element.innerText || '').slice(0, 300),
                    hasVue: !!element.__vue__
                };
            })
        });
    })()`;
    const instances = [];
    Java.choose('com.tencent.mm.ui.widget.MMWebView', {
        onMatch(instance) {
            instances.push(Java.retain(instance));
        },
        onComplete() {
            Java.scheduleOnMainThread(function () {
                instances.forEach(function (instance) {
                    if (!String(instance.getUrl()).includes('websearch')) return;
                    instance.evaluateJavascript(expression, Callback.$new());
                });
            });
        }
    });
});
