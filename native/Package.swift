// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "NFS5Native",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "NFS5Kit", targets: ["NFS5Kit"]),
        .executable(name: "nfs5car", targets: ["nfs5car"]),
    ],
    targets: [
        .target(name: "NFS5Kit"),
        .executableTarget(name: "nfs5car", dependencies: ["NFS5Kit"]),
        .testTarget(name: "NFS5KitTests", dependencies: ["NFS5Kit"]),
    ]
)
