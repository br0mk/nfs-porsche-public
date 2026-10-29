/// Контейнер модели CRP (« raC»). Описание структуры — в src/nfs5/crp.py;
/// это прямой перенос эталонного читателя на Swift.
public struct CRPPart {
    public let index: Int
    public let tag: String
    public let info: UInt32
    public let count: Int
    public let start: Int   // Смещение полезных данных в распакованном файле, в байтах.
    public var length: Int { Int(info >> 8) }
}

public struct CRPArticle {
    public let parts: [CRPPart]
    public let name: String

    public func find(_ tag: String, _ index: Int? = nil) -> [CRPPart] {
        parts.filter { $0.tag == tag && (index == nil || $0.index == index!) }
    }
}

public struct CRPPrimitive {
    public let lod: Int
    public let material: Int
    /// Младший байт флагов: 3 — список треугольников, 1/4 — полоса.
    public let kind: Int
    public var streams: [Int: (offset: Int, length: Int, group: Int)] = [:]
    public var vertexIndices: [Int] = []
    public var uvIndices: [Int] = []
}

public struct CRPMesh {
    public var positions: [SIMD3<Float>] = []
    public var normals: [SIMD3<Float>] = []
    public var uvs: [SIMD2<Float>] = []
    /// Исходные байты «df» в порядке BGRA; белый цвет, если данных нет.
    public var colors: [SIMD4<UInt8>] = []
    /// (материал, первая вершина, число вершин); треугольники без общих индексов.
    public var draws: [(material: Int, first: Int, count: Int)] = []
}

public final class CRP {
    public let data: [UInt8]
    public private(set) var articles: [CRPArticle] = []
    public private(set) var misc: [CRPPart] = []

    public init(_ raw: [UInt8]) throws {
        data = try RefPack.load(raw)
        guard data.count >= 16, ["Car ", "Trak"].contains(tag4(0)) else { throw NFS5Error.format("not a CRP model") }
        let nArticles = Int(data.u32(4) >> 5)
        let miscCount = Int(data.u32(8))
        var pos = 16
        for _ in 0..<nArticles {
            guard tag4(pos) == "Arti" else { throw NFS5Error.format("expected Arti at \(pos)") }
            let count = Int(data.u32(pos + 8))
            let base = pos + Int(data.u32(pos + 12)) * 16
            let parts = (0..<count).map { part(base + 16 * $0) }
            let name = parts.first { $0.tag == "Name" }.map { data.cString($0.start, max: $0.length) } ?? ""
            articles.append(CRPArticle(parts: parts, name: name.trimmingCharacters(in: .whitespaces)))
            pos += 16
        }
        misc = (0..<miscCount).map { part(pos + 16 * $0) }
    }

    private func tag4(_ o: Int) -> String { String(data.ascii(o, 4).reversed()) }

    private func part(_ pos: Int) -> CRPPart {
        let t4 = tag4(pos)
        let isTag4 = t4.allSatisfy { $0.isLetter || $0 == " " } && t4.contains { $0.isLetter }
            && !t4.contains("\0")
        let index = isTag4 ? 0 : data.u16(pos)
        let tag = isTag4 ? t4 : String(data.ascii(pos + 2, 2).reversed())
        return CRPPart(index: index, tag: tag, info: data.u32(pos + 4), count: Int(data.u32(pos + 8)),
                       start: pos + Int(data.u32(pos + 12)))
    }

    public func primitive(_ p: CRPPart) -> CRPPrimitive {
        let b = p.start
        var prim = CRPPrimitive(lod: p.index >> 12, material: Int(data.u32(b + 4) & 0xFFFF),
                                kind: data.u8(b))
        let nStreams = Int(data.u32(b + 40)), nIndex = Int(data.u32(b + 44))
        var q = b + 48
        for _ in 0..<nStreams {
            prim.streams[data.u16(q + 10)] = (Int(data.u32(q + 4)), data.u16(q + 8), data.u16(q + 12))
            q += 16
        }
        var idx: [String: Int] = [:]
        for _ in 0..<nIndex {
            idx[String(data.ascii(q + 2, 2).reversed())] = Int(data.u32(q + 4))
            q += 8
        }
        let seq = Array(0..<p.count)
        prim.vertexIndices = idx["Iv"].map { o in (0..<p.count).map { data.u8(q + o + $0) } } ?? seq
        prim.uvIndices = idx["Iu"].map { o in (0..<p.count).map { data.u8(q + o + $0) } } ?? seq
        return prim
    }

    func floats(_ p: CRPPart, _ width: Int) -> [[Float]] {
        (0..<(p.length / (4 * width))).map { i in (0..<width).map { data.f32(p.start + 4 * (width * i + $0)) } }
    }

