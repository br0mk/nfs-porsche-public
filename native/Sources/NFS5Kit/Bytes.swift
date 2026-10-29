import Foundation

public enum NFS5Error: Error, CustomStringConvertible {
    case format(String)
    public var description: String {
        switch self { case .format(let s): return s }
    }
}

/// Чтение чисел из массива байтов в порядке little-endian.
extension Array where Element == UInt8 {
    @inline(__always) func u8(_ o: Int) -> Int { Int(self[o]) }
    @inline(__always) func u16(_ o: Int) -> Int { Int(self[o]) | Int(self[o + 1]) << 8 }
    @inline(__always) func u24(_ o: Int) -> Int { u16(o) | Int(self[o + 2]) << 16 }
    @inline(__always) func u32(_ o: Int) -> UInt32 {
        UInt32(self[o]) | UInt32(self[o + 1]) << 8 | UInt32(self[o + 2]) << 16 | UInt32(self[o + 3]) << 24
    }
    @inline(__always) func i32(_ o: Int) -> Int { Int(Int32(bitPattern: u32(o))) }
    @inline(__always) func f32(_ o: Int) -> Float { Float(bitPattern: u32(o)) }
    func ascii(_ o: Int, _ n: Int) -> String {
        String(decoding: self[o..<Swift.min(o + n, count)], as: UTF8.self)
    }
    func cString(_ o: Int, max n: Int) -> String {
        var end = o
        while end < Swift.min(o + n, count) && self[end] != 0 { end += 1 }
        return String(decoding: self[o..<end], as: UTF8.self)
    }
}

public func readBytes(_ url: URL) throws -> [UInt8] {
    [UInt8](try Data(contentsOf: url))
}
