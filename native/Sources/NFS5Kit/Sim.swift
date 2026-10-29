import Foundation

/// Параметры автомобиля (Simulation/CarData/*.sim), перенос src/nfs5/sim.py;
/// представлены только поля с установленным или предполагаемым назначением.
public struct SimParams {
    public let title: String
    public let massKg: Float
    public let wheelbaseMM: Float
    public let engineLayout: Int        // 0 — заднее, 1 — центральное, 2 — переднее расположение двигателя.
    public let turbo: Bool
    public let gearCount: Int
    public let frontDrivePercent: Float // 0 — задний привод.
    public let reverseRatio: Float
    public let gearRatios: [Float]      // Передачи от первой до gearCount.
    public let finalDrive: Float
    public let tyreWidthMM: Float
    public let tyreAspect: Float
    public let rimInches: Float
    public let topSpeedMph: Float
    public let redlineRPM: Float
    public let torqueCurveLbFt: [Float] // 21 точка с шагом 500 об/мин; число уточнено по анализу игры.

    public static let torqueStepRPM: Float = 500

    public init(_ d: [UInt8]) throws {
        guard d.count == 328 else { throw NFS5Error.format("sim: expected 328 bytes, got \(d.count)") }
        title = d.cString(0, max: 64).trimmingCharacters(in: .whitespaces)
        massKg = d.f32(64)
        wheelbaseMM = d.f32(68)
        engineLayout = Int(d.u32(72))
        turbo = d.u32(76) != 0
        gearCount = Int(d.u32(80))
        frontDrivePercent = d.f32(92)
        reverseRatio = d.f32(96)
        gearRatios = (0..<min(Int(d.u32(80)), 6)).map { d.f32(104 + 4 * $0) }
        finalDrive = d.f32(128)
        tyreWidthMM = d.f32(132)
        tyreAspect = d.f32(136)
        rimInches = d.f32(140)
        topSpeedMph = d.f32(144)
        redlineRPM = d.f32(148)
        torqueCurveLbFt = (0..<21).map { d.f32(156 + 4 * $0) }
    }

    public init(url: URL) throws { try self.init(readBytes(url)) }

    /// Радиус качения в метрах, вычисленный по размерам шины.
    public var wheelRadius: Float { (rimInches * 0.0254 + 2 * tyreWidthMM / 1000 * tyreAspect / 100) / 2 }

    /// Момент двигателя в Н·м при заданных оборотах; линейная интерполяция между точками.
    public func torqueNm(rpm: Float) -> Float {
        let x = max(0, rpm) / Self.torqueStepRPM
        let i = min(Int(x), torqueCurveLbFt.count - 2)
        let t = min(x - Float(i), 1)
        return (torqueCurveLbFt[i] * (1 - t) + torqueCurveLbFt[i + 1] * t) * 1.35582
    }
}

/// FEData/Data/nfs5.car: записи по 1648 байт (имя +2, карточка +77, модель +127,
/// SIM-файл +177, изображение для показа +227).
public struct CarDB {
    public struct Entry { public let name, card, model, sim, showcase: String }
    public let entries: [Entry]

    public init(url: URL) throws {
        let d = try readBytes(url)
        guard d.count % 1648 == 0 else { throw NFS5Error.format("nfs5.car: unexpected size") }
        entries = stride(from: 0, to: d.count, by: 1648).map { o in
            Entry(name: d.cString(o + 2, max: 50).trimmingCharacters(in: .whitespaces),
                  card: d.cString(o + 77, max: 50), model: d.cString(o + 127, max: 50),
                  sim: d.cString(o + 177, max: 50), showcase: d.cString(o + 227, max: 50))
        }
    }

    /// SIM-файл модели с предпочтением купе; nil для транспортных машин.
    public func simName(forModel model: String) -> String? {
        let sims = entries.filter { $0.model.lowercased() == model.lowercased() && !$0.sim.isEmpty }.map(\.sim)
        return sims.first { $0.lowercased().contains("coupe") } ?? sims.first
    }
}

/// Поиск SIM-файла в Simulation/CarData без учёта регистра.
public func findSimFile(_ name: String, in dir: URL) -> URL? {
    let files = (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []
    return files.first { $0.lowercased() == name.lowercased() + ".sim" }.map { dir.appendingPathComponent($0) }
}
