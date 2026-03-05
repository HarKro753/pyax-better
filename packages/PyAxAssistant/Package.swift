// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "PyAxAssistant",
    platforms: [
        .macOS(.v15)
    ],
    targets: [
        .executableTarget(
            name: "PyAxAssistant",
            path: "Sources/PyAxAssistant"
        ),
        .testTarget(
            name: "PyAxAssistantTests",
            dependencies: ["PyAxAssistant"]
        ),
    ]
)
