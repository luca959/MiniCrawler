'use strict';

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.WebSearchValueCallback',
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) {
                send({kind: 'websearch-dump', value: String(value)});
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
                    const url = String(instance.getUrl());
                    if (!url.includes('websearch')) return;
                    instance.evaluateJavascript(
                        'JSON.stringify(window.__MC_EVENTS || [])',
                        Callback.$new()
                    );
                });
            });
        }
    });
});

