'use strict';

Java.perform(function () {
    const Callback = Java.registerClass({
        name: 'org.minicrawler.WeAppValueCallback',
        implements: [Java.use('android.webkit.ValueCallback')],
        methods: {
            onReceiveValue(value) {
                send({kind: 'weapp-dump', value: String(value)});
            }
        }
    });
    const expression = `(function () {
        return JSON.stringify(Array.from(document.querySelectorAll('.unified-account, .weapp')).map(function (element) {
            var vm = element.__vue__;
            var item = vm && (vm.item || (vm.$props && vm.$props.item));
            if (item) return {item: item, text: element.innerText};
            return {
                docID: element.getAttribute('data-id') || '',
                text: element.innerText,
                html: element.outerHTML,
                vueKeys: vm ? Object.keys(vm) : []
            };
        }));
    })()`;
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
                    instance.evaluateJavascript(expression, Callback.$new());
                });
            });
        }
    });
});
