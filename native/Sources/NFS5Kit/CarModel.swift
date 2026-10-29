import Foundation

/// Автомобиль из CarModel/<имя>.{crp,tpg,clr}; перенос src/nfs5/car.py.
public struct TexturePage {
    public enum Mode: String { case opaque, mask, blend }
    public let index: Int
    public let width: Int
    public let height: Int
    public var rgba: [UInt8]
    public let mode: Mode
    public let painted: Bool
}

public struct CarBatch {
    public let page: Int
    public var positions: [SIMD3<Float>] = []
    public var normals: [SIMD3<Float>] = []
    public var uvs: [SIMD2<Float>] = []
}

public final class CarModel {
    static let globalFiles = [1: "Shadow.fsh", 2: "INTGLASS.FSH", 3: "Suit.fsh", 4: "Head.fsh", 5: "Cabrio.fsh"]
    public static let hiddenPrefixes = ["Cabrio", "Driver", "Legs", "LeftArm", "RightArm", "LeftHand",
                                        "RightHand", "LOD", "Glare", "DecalHood", "DecalDoor", "DecalTrunk"]

    public let name: String
    public let crp: CRP
    public let tpg: INI
    public let paint: SIMD3<Float>
    public private(set) var pages: [Int: TexturePage] = [:]

    public static func carNames(in dir: URL) -> [String] {
        let files = (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []
        return files.filter { $0.lowercased().hasSuffix(".crp") }.map { String($0.dropLast(4)) }.sorted()
    }

    public init(dir: URL, name: String, colour: Int = 1) throws {
        self.name = name
        crp = try CRP(readBytes(dir.appendingPathComponent("\(name).crp")))
        tpg = parseINI(try readBytes(dir.appendingPathComponent("\(name).tpg")))
        let clrURL = dir.appendingPathComponent("\(name).clr")
        if let clr = try? readBytes(clrURL), let s = parseINI(clr)["section\(colour)"],
           let r = Float(s["color1.r"] ?? ""), let g = Float(s["color1.g"] ?? ""), let b = Float(s["color1.b"] ?? "") {
            paint = SIMD3(r, g, b) / 255
        } else {
            paint = SIMD3(0.8, 0.8, 0.8)
        }
        try buildPages(dir: dir)
    }

    private func buildPages(dir: URL) throws {
        let header = tpg["header"] ?? [:]
        let nPages = Int(header["numtpages"] ?? "0") ?? 0
        let nFiles = Int(header["numfiles"] ?? "0") ?? 0
        let embedded = try crp.textures()
        var fileOfPage: [Int: (Int, [String: String])] = [:]
        for f in 1...max(nFiles, 1) {
            if let det = tpg["file\(f).details"], let t = Int(det["tpage"] ?? "") { fileOfPage[t] = (f, det) }
        }
        for t in 1...max(nPages, 1) {
            let det = tpg["tpage\(t).details"] ?? [:]
            let w = Int(det["width"] ?? "256") ?? 256, h = Int(det["height"] ?? "256") ?? 256
            // «sourcetpage»: атлас зеркальной половины; каждая картинка отражается на своём месте.
            let source = Int(det["sourcetpage"] ?? "")
            let (file, fdet) = fileOfPage[source ?? t] ?? (0, [:])
            var images: [FSHImage]? = embedded[file - 1]
            if images == nil, let g = Int(fdet["global"] ?? ""), let gname = Self.globalFiles[g] {
                images = try? FSH.parse(RefPack.load(readBytes(dir.appendingPathComponent(gname))))
            }
            var rgba = images.map { compose($0, w, h, mirror: source != nil) }
                ?? [UInt8](repeating: 255, count: w * h * 4)
            let fname = header["file\(file)"] ?? ""
            let painted = fname == "exterior.fsh"
            if painted { applyPaint(&rgba) }
            let mode: TexturePage.Mode = det["window"] == "1" || ["glass.fsh", "intglass.fsh", "shadow.fsh"].contains(fname)
                ? .blend : painted ? .opaque : .mask
            pages[t - 1] = TexturePage(index: t - 1, width: w, height: h, rgba: rgba, mode: mode, painted: painted)
        }
    }

    /// Размещает картинки по координатам SHPI; первая или предпочтительная имеет приоритет.
    private func compose(_ images: [FSHImage], _ w: Int, _ h: Int, mirror: Bool = false) -> [UInt8] {
        let prefer: Set<String> = ["whg", "top"]
        var ordered = images.enumerated().sorted {
            let pa = prefer.contains($0.element.name.trimmingCharacters(in: .whitespaces))
            let pb = prefer.contains($1.element.name.trimmingCharacters(in: .whitespaces))
            return pa != pb ? pa : $0.offset < $1.offset
        }.map { $0.element }
        ordered.reverse()
        var page = [UInt8](repeating: 0, count: w * h * 4)
        for img in ordered {
            for y in 0..<img.height where img.y + y < h {
                for x in 0..<img.width where img.x + x < w {
                    let sx = mirror ? img.width - 1 - x : x
                    let dst = 4 * ((img.y + y) * w + img.x + x), src = 4 * (y * img.width + sx)
                    for c in 0..<4 { page[dst + c] = img.rgba[src + c] }
                }
            }
        }
        return page
    }

    private func applyPaint(_ rgba: inout [UInt8]) {
        for i in stride(from: 0, to: rgba.count, by: 4) {
            if rgba[i + 3] < 255 {
                for c in 0..<3 { rgba[i + c] = UInt8(min(255, Float(rgba[i + c]) * paint[c])) }
            }
            rgba[i + 3] = 255
        }
    }

    /// Видимые треугольники сгруппированы по текстурной странице и переведены в правую
    /// систему координат: Z инвертирована, обход изменён, как в src/nfs5/export.py.
    /// Перенос car.overlapping_variants: убираем варианты детали, которые находятся
    /// на месте базовой детали; это приближение к выбору варианта кузова игрой.
    static func overlappingVariants(_ meshes: [(String, CRPMesh)], grid: Double = 0.01, share: Double = 0.3) -> Set<String> {
        struct Cell: Hashable { let x, y, z: Int64 }
        var cells: [String: Set<Cell>] = [:]
        for (name, m) in meshes {
            var set = cells[name] ?? []
            for k in stride(from: 0, to: m.positions.count - 2, by: 3) {
                let a = m.positions[k], b = m.positions[k + 1], c = m.positions[k + 2]
                let cx = (Double(a.x) + Double(b.x) + Double(c.x)) / 3.0
                let cy = (Double(a.y) + Double(b.y) + Double(c.y)) / 3.0
                let cz = (Double(a.z) + Double(b.z) + Double(c.z)) / 3.0
                set.insert(Cell(x: Int64((cx / grid).rounded(.down)), y: Int64((cy / grid).rounded(.down)),
                                z: Int64((cz / grid).rounded(.down))))
            }
            cells[name] = set
        }
        var groups: [String: [String]] = [:]
        for n in cells.keys { groups[Self.variantBase(n), default: []].append(n) }
        var drop: Set<String> = []
        for names in groups.values {
            var kept: [String] = []
            for n in names.sorted(by: { ($0.count, $0) < ($1.count, $1) }) {
                let own = cells[n]!
                if kept.contains(where: { Double(own.intersection(cells[$0]!).count) > share * Double(own.count) }) {
                    drop.insert(n)
                } else {
                    kept.append(n)
                }
            }
        }
        return drop
    }

    /// Имя с удалённым суффиксом, соответствующим выражению [0-9]*[ab]?$.
    static func variantBase(_ n: String) -> String {
        var s = Substring(n)
        if let l = s.last, l == "a" || l == "b" { s = s.dropLast() }
        while let l = s.last, l.isASCII, l.isNumber { s = s.dropLast() }
        return String(s)
    }

    public func batches(lod: Int = 1, includeHidden: Bool = false) -> [CarBatch] {
        let matPage = crp.materialPages()
        var byPage: [Int: CarBatch] = [:]
        var visible: [(String, CRPMesh)] = []
        for art in crp.articles {
            if !includeHidden && Self.hiddenPrefixes.contains(where: { art.name.hasPrefix($0) }) { continue }
            guard let m = crp.mesh(art, lod: lod) else { continue }
            visible.append((art.name, m))
        }
        let drop = includeHidden ? [] : Self.overlappingVariants(visible)
        for (name, m) in visible where !drop.contains(name) {
            for d in m.draws {
                var page = matPage[d.material] ?? 0
                if pages[page] == nil { page = 0 }
                var b = byPage[page] ?? CarBatch(page: page)
                for k in stride(from: d.first, to: d.first + d.count - 2, by: 3) {
                    for j in [0, 2, 1] {
                        let p = m.positions[k + j], n = m.normals[k + j]
                        b.positions.append(SIMD3(p.x, p.y, -p.z))
                        b.normals.append(SIMD3(n.x, n.y, -n.z))
                        b.uvs.append(m.uvs[k + j])
                    }
                }
                byPage[page] = b
            }
        }
        return byPage.keys.sorted().map { byPage[$0]! }
    }
}
