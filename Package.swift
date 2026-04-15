// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "IZoneDesktop",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(
            name: "IZoneDesktop",
            targets: ["IZoneDesktop"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "IZoneDesktop",
            path: ".",
            exclude: [
                ".codex",
                "__pycache__",
                "docs",
                "dist",
                "script",
                ".build",
                "README.md",
                "LICENSE",
                ".gitignore",
                "izone",
                "izone_mcp_server.py",
            ]
        ),
    ]
)