    /// Матрица 4×4 для векторов-строк из блока «tr»; перенос в последней строке.
    func transform(_ art: CRPArticle, group: Int) -> [Float]? {
        var t = art.find("tr", group).first
        if t == nil {
            let all = art.find("tr")
            if all.count == 1 { t = all[0] }  // Единственная матрица применяется ко всем группам.
        }
        guard let tr = t else { return nil }
        return (0..<16).map { data.f32(tr.start + 4 * $0) }
    }

    /// Порядок углов, преобразующий примитив в обычный список треугольников.
    static func cornerOrder(_ prim: CRPPrimitive) -> [Int] {
        let n = prim.vertexIndices.count
        guard prim.kind == 1 || prim.kind == 4 else { return Array(0..<(n - n % 3)) }
        var out: [Int] = []
        for i in 0..<max(0, n - 2) {
            let tri = i % 2 == 0 ? [i, i + 1, i + 2] : [i + 1, i, i + 2]
            if Set(tri.map { prim.vertexIndices[$0] }).count == 3 { out += tri }  // Пропускаем вырожденные треугольники, соединяющие полосы.
        }
        return out
    }

    public func mesh(_ art: CRPArticle, lod: Int = 1, damage: Int = 0) -> CRPMesh? {
        let prims = art.find("pr").filter { $0.index >> 12 == lod }.map(primitive)
        if prims.isEmpty { return nil }
        var m = CRPMesh()
        for prim in prims {
            // Виды потоков: 0 — вершины, 1 — нормали, 2 — UV, 3 — цвета («df»).
            guard let vs = prim.streams[0] else { continue }
            let group = vs.group
            guard let vt = art.find("vt", damage << 4 | group).first ?? art.find("vt", group).first else { continue }
            let v = floats(vt, 4)
            let n = (art.find("nm", damage << 4 | group).first ?? art.find("nm", group).first).map { floats($0, 4) }
            let uvPart = art.find("uv", group).first
            let t = uvPart.map { floats($0, 2) } ?? [[0, 0]]
            var colorBase: Int?
            if let cs = prim.streams[3], let df = art.find("df", cs.group).first {
                colorBase = df.start + cs.offset
            }
            let mtx = transform(art, group: group)
            let first = m.positions.count
            for k in Self.cornerOrder(prim) {
                let vi = prim.vertexIndices[k] + vs.offset / 16
                var p = SIMD3<Float>(v[vi][0], v[vi][1], v[vi][2])
                var nn = n.map { SIMD3<Float>($0[vi][0], $0[vi][1], $0[vi][2]) } ?? .zero
                if let a = mtx {
                    p = SIMD3(p.x * a[0] + p.y * a[4] + p.z * a[8] + a[12],
                              p.x * a[1] + p.y * a[5] + p.z * a[9] + a[13],
                              p.x * a[2] + p.y * a[6] + p.z * a[10] + a[14])
                    nn = SIMD3(nn.x * a[0] + nn.y * a[4] + nn.z * a[8],
                               nn.x * a[1] + nn.y * a[5] + nn.z * a[9],
                               nn.x * a[2] + nn.y * a[6] + nn.z * a[10])
                }
                var uv = SIMD2<Float>(0, 0)
                if let us = prim.streams[2], uvPart != nil {
                    let ui = prim.uvIndices[k] + us.offset / 8
                    if ui < t.count { uv = SIMD2(t[ui][0], t[ui][1]) }
                }
                var c = SIMD4<UInt8>(255, 255, 255, 255)
                if let cb = colorBase {
                    let o = cb + 4 * k
                    c = SIMD4(data[o], data[o + 1], data[o + 2], data[o + 3])
                }
                m.positions.append(p); m.normals.append(nn); m.uvs.append(uv); m.colors.append(c)
            }
            m.draws.append((prim.material, first, m.positions.count - first))
        }
        return m
    }

    /// Встроенные архивы SHPI с ключами по индексу «sf».
    public func textures() throws -> [Int: [FSHImage]] {
        var out: [Int: [FSHImage]] = [:]
        for p in misc where p.tag == "sf" {
            out[p.index] = try FSH.parse(Array(data[p.start..<(p.start + p.length)]))
        }
        return out
    }

    /// Индекс материала → номер текстурной страницы с нуля (u32 по смещению 40).
    public func materialPages() -> [Int: Int] {
        var out: [Int: Int] = [:]
        for p in misc where p.tag == "mt" { out[p.index] = Int(data.u32(p.start + 40)) }
        return out
    }
}

import Foundation
