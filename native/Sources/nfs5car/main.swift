import Foundation
import NFS5Kit

// Запуск: nfs5car <каталог CarModel> [имя ...]
// Запуск: nfs5car --tracks <каталог Track> [имя ...]
// Выводит число треугольников и позиционную контрольную сумму каждой машины
// для сравнения с эталонным читателем Python (scripts/parity.py).
let args = CommandLine.arguments
guard args.count >= 2 else {
    print("usage: nfs5car <CarModel dir> [name ...]")
    exit(2)
}
if args[1] == "--tracks" {
    let dir = URL(fileURLWithPath: args[2])
    let names = args.count > 3 ? Array(args[3...]) : Track.trackNames(in: dir)
    var bad = 0
    for name in names {
        do {
            let t = try Track(dir: dir, name: name)
            let batches = t.batches()
            let tris = batches.reduce(0) { $0 + $1.positions.count / 3 }
            var sum = 0.0, csum = 0.0
            for b in batches {
                for p in b.positions { sum += Double(p.x) + 2 * Double(p.y) + 3 * Double(p.z) }
                for c in b.colors { csum += Double(c.x) + 2 * Double(c.y) + 3 * Double(c.z) }
            }
            print("\(name) triangles=\(tris) batches=\(batches.count) checksum=\(String(format: "%.1f", sum)) " +
                  "colorsum=\(String(format: "%.1f", csum)) road=\(t.road().count)")
        } catch {
            bad += 1
            print("\(name) ERROR \(error)")
        }
    }
    exit(bad == 0 ? 0 : 1)
}
let dir = URL(fileURLWithPath: args[1])
let names = args.count > 2 ? Array(args[2...]) : CarModel.carNames(in: dir)
var failures = 0
for name in names {
    do {
        let car = try CarModel(dir: dir, name: name)
        let batches = car.batches()
        let tris = batches.reduce(0) { $0 + $1.positions.count / 3 }
        var sum = 0.0
        for b in batches { for p in b.positions { sum += Double(p.x) + 2 * Double(p.y) + 3 * Double(p.z) } }
        var texsum = 0
        for (i, page) in car.pages { for (j, b) in page.rgba.enumerated() { texsum &+= Int(b) * ((j % 7) + i + 1) } }
        print("\(name) triangles=\(tris) pages=\(car.pages.count) checksum=\(String(format: "%.3f", sum)) texsum=\(texsum)")
    } catch {
        failures += 1
        print("\(name) ERROR \(error)")
    }
}
exit(failures == 0 ? 0 : 1)
