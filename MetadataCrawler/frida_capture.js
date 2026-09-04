'use strict';

function emit(kind, value, extra) {
    send({
        kind: kind,
        value: String(value),
        extra: extra || null,
        timestamp: new Date().toISOString()
    });
}

function relevant(value) {
    if (value === null || value === undefined) return false;
    const text = String(value).toLowerCase();
    return text.includes('innersearch') ||
        text.includes('subsearch') ||
        text.includes('finderinnersearch') ||
        (text.includes('search') &&
            (text.includes('weixin.qq.com') || text.includes('wechat.com') ||
             text.includes('appbrand') || text.includes('miniprogram') ||
             text.includes('wxa')));
}

function hookOverloads(className, methodName, renderer) {
    try {
        const klass = Java.use(className);
        const method = klass[methodName];
        method.overloads.forEach(function (overload) {
            overload.implementation = function () {
                const args = Array.prototype.slice.call(arguments);
                try {
                    const rendered = renderer(args, this);
                    if (relevant(rendered)) emit(className + '.' + methodName, rendered);
                } catch (error) {
                    emit('hook-error', className + '.' + methodName + ': ' + error);
                }
                return overload.apply(this, args);
            };
        });
        emit('hooked', className + '.' + methodName);
    } catch (error) {
        // The dependency is optional or not loaded in this process.
    }
}

Java.perform(function () {
    hookOverloads('java.net.URL', 'openConnection', function (_args, receiver) {
        return receiver.toString();
    });
    hookOverloads('android.net.Uri', 'parse', function (args) {
        return args.map(String).join(' ');
    });
    hookOverloads('android.webkit.WebView', 'loadUrl', function (args) {
        return args.map(String).join(' ');
    });
    hookOverloads('okhttp3.Request$Builder', 'url', function (args) {
        return args.map(String).join(' ');
    });
    hookOverloads('org.chromium.net.UrlRequest$Builder', 'build', function (_args, receiver) {
        return receiver.toString();
    });
});

['SSL_write', 'SSL_write_ex'].forEach(function (symbol) {
    try {
        const address = Module.getGlobalExportByName(symbol);
        Interceptor.attach(address, {
            onEnter: function (args) {
                try {
                    const length = symbol === 'SSL_write' ? args[2].toInt32() : 65536;
                    if (length <= 0 || length > 1024 * 1024) return;
                    const text = args[1].readUtf8String(length);
                    if (relevant(text)) emit('native.' + symbol, text);
                } catch (error) {
                    // Binary TLS records and unreadable buffers are expected.
                }
            }
        });
        emit('hooked', 'native.' + symbol);
    } catch (error) {
        // WeChat may use a private or statically linked TLS implementation.
    }
});
