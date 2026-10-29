/// Текстурные архивы EA SHPI («FSH»). Структура описана в src/nfs5/fsh.py.
public struct FSHImage {
    public let name: String
    public let width: Int
    public let height: Int
    public let x: Int
    public let y: Int
    /// RGBA8, построчно, начиная с верхней строки.
    public let rgba: [UInt8]
}

public enum FSH {
    public static func parse(_ d: [UInt8]) throws -> [FSHImage] {
        guard d.count >= 16, d.ascii(0, 4) == "SHPI" else { throw NFS5Error.format("not SHPI") }
        let count = Int(d.u32(8))
        var offsets: [(String, Int)] = []
        for i in 0..<count {
            offsets.append((d.ascii(16 + 8 * i, 4), Int(d.u32(20 + 8 * i))))
        }
        let ends = Set(offsets.map { $0.1} + [d.count]).sorted()
        return try offsets.map { name, off in
            let limit = ends.first { $0 > off } ?? d.count
            // Цепочка блоков: u8 код, u24 смещение следующего блока (0 — последний).
            var blocks: [(code: Int, start: Int, end: Int)] = []
            var p = off
            while true {
                let next = d.u24(p + 1)
                blocks.append((d.u8(p), p, next != 0 ? p + next : limit))
                if next == 0 { break }
                p += next
            }
            let img = blocks[0]
            let w = d.u16(img.start + 4), h = d.u16(img.start + 6)
            let x = d.u16(img.start + 12), y = d.u16(img.start + 14)
            var code = img.code
            var pixels = Array(d[(img.start + 16)..<img.end])
            if code & 0x80 != 0 {
                code &= 0x7F
                pixels = try RefPack.decompress(pixels)
            }
            let palette = blocks.dropFirst().first { [0x22, 0x24, 0x29, 0x2A, 0x2D].contains($0.code) }
            let rgba = try decode(code: code, w: w, h: h, px: pixels, d: d, palette: palette)
            return FSHImage(name: name, width: w, height: h, x: x, y: y, rgba: rgba)
        }
    }

    static func expand16(_ v: Int, _ code: Int) -> (UInt8, UInt8, UInt8, UInt8) {
        switch code {
        case 0x78:
            return (UInt8((v >> 11 & 31) * 255 / 31), UInt8((v >> 5 & 63) * 255 / 63), UInt8((v & 31) * 255 / 31), 255)
        case 0x7E:
            return (UInt8((v >> 10 & 31) * 255 / 31), UInt8((v >> 5 & 31) * 255 / 31), UInt8((v & 31) * 255 / 31), UInt8((v >> 15 & 1) * 255))
        default:  // 0x6D 4444
            return (UInt8((v >> 8 & 15) * 17), UInt8((v >> 4 & 15) * 17), UInt8((v & 15) * 17), UInt8((v >> 12 & 15) * 17))
        }
    }

    static func decode(code: Int, w: Int, h: Int, px: [UInt8], d: [UInt8],
                       palette: (code: Int, start: Int, end: Int)?) throws -> [UInt8] {
        let n = w * h
        var out = [UInt8](repeating: 0, count: n * 4)
        func put(_ i: Int, _ c: (UInt8, UInt8, UInt8, UInt8)) {
            out[4 * i] = c.0; out[4 * i + 1] = c.1; out[4 * i + 2] = c.2; out[4 * i + 3] = c.3
        }
        switch code {
        case 0x7B:
            guard let pal = palette else { throw NFS5Error.format("indexed image without palette") }
            let pc = d.u16(pal.start + 4), ps = pal.start + 16
            var table = [(UInt8, UInt8, UInt8, UInt8)](repeating: (0, 0, 0, 0), count: 256)
            for i in 0..<min(pc, 256) {
                switch pal.code {
                case 0x24: table[i] = (d[ps + 3 * i + 2], d[ps + 3 * i + 1], d[ps + 3 * i], 255)
                case 0x29: table[i] = expand16(d.u16(ps + 2 * i), 0x78)
                case 0x2D: table[i] = expand16(d.u16(ps + 2 * i), 0x7E)
                default: table[i] = (d[ps + 4 * i + 2], d[ps + 4 * i + 1], d[ps + 4 * i], d[ps + 4 * i + 3])
                }
            }
            guard px.count >= n else { throw NFS5Error.format("short pixel data") }
            for i in 0..<n { put(i, table[Int(px[i])]) }
        case 0x78, 0x7E, 0x6D:
            guard px.count >= 2 * n else { throw NFS5Error.format("short pixel data") }
            for i in 0..<n { put(i, expand16(px.u16(2 * i), code)) }
        case 0x7F:
            guard px.count >= 3 * n else { throw NFS5Error.format("short pixel data") }
            for i in 0..<n { put(i, (px[3 * i + 2], px[3 * i + 1], px[3 * i], 255)) }
        case 0x7D:
            guard px.count >= 4 * n else { throw NFS5Error.format("short pixel data") }
            for i in 0..<n { put(i, (px[4 * i + 2], px[4 * i + 1], px[4 * i], px[4 * i + 3])) }
        default:
            throw NFS5Error.format(String(format: "unsupported FSH image code 0x%02x", code))
        }
        return out
    }
}
