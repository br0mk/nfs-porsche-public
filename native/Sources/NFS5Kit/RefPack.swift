/// Распаковка RefPack («QFS») на основе LZ77, используемая EA для CRP и FSH.
public enum RefPack {
    public static func isRefPack(_ d: [UInt8]) -> Bool {
        d.count >= 5 && d[1] == 0xFB && (d[0] & 0x3E) == 0x10
    }

    public static func decompress(_ d: [UInt8]) throws -> [UInt8] {
        guard isRefPack(d) else { throw NFS5Error.format("not a RefPack stream") }
        let flags = d[0]
        let sizeLen = flags & 0x80 != 0 ? 4 : 3
        var pos = 2
        if flags & 0x01 != 0 { pos += sizeLen }
        var outLen = 0
        for i in 0..<sizeLen { outLen = outLen << 8 | Int(d[pos + i]) }
        pos += sizeLen

        var out = [UInt8](repeating: 0, count: outLen)
        var o = 0
        func copyLiteral(_ n: Int) throws {
            guard pos + n <= d.count, o + n <= outLen else { throw NFS5Error.format("literal overrun") }
            for i in 0..<n { out[o + i] = d[pos + i] }
            o += n
            pos += n
        }
        while pos < d.count {
            let b0 = Int(d[pos])
            var lit = 0, length = 0, dist = 0
            if b0 < 0x80 {
                let b1 = Int(d[pos + 1]); pos += 2
                lit = b0 & 3; length = ((b0 & 0x1C) >> 2) + 3; dist = ((b0 & 0x60) << 3) + b1 + 1
            } else if b0 < 0xC0 {
                let b1 = Int(d[pos + 1]), b2 = Int(d[pos + 2]); pos += 3
                lit = b1 >> 6; length = (b0 & 0x3F) + 4; dist = ((b1 & 0x3F) << 8) + b2 + 1
            } else if b0 < 0xE0 {
                let b1 = Int(d[pos + 1]), b2 = Int(d[pos + 2]), b3 = Int(d[pos + 3]); pos += 4
                lit = b0 & 3; length = ((b0 & 0x0C) << 6) + b3 + 5; dist = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
            } else if b0 < 0xFC {
                pos += 1
                try copyLiteral(((b0 & 0x1F) + 1) * 4)
                continue
            } else {
                pos += 1
                try copyLiteral(b0 & 3)
                break
            }
            try copyLiteral(lit)
            let src = o - dist
            guard src >= 0, o + length <= outLen else { throw NFS5Error.format("bad back-reference") }
            for i in 0..<length { out[o + i] = out[src + i] }  // Области могут перекрываться.
            o += length
        }
        guard o == outLen else { throw NFS5Error.format("size mismatch \(o) != \(outLen)") }
        return out
    }

    /// Возвращает распакованные данные RefPack либо исходные данные другого формата.
    public static func load(_ d: [UInt8]) throws -> [UInt8] {
        isRefPack(d) ? try decompress(d) : d
    }
}
