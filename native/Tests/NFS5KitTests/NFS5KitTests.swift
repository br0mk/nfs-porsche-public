import Foundation
import XCTest
@testable import NFS5Kit

final class NFS5KitTests: XCTestCase {
    let carDir = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .deletingLastPathComponent().appendingPathComponent("work/selected-disc-joliet/GameData/CarModel")

    func testRefPackLiteralAndCopy() throws {
        // Заголовок 10 FB, размер 000008; литералы «ABCD», копия длины 3 с расстояния 4, конец с «E».
        let stream: [UInt8] = [0x10, 0xFB, 0x00, 0x00, 0x08, 0xE0, 0x41, 0x42, 0x43, 0x44, 0x00, 0x03, 0xFD, 0x45]
        XCTAssertEqual(try RefPack.decompress(stream), Array("ABCDABCE".utf8))
    }

    func test356Model() throws {
        try XCTSkipUnless(FileManager.default.fileExists(atPath: carDir.path), "game data not extracted")
        let car = try CarModel(dir: carDir, name: "356_1")
        XCTAssertEqual(car.crp.articles.count, 115)
        XCTAssertEqual(car.pages.count, 11)
        // Эталон Python (nfs5.export): 2898 видимых треугольников LOD-1 после удаления перекрытий.
        XCTAssertEqual(car.batches().reduce(0) { $0 + $1.positions.count / 3 }, 2898)
    }

    func testAlpsTrack() throws {
        let trackDir = carDir.deletingLastPathComponent().appendingPathComponent("Track")
        try XCTSkipUnless(FileManager.default.fileExists(atPath: trackDir.path), "game data not extracted")
        let track = try Track(dir: trackDir, name: "alps")
        XCTAssertEqual(track.crp.articles.count, 1752)
        // Эталон Python (nfs5.track): 62194 треугольника LOD-0 в 184 группах.
        let batches = track.batches()
        XCTAssertEqual(batches.reduce(0) { $0 + $1.positions.count / 3 }, 62194)
        XCTAssertEqual(batches.count, 184)
        XCTAssertEqual(track.road().count, 1795)
    }
}
