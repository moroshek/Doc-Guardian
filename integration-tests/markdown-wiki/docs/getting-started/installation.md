# Installation Guide

This guide walks you through installing DataFlow on your system.

**Last Updated:** 2025-01-10

## Prerequisites

Before installing DataFlow, ensure you have:
- Python 3.9 or later
- Rust 1.70+ (for native extensions)
- Docker (optional, for containerized deployment)
- 4GB RAM minimum (8GB recommended)

## Installation Methods

### Method 1: pip install (Recommended)

```bash
pip install dataflow
```

This installs the Python API and CLI tools.

### Method 2: From Source

Clone the repository and build:

```bash
git clone https://github.com/dataflow/dataflow.git
cd dataflow
cargo build --release
pip install -e .
```

### Method 3: Docker

Pull the official image:

```bash
docker pull dataflow/dataflow:latest
docker run -p 8080:8080 dataflow/dataflow
```

## Verify Installation

Check that DataFlow is installed correctly:

```bash
dataflow --version
```

You should see output like:

```
DataFlow v2.4.1
```

## Next Steps

- [Quick Start Guide](quick-start.md) - Build your first pipeline
- [Configuration](configuration.md) - Configure the runtime
- [User Guide](../guides/user-guide.md) - Learn pipeline development

## Common Issues

### Python Version Error

If you see "Python 3.9+ required":
1. Check your Python version: `python --version`
2. Use a virtual environment with Python 3.9+
3. See [Troubleshooting Guide](../guides/troubleshooting.md)

### Rust Build Fails

If native extensions fail to compile:
1. Update Rust: `rustup update`
2. Install build tools: `apt-get install build-essential`
3. Use pre-built wheels: `pip install dataflow --only-binary :all:`

## Platform-Specific Notes

### Linux
Most distributions work out of the box. For Ubuntu/Debian:
```bash
sudo apt-get install python3-dev libssl-dev
pip install dataflow
```

### macOS
Install via Homebrew:
```bash
brew install python rust
pip install dataflow
```

### Windows
Use WSL2 for best experience:
```bash
wsl --install
# Then follow Linux instructions
```

## Need Help?

- Check the [Troubleshooting Guide](../guides/troubleshooting.md)
- Ask on [Discord](https://discord.gg/dataflow)
- File an issue on [GitHub](https://github.com/dataflow/dataflow/issues)
