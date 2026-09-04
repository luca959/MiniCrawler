'use strict';

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.StopBatchCallback' + Date.now(),
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) { send({kind: 'batch-stopped', value: String(value)}); }
        }
    });
    const views = [];
    Java.choose('com.tencent.mm.ui.widget.MMWebView', {
        onMatch(instance) { views.push(Java.retain(instance)); },
        onComplete() {
            Java.scheduleOnMainThread(function () {
                views.forEach(function (view) {
                    if (!String(view.getUrl()).includes('websearch')) return;
                    view.evaluateJavascript(`(function () {
                        var state = window.__MC_BATCH;
                        if (!state) return 'not-running';
                        if (state.active && state.active.timeoutId) clearTimeout(state.active.timeoutId);
                        state.active = null;
                        state.queries = [];
                        state.queryIndex = 0;
                        state.done = true;
                        if (typeof state.restore === 'function') state.restore();
                        return 'stopped';
                    })()`, Callback.$new());
                });
            });
        }
    });
});
