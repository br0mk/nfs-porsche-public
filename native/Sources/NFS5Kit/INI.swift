/// Читатель текстовых файлов игры в формате, похожем на INI (.tpg, .clr).
public typealias INI = [String: [String: String]]

public func parseINI(_ bytes: [UInt8]) -> INI {
    var out: INI = [:]
    var section: String?
    let text = String(decoding: bytes, as: UTF8.self)
    for raw in text.split(whereSeparator: { $0.isNewline }) {  // Пара «\r\n» представляет один Character.
        let line = raw.trimmingCharacters(in: .whitespaces)
        if line.isEmpty || line.hasPrefix(";") { continue }
        if line.hasPrefix("[") && line.hasSuffix("]") {
            section = String(line.dropFirst().dropLast())
            if out[section!] == nil { out[section!] = [:] }
        } else if let s = section, let eq = line.firstIndex(of: "=") {
            out[s]![line[..<eq].trimmingCharacters(in: .whitespaces)] =
                line[line.index(after: eq)...].trimmingCharacters(in: .whitespaces)
        }
    }
    return out
}

import Foundation
