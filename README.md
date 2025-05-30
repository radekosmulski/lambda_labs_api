# Lambda Labs API Client

A Python client and command-line tool for managing GPU instances on Lambda Labs Cloud. This package provides an easy way to list, launch, and monitor GPU instances with automatic retry capabilities for high-demand resources.

## Features

- 📋 **List running instances** - View all your active instances with details
- 🖥️ **List instance types** - See all available GPU types (including unavailable ones)
- 🚀 **Launch instances** - Start new GPU instances with a single command
- 🔄 **Automatic retry** - Keep trying to launch instances until they become available
- 🔍 **Smart filtering** - Filter instance types by GPU model or availability status
- 💰 **Cost tracking** - See hourly pricing for all instance types
- 🛑 **Terminate instances** - Stop instances individually or all at once

## Installation

### From PyPI (Recommended)

```bash
pip install lambda-labs-client
```

### From Source

```bash
git clone https://github.com/radekosmulski/lambda_labs_api.git
cd lambda_labs_api
pip install .
```

### Development Installation

```bash
git clone https://github.com/radekosmulski/lambda_labs_api.git
cd lambda_labs_api
pip install -e .[dev]
```

## Authentication

You need a Lambda Labs API key to use this client. Get one from the [Lambda Labs API keys page](https://cloud.lambda.ai/api-keys).

### Setting up your API key

You can provide your API key in two ways:

#### Option 1: Environment Variable (Recommended)
```bash
export LAMBDA_API_KEY="your-api-key-here"
```

Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent.

#### Option 2: Command Line Argument
```bash
python lambda_labs_client.py --api-key "your-api-key-here" --list-instances
```

## Usage

### Basic Commands

#### List Running Instances
```bash
# Using environment variable
lambda-labs --list-instances

# Using API key argument
lambda-labs --api-key "your-key" --list-instances
```

#### List All Instance Types
```bash
# Show all instance types (available and unavailable)
lambda-labs --list-types

# Show only available instances
lambda-labs --list-types --show available

# Show only unavailable instances
lambda-labs --list-types --show unavailable

# Filter by GPU type
lambda-labs --list-types --filter-type a100
lambda-labs --list-types --filter-type h100
```

#### Launch an Instance
```bash
# Basic launch (will fail if unavailable)
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key"

# Launch with custom name
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key" --name "ML-Training"

# Launch in specific region
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key" --region us-east-1

# Launch multiple instances
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key" --quantity 2
```

### Auto-Retry Feature

The killer feature: automatically retry launching instances until they become available!

```bash
# Keep trying every 5 seconds until successful
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key" --wait

# Retry with custom interval (every 10 seconds)
lambda-labs --launch gpu_8x_h100 --ssh-key "my-ssh-key" --wait --retry-interval 10

# Retry with maximum attempts
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key" --wait --max-retries 100

# Retry for specific region
lambda-labs --launch gpu_1x_a100 --ssh-key "my-ssh-key" --region us-west-1 --wait
```

Press `Ctrl+C` anytime to cancel the retry loop.

### Terminating Instances

```bash
# Terminate specific instances by ID
lambda-labs --terminate 0920582c7ff041399e34823a0be62549

# Terminate multiple instances
lambda-labs --terminate instance-id-1 instance-id-2 instance-id-3

# Terminate ALL running instances
lambda-labs --terminate all

# Skip confirmation prompt (use with caution!)
lambda-labs --terminate all --force
```

## Common Workflows

### 1. Check What's Available and Launch

```bash
# First, see what's available
lambda-labs --list-types --show available

# Then launch an available instance
lambda-labs --launch gpu_1x_a100 --ssh-key "my-key"
```

### 2. Wait for High-Demand GPUs

```bash
# Set up a retry for an H100 instance
lambda-labs --launch gpu_8x_h100 --ssh-key "my-key" --wait --retry-interval 30
```

### 3. Monitor Your Instances

```bash
# Check your running instances
lambda-labs --list-instances
```

### 4. Launch in Preferred Region

```bash
# Try to launch in us-east-1, but fall back to any available region
lambda-labs --launch gpu_1x_a100 --ssh-key "my-key" --region us-east-1 --wait
```

## SSH Key Management

Before launching instances, you need to have SSH keys configured in your Lambda Labs account. 

To see your available SSH keys:
```bash
lambda-labs --launch gpu_1x_a100
# (without specifying --ssh-key, it will list available keys)
```

## Python API Usage

You can also use the client programmatically:

```python
from lambda_labs_client import LambdaLabsClient

# Initialize client
client = LambdaLabsClient(api_key="your-api-key")

# List instances
instances = client.list_instances()
print(f"Found {len(instances)} running instances")

# Get instance types
instance_types = client.get_instance_types()
print(f"Available instance types: {len(instance_types)}")

# Launch an instance
instance_ids = client.launch_instance(
    region_name="us-west-1",
    instance_type_name="gpu_1x_a100",
    ssh_key_names=["my-ssh-key"],
    name="My Instance"
)
print(f"Launched instances: {instance_ids}")

# Terminate a specific instance
terminated = client.terminate_instance("instance-id-here")

# Terminate multiple instances
terminated = client.terminate_instances(["id1", "id2", "id3"])

# Terminate all running instances
terminated = client.terminate_all_instances()
print(f"Terminated {len(terminated)} instances")
```

## Instance Type Examples

Common instance types you can launch:
- `gpu_1x_a10` - 1x A10 (24 GB)
- `gpu_1x_a100` - 1x A100 (40 GB)
- `gpu_8x_a100` - 8x A100 (40 GB)
- `gpu_1x_h100` - 1x H100 (80 GB)
- `gpu_8x_h100` - 8x H100 (80 GB)

## Output Examples

### Listing Instances
```
================================================================================
                               RUNNING INSTANCES                                
================================================================================

Instance: ML-Training (ID: 0920582c7ff041399e34823a0be62549)
  Status: active
  Type: 1x A100 (40 GB SXM4)
  Region: California, USA (us-west-1)
  Public IP: 198.51.100.2
  Private IP: 10.0.2.100
  SSH Keys: my-ssh-key
  Jupyter URL: https://jupyter-url.lambdaspaces.com/?token=...
  Cost: $1.29/hour
```

### Auto-Retry Output
```
Starting launch attempts for 'gpu_1x_a100'...
Retry interval: 5 seconds
Max retries: unlimited
Press Ctrl+C to cancel

[14:23:45] Attempt #1 (elapsed: 0s)
  ❌ No availability in any region
  ⏳ Waiting 5 seconds before next attempt...

[14:23:50] Attempt #2 (elapsed: 5s)
  ❌ No availability in any region
  ⏳ Waiting 5 seconds before next attempt...

[14:23:55] Attempt #3 (elapsed: 10s)
  ✅ Instance available in region 'us-west-1'! Launching...

🎉 Successfully launched 1 instance(s):
  - 0920582c7ff041399e34823a0be62549

Total wait time: 0m 10s
```

## Tips

1. **High-Demand GPUs**: H100 and A100 instances are often fully booked. Use `--wait` to automatically grab one when it becomes available.

2. **Overnight Launches**: Set up a retry before going to bed:
   ```bash
   lambda-labs --launch gpu_8x_h100 --ssh-key "my-key" --wait --retry-interval 60
   ```

3. **Cost Awareness**: Always check the hourly cost shown in `--list-types` before launching.

4. **Region Selection**: Some regions have better availability. If you don't need a specific region, don't specify `--region` to allow the tool to pick any available region.

## Error Handling

The client provides clear error messages:
- **Invalid API Key**: Check your API key or create a new one
- **No SSH Keys**: Add SSH keys to your Lambda Labs account first
- **Instance Type Not Found**: Use `--list-types` to see valid instance names
- **No Availability**: Use `--wait` to keep retrying

## License

[Your chosen license]

## Contributing

[Your contribution guidelines]

## Support

For issues with the Lambda Labs API itself, contact Lambda Labs support.
For issues with this client, please open a GitHub issue.