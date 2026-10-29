import Foundation

/// Модель трассы: GameData/Track/<имя>.crp («Trak») и <имя>.fsh; перенос src/nfs5/track.py.
public struct TrackBatch {
    public let texture: String
    public let kind: String
    public let mode: TexturePage.Mode
    public let image: FSHImage?
    public var positions: [SIMD3<Float>] = []
    public var uvs: [SIMD2<Float>] = []
    /// RGBA от 0 до 1; исходный BGRA из «df» умножается на 2 и ограничивается.
    public var colors: [SIMD4<Float>] = []
}

public struct RoadNode {
    public let position: SIMD3<Float>
    public let up: SIMD3<Float>
    public let forward: SIMD3<Float>
    public var right: SIMD3<Float> = .zero
    /// Ширина дорожной поверхности в направлениях −right и +right от осевой, в метрах.
    /// Первые два значения ширины SimD; проверены по геометрии дороги «RD».
    public var widthLeft: Float = 5
    public var widthRight: Float = 5

    public init(position: SIMD3<Float>, up: SIMD3<Float>, forward: SIMD3<Float>, right: SIMD3<Float> = .zero,
                widthLeft: Float = 5, widthRight: Float = 5) {
        self.position = position; self.up = up; self.forward = forward; self.right = right
        self.widthLeft = widthLeft; self.widthRight = widthRight
    }
}

public final class Track {
    public let name: String
    public let crp: CRP
    public let images: [String: FSHImage]
    public let materials: [Int: (kind: String, texture: String)]

    public static func trackNames(in dir: URL) -> [String] {
        let files = (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []
        return files.filter { $0.lowercased().hasSuffix(".crp") }.map { String($0.dropLast(4)) }.sorted()
    }

    public init(dir: URL, name: String) throws {
        self.name = name
        crp = try CRP(readBytes(dir.appendingPathComponent("\(name).crp")))
        var imgs: [String: FSHImage] = [:]
        for img in try FSH.parse(RefPack.load(readBytes(dir.appendingPathComponent("\(name).fsh")))) where imgs[img.name] == nil {
            imgs[img.name] = img
        }
        images = imgs
        var mats: [Int: (String, String)] = [:]
        for p in crp.misc where p.tag == "mt" {
            mats[p.index] = (crp.data.cString(p.start + 16, max: 16), crp.data.ascii(p.start + 40, 4))
        }
        materials = mats
    }

    static func alphaMode(kind: String, image: FSHImage?) -> TexturePage.Mode {
        if kind == "FakeSort" { return .blend }
        guard let img = image else { return .opaque }
        var transparent = 0
        for i in stride(from: 3, to: img.rgba.count, by: 4) where img.rgba[i] < 128 { transparent += 1 }
        return Double(transparent) / Double(img.width * img.height) > 0.01 ? .mask : .opaque
    }

    /// Треугольники сгруппированы по текстуре и классу материала; Z и обход инвертированы.
    public func batches(lod: Int = 0) -> [TrackBatch] {
        struct Key: Hashable { let tex: String; let kind: String }
        var groups: [Key: TrackBatch] = [:]
        for art in crp.articles {
            guard let m = crp.mesh(art, lod: lod) else { continue }
            for d in m.draws {
                let mat = materials[d.material]
                let key = Key(tex: mat?.texture ?? "", kind: mat?.kind ?? "Opaque")
                var b = groups[key] ?? TrackBatch(texture: key.tex, kind: key.kind,
                                                  mode: Self.alphaMode(kind: key.kind, image: images[key.tex]),
                                                  image: images[key.tex])
                for k in stride(from: d.first, to: d.first + d.count - 2, by: 3) {
                    for j in [0, 2, 1] {
                        let p = m.positions[k + j], c = m.colors[k + j]
                        b.positions.append(SIMD3(p.x, p.y, -p.z))
                        b.uvs.append(m.uvs[k + j])
                        b.colors.append(SIMD4(min(Float(c[2]) / 128, 1), min(Float(c[1]) / 128, 1),
                                              min(Float(c[0]) / 128, 1), Float(c[3]) / 255))
                    }
                }
                groups[key] = b
            }
        }
        return groups.keys.sorted { ($0.tex, $0.kind) < ($1.tex, $1.kind) }.map { groups[$0]! }
    }

    /// Самая длинная цепочка дороги из «SimD», разделённого по «SimT», в правой системе координат.
    public func road() -> [RoadNode] {
        guard let sd = crp.misc.first(where: { $0.tag == "SimD" }),
              let st = crp.misc.first(where: { $0.tag == "SimT" }) else { return [] }
        let d = crp.data
        func v3(_ o: Int) -> SIMD3<Float> { SIMD3(d.f32(o), d.f32(o + 4), -d.f32(o + 8)) }
        let sizes = (0..<(st.length / 4)).map { Int(d.u32(st.start + 4 * $0)) }
        var chains: [[RoadNode]] = []
        var start = 0
        for n in sizes where n > 0 {
            chains.append((start..<min(start + n, sd.count)).map { i in
                let o = sd.start + 80 * i
                return RoadNode(position: v3(o + 4), up: v3(o + 16), forward: v3(o + 28), right: v3(o + 40),
                                widthLeft: d.f32(o + 64), widthRight: d.f32(o + 68))
            })
            start += n
        }
        return chains.max { $0.count < $1.count } ?? []
    }
}
