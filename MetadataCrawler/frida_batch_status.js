'use strict';

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.BatchStatusCallback' + Date.now(),
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) {
                send({kind: 'batch-status', value: String(value)});
            }
        }
    });
    const views = [];
    Java.choose('com.tencent.mm.ui.widget.MMWebView', {
        onMatch(instance) { views.push(Java.retain(instance)); },
        onComplete() {
            Java.scheduleOnMainThread(function () {
                views.forEach(function (view) {
                    if (!String(view.getUrl()).includes('websearch')) return;
                    view.evaluateJavascript(`JSON.stringify(window.__MC_BATCH ? {
                        queryIndex: window.__MC_BATCH.queryIndex,
                        total: window.__MC_BATCH.queries && window.__MC_BATCH.queries.length,
                        done: window.__MC_BATCH.done,
                        active: window.__MC_BATCH.active,
                        outputCount: window.__MC_BATCH.output && window.__MC_BATCH.output.length
                    } : null)`, Callback.$new());
                });
            });
        }
    });
});
