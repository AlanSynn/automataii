const encoder = new TextEncoder();
const CRC_TABLE = Array.from({ length: 256 }, (_, i) => {
  let c = i;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

export function createZipBlob(files) {
  return new Blob([createZipBytes(files)], { type: "application/zip" });
}

export function createZipBytes(files) {
  const local = [];
  const central = [];
  let offset = 0;
  for (const file of files) {
    const name = encoder.encode(file.name);
    const data = typeof file.content === "string" ? encoder.encode(file.content) : new Uint8Array(file.content);
    const crc = crc32(data);
    const header = record(30 + name.length);
    writeLocalHeader(header, name, data, crc);
    local.push(header, data);
    const directory = record(46 + name.length);
    writeCentralHeader(directory, name, data, crc, offset);
    central.push(directory);
    offset += header.length + data.length;
  }
  const centralSize = central.reduce((sum, item) => sum + item.length, 0);
  const end = record(22);
  view(end).setUint32(0, 0x06054b50, true);
  view(end).setUint16(8, files.length, true);
  view(end).setUint16(10, files.length, true);
  view(end).setUint32(12, centralSize, true);
  view(end).setUint32(16, offset, true);
  return concat([...local, ...central, end]);
}

export function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function writeLocalHeader(bytes, name, data, crc) {
  const v = view(bytes);
  v.setUint32(0, 0x04034b50, true);
  v.setUint16(4, 20, true);
  v.setUint32(14, crc, true);
  v.setUint32(18, data.length, true);
  v.setUint32(22, data.length, true);
  v.setUint16(26, name.length, true);
  bytes.set(name, 30);
}

function writeCentralHeader(bytes, name, data, crc, offset) {
  const v = view(bytes);
  v.setUint32(0, 0x02014b50, true);
  v.setUint16(4, 20, true);
  v.setUint16(6, 20, true);
  v.setUint32(16, crc, true);
  v.setUint32(20, data.length, true);
  v.setUint32(24, data.length, true);
  v.setUint16(28, name.length, true);
  v.setUint32(42, offset, true);
  bytes.set(name, 46);
}

function record(length) {
  return new Uint8Array(length);
}

function view(bytes) {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

function concat(chunks) {
  const out = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}
