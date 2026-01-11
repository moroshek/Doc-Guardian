# CLI Reference

Command-line interface reference for DataFlow.

**Last Updated:** 2025-01-09

## Installation

The `dataflow` CLI is installed with the package:

```bash
pip install dataflow
```

Verify installation:
```bash
dataflow --version
```

## Global Options

Available for all commands:

```bash
dataflow [OPTIONS] COMMAND [ARGS]
```

**Options:**
- `--config PATH` - Config file path (default: ./dataflow.yaml)
- `--profile NAME` - Config profile to use
- `--verbose` - Enable verbose output
- `--quiet` - Suppress non-error output
- `--help` - Show help message

## Commands

### run

Run a pipeline.

```bash
dataflow run [OPTIONS] PIPELINE_FILE
```

**Options:**
- `-c, --config PATH` - Config file
- `-p, --profile NAME` - Config profile
- `--checkpoint PATH` - Resume from checkpoint
- `--dry-run` - Validate without executing
- `--debug` - Enable debug mode

**Examples:**
```bash
# Basic run
dataflow run my_pipeline.py

# With config
dataflow run --config prod.yaml my_pipeline.py

# With profile
dataflow run --profile prod my_pipeline.py

# Debug mode
dataflow run --debug my_pipeline.py
```

### start

Start a pipeline as background service.

```bash
dataflow start [OPTIONS] PIPELINE_FILE
```

**Options:**
- `--name NAME` - Pipeline name (default: filename)
- `--config PATH` - Config file
- `--detach` - Run in background

**Example:**
```bash
dataflow start --name my-service my_pipeline.py
```

### stop

Stop a running pipeline.

```bash
dataflow stop PIPELINE_NAME
```

**Options:**
- `--timeout SECONDS` - Graceful shutdown timeout (default: 30)
- `--force` - Force stop without graceful shutdown

**Examples:**
```bash
# Graceful stop
dataflow stop my-service

# Force stop
dataflow stop --force my-service
```

### status

Show pipeline status.

```bash
dataflow status [PIPELINE_NAME]
```

**Options:**
- `--json` - Output in JSON format
- `--watch` - Watch mode (updates every 2s)

**Examples:**
```bash
# All pipelines
dataflow status

# Specific pipeline
dataflow status my-service

# JSON output
dataflow status --json my-service

# Watch mode
dataflow status --watch
```

### list

List all pipelines.

```bash
dataflow list [OPTIONS]
```

**Options:**
- `--status STATUS` - Filter by status (running, stopped, failed)
- `--json` - Output in JSON format

**Example:**
```bash
# All pipelines
dataflow list

# Only running
dataflow list --status running
```

### logs

View pipeline logs.

```bash
dataflow logs [OPTIONS] PIPELINE_NAME
```

**Options:**
- `-f, --follow` - Follow log output
- `-n, --tail N` - Show last N lines (default: 100)
- `--level LEVEL` - Filter by level (debug, info, warn, error)
- `--since DURATION` - Show logs since duration (e.g., 1h, 30m)

**Examples:**
```bash
# Last 100 lines
dataflow logs my-service

# Last 500 lines
dataflow logs --tail 500 my-service

# Follow logs
dataflow logs --follow my-service

# Only errors
dataflow logs --level error my-service

# Last hour
dataflow logs --since 1h my-service
```

### metrics

Show pipeline metrics.

```bash
dataflow metrics [OPTIONS] [PIPELINE_NAME]
```

**Options:**
- `--format FORMAT` - Output format (table, json, prometheus)
- `--summary` - Show summary only

**Examples:**
```bash
# All metrics
dataflow metrics

# Specific pipeline
dataflow metrics my-service

# JSON format
dataflow metrics --format json

# Summary only
dataflow metrics --summary
```

### config

Manage configuration.

#### validate

Validate configuration file:

```bash
dataflow config validate [CONFIG_FILE]
```

**Example:**
```bash
dataflow config validate dataflow.yaml
```

#### show

Display configuration:

```bash
dataflow config show [OPTIONS]
```

**Options:**
- `--profile NAME` - Show specific profile
- `--format FORMAT` - Output format (yaml, json)

**Example:**
```bash
dataflow config show --profile prod
```

#### set

Set configuration value:

```bash
dataflow config set KEY VALUE
```

**Example:**
```bash
dataflow config set runtime.workers 16
```

### checkpoint

Manage checkpoints.

#### list

List checkpoints:

```bash
dataflow checkpoint list PIPELINE_NAME
```

**Example:**
```bash
dataflow checkpoint list my-service
```

#### restore

Restore from checkpoint:

```bash
dataflow checkpoint restore PIPELINE_NAME CHECKPOINT_ID
```

**Example:**
```bash
dataflow checkpoint restore my-service checkpoint-123
```

#### delete

Delete checkpoint:

```bash
dataflow checkpoint delete PIPELINE_NAME CHECKPOINT_ID
```

