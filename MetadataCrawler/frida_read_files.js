'use strict';

const openFile = new NativeFunction(Module.getGlobalExportByName('open'), 'int', ['pointer', 'int']);
const readFile = new NativeFunction(Module.getGlobalExportByName('read'), 'int', ['int', 'pointer', 'ulong']);
const closeFile = new NativeFunction(Module.getGlobalExportByName('close'), 'int', ['int']);

rpc.exports = {
    readfile(path) {
        const fd = openFile(Memory.allocUtf8String(path), 0);
        if (fd < 0) throw new Error('cannot open ' + path);
        const bufferSize = 64 * 1024;
        const buffer = Memory.alloc(bufferSize);
        let total = 0;
        try {
            while (true) {
                const size = readFile(fd, buffer, bufferSize);
                if (size < 0) throw new Error('read failed for ' + path);
                if (size === 0) break;
                send({type: 'file-chunk', path: path, offset: total}, buffer.readByteArray(size));
                total += size;
            }
        } finally {
            closeFile(fd);
        }
        return total;
    }
};

