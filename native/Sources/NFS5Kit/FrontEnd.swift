import Foundation

/// Данные интерфейса игры: макеты меню (FEData/Layouts/*.lay),
/// таблица строк (FEData/Locale/festrings.loc), изображения (FEData/Art/*.fsh) и
/// таблицы машин и трасс (FEData/Data/nfs5.car, nfs5.trk). Здесь читаются только данные;
/// оригинальная логика меню из исполняемого файла в этот модуль не входит.

/// FEData/Locale/*.loc: «LOCI» сопоставляет идентификаторы строк с индексами в «LOCL».
public struct StringTable {
    public let strings: [Int: String]

    public init(url: URL, language: Int = 0) throws {
        let d = try readBytes(url)
        guard d.ascii(0, 4) == "LOCH" else { throw NFS5Error.format("not a LOC file") }
        let nBlocks = Int(d.u32(12))
        let offsets = (0..<nBlocks).map { Int(d.u32(16 + 4 * $0)) }
        var ids: [(Int, Int)] = []
        if d.ascii(44, 4) == "LOCI" {
            let count = Int(d.u32(52))
            ids = (0..<count).map { (d.u16(60 + 4 * $0), d.u16(62 + 4 * $0)) }
        }
        let blocks = offsets.filter { d.ascii($0, 4) == "LOCL" }
        guard language < blocks.count else { throw NFS5Error.format("no language \(language)") }
        let o = blocks[language]
        let count = Int(d.u32(o + 12))
        let texts: [String] = (0..<count).map { i in
            let s = o + Int(d.u32(o + 16 + 4 * i))
            var e = s
            while e < d.count && d[e] != 0 { e += 1 }
            return String(decoding: d[s..<e], as: UTF8.self)
        }
        var map: [Int: String] = [:]
        for (id, idx) in ids where idx < texts.count { map[id] = texts[idx] }
        strings = map
    }

    public subscript(id: Int) -> String? { strings[id] }
}

/// Один элемент макета меню («[section.N]»).
public struct LayoutElement {
    public let fields: [String: String]
    public var type: String { fields["id"] ?? "" }
    public var name: String { fields["name"] ?? "" }

    public func ints(_ key: String) -> [Int] {
        (fields[key] ?? "").split(separator: ",").map { Int($0.trimmingCharacters(in: .whitespaces)) ?? 0 }
    }
    public func int(_ key: String) -> Int? { Int(fields[key] ?? "") }
    /// Цвета записаны в формате 0xAARRGGBB.
    public func color(_ key: String) -> UInt32? {
        guard var s = fields[key], !s.isEmpty else { return nil }
        if s.lowercased().hasPrefix("0x") { s = String(s.dropFirst(2)) }
        return UInt32(s, radix: 16)
    }
}

public struct Layout {
    public let name: String
    public let elements: [LayoutElement]

    public init(url: URL) throws {
        name = url.deletingPathExtension().lastPathComponent
        let ini = parseINI(try readBytes(url))
        elements = ini.keys
            .compactMap { k -> (Int, LayoutElement)? in
                guard k.hasPrefix("section."), let n = Int(k.dropFirst(8)) else { return nil }
                return (n, LayoutElement(fields: ini[k]!))
            }
            .sorted { $0.0 < $1.0 }.map { $0.1 }
    }

    /// Имя фонового макета из секции 0 («screen=ID_MOVIEOVAL» → ScreenMovieOval).
    public var backgroundName: String? {
        guard let s = elements.first?.fields["screen"], s.hasPrefix("ID_"), s != "ID_SCREEN" else { return nil }
        let words = s.dropFirst(3).lowercased()
        return "Screen" + words
    }
}

/// FEData/Data/nfs5.trk: 15 записей по 1192 байта; имя трассы начинается по смещению +8,
/// имя изображения — по +48. Остальные поля здесь не используются.
public struct TrackEntry {
    public let file: String
    public let art: String
}

public func loadTrackTable(_ url: URL) throws -> [TrackEntry] {
    let d = try readBytes(url)
    guard d.count % 1192 == 0 else { throw NFS5Error.format("nfs5.trk: unexpected size") }
    return stride(from: 0, to: d.count, by: 1192).map {
        TrackEntry(file: d.cString($0 + 8, max: 32), art: d.cString($0 + 48, max: 20))
    }
}

/// Поиск файла в каталоге без учёта регистра.
public func findFile(_ name: String, in dir: URL) -> URL? {
    let files = (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []
    return files.first { $0.lowercased() == name.lowercased() }.map { dir.appendingPathComponent($0) }
}

/// Данные интерфейса из корневого каталога пользовательской копии игры.
public final class FrontEndData {
    public let root: URL
    public let strings: StringTable
    public let cars: CarDB
    public let tracks: [TrackEntry]
    private var fshCache: [String: [FSHImage]] = [:]

    public init(root: URL) throws {
        self.root = root
        let fe = root.appendingPathComponent("FEData")
        strings = try StringTable(url: fe.appendingPathComponent("Locale/festrings.loc"))
        cars = try CarDB(url: fe.appendingPathComponent("Data/nfs5.car"))
        tracks = try loadTrackTable(fe.appendingPathComponent("Data/nfs5.trk"))
    }

    public func layout(_ name: String) -> Layout? {
        guard let url = findFile(name + ".lay", in: root.appendingPathComponent("FEData/Layouts")) else { return nil }
        return try? Layout(url: url)
    }

    /// Картинки архива FSH из FEData/<каталог>; по умолчанию Art.
    public func images(_ file: String, dir: String = "Art") -> [FSHImage] {
        let key = dir + "/" + file.lowercased()
        if let c = fshCache[key] { return c }
        var out: [FSHImage] = []
        if let url = findFile(file, in: root.appendingPathComponent("FEData/" + dir)),
           let raw = try? readBytes(url), let imgs = try? FSH.parse(RefPack.load(raw)) {
            out = imgs
        }
        fshCache[key] = out
        return out
    }

    /// Доступные модели, для которых есть запись в таблице автомобилей и имя SIM-файла.
    public func carModelsAvailable(carModelDir: URL) -> [CarDB.Entry] {
        let models = Set(CarModel.carNames(in: carModelDir).map { $0.lowercased() })
        return cars.entries.filter { !$0.model.isEmpty && models.contains($0.model.lowercased()) && !$0.sim.isEmpty }
    }
}