**Example:**
```bash
dataflow checkpoint delete my-service checkpoint-123
```

### state

Manage pipeline state.

#### export

Export pipeline state:

```bash
dataflow state export [OPTIONS] PIPELINE_NAME
```

**Options:**
- `-o, --output FILE` - Output file (default: stdout)
- `--format FORMAT` - Format (json, binary)

**Example:**
```bash
dataflow state export --output state.json my-service
```

#### import

Import pipeline state:

```bash
dataflow state import [OPTIONS] PIPELINE_NAME
```

**Options:**
- `-i, --input FILE` - Input file
- `--overwrite` - Overwrite existing state

**Example:**
```bash
dataflow state import --input state.json my-service
```

#### clear

Clear pipeline state:

```bash
dataflow state clear PIPELINE_NAME
```

**Options:**
- `--confirm` - Skip confirmation prompt

**Example:**
```bash
dataflow state clear --confirm my-service
```

### debug

Debug utilities.

#### heap-dump

Generate heap dump:

```bash
dataflow debug heap-dump [OPTIONS]
```

**Options:**
- `-o, --output FILE` - Output file
- `--live` - Only dump live objects

**Example:**
```bash
dataflow debug heap-dump --output heap.hprof
```

#### profile

Profile pipeline:

```bash
dataflow debug profile [OPTIONS] PIPELINE_NAME
```

**Options:**
- `--duration SECONDS` - Profile duration (default: 60)
- `--output FILE` - Output file
- `--format FORMAT` - Format (flamegraph, json)

**Example:**
```bash
dataflow debug profile --duration 30 --format flamegraph my-service
```

#### bundle

Create debug bundle:

```bash
dataflow debug bundle [OPTIONS]
```

**Options:**
- `-o, --output FILE` - Output file (default: debug.tar.gz)

**Example:**
```bash
dataflow debug bundle --output debug-$(date +%Y%m%d).tar.gz
```

### version

Show version information:

```bash
dataflow version
```

**Options:**
- `--short` - Show version number only
- `--full` - Show all build info

**Examples:**
```bash
# Standard
dataflow version

# Short
dataflow version --short

# Full details
dataflow version --full
```

### info

Show system information:

```bash
dataflow info
```

Displays:
- DataFlow version
- Python version
- OS information
- Resource limits
- Configuration path

### health

Check system health:

```bash
dataflow health [OPTIONS]
```

**Options:**
- `--json` - JSON output
- `--wait` - Wait for healthy status

**Examples:**
```bash
# Quick check
dataflow health

# JSON output
dataflow health --json

# Wait for healthy
dataflow health --wait
```

## Environment Variables

Configure via environment variables:

```bash
# Config file
export DATAFLOW_CONFIG=/etc/dataflow/config.yaml

# Profile
export DATAFLOW_PROFILE=prod

# Log level
export DATAFLOW_LOG_LEVEL=debug

# Workers
export DATAFLOW_WORKERS=16

# Memory
export DATAFLOW_MEMORY=32GB
```

## Exit Codes

Standard exit codes:

- `0` - Success
- `1` - General error
- `2` - Invalid arguments
- `3` - Configuration error
- `4` - Pipeline error
- `5` - Connection error
- `130` - Interrupted (Ctrl+C)

## Shell Completion

Enable shell completion:

### Bash
```bash
eval "$(dataflow completion bash)"
```

### Zsh
```bash
eval "$(dataflow completion zsh)"
```

### Fish
```bash
dataflow completion fish | source
```

**Install permanently:**
```bash
# Bash
dataflow completion bash > /etc/bash_completion.d/dataflow

# Zsh
dataflow completion zsh > ~/.zsh/completion/_dataflow

# Fish
dataflow completion fish > ~/.config/fish/completions/dataflow.fish
```

## Examples

### Development Workflow

```bash
# Validate config
dataflow config validate dataflow.yaml

# Test pipeline locally
dataflow run --dry-run my_pipeline.py

# Run with debug
dataflow run --debug my_pipeline.py

# View logs
dataflow logs --follow my-service
```

### Production Deployment

```bash
# Start service
dataflow start --name prod-pipeline --profile prod pipeline.py

# Monitor status
dataflow status --watch prod-pipeline

# View metrics
dataflow metrics prod-pipeline

# Check logs for errors
dataflow logs --level error prod-pipeline
```

### Troubleshooting

```bash
# Check health
dataflow health

# Generate debug bundle
dataflow debug bundle

# Profile performance
dataflow debug profile --duration 60 my-service

# Export state
dataflow state export --output state-backup.json my-service
```

## Tips

1. **Use profiles** for different environments
2. **Enable completion** for faster typing
3. **Watch status** during deployment
4. **Follow logs** for debugging
5. **Create debug bundles** when reporting issues

## See Also

- [API Reference](api.md) - Python API
- [Configuration Reference](config.md) - Config options
- [User Guide](../guides/user-guide.md) - Usage patterns
- [Admin Guide](../guides/admin-guide.md) - Operations
