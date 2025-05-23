# Lambda Labs API Client

A Python command-line tool for managing GPU instances on Lambda Labs Cloud. This client provides an easy way to list, launch, and monitor GPU instances with automatic retry capabilities for high-demand resources.

## Features

- 📋 **List running instances** - View all your active instances with details
- 🖥️ **List instance types** - See all available GPU types (including unavailable ones)
- 🚀 **Launch instances** - Start new GPU instances with a single command
- 🔄 **Automatic retry** - Keep trying to launch instances until they become available
- 🔍 **Smart filtering** - Filter instance types by GPU model or availability status
- 💰 **Cost tracking** - See hourly pricing for all instance types

## Installation

### Requirements

- Python 3.6+
- `requests` library

### Setup

1. Clone this repository:
```bash
git clone <your-repo-url>
cd lambda-labs-client
```

2. Install dependencies:
```bash
pip install requests
```

3. Make the script executable (optional):
```bash
chmod +x lambda_labs_client.py
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
python lambda_labs_client.py --list-instances

# Using API key argument
python lambda_labs_client.py --api-key "your-key" --list-instances
```

#### List All Instance Types
```bash
# Show all instance types (available and unavailable)
python lambda_labs_client.py --list-types

# Show only available instances
python lambda_labs_client.py --list-types --show available

# Show only unavailable instances
python lambda_labs_client.py --list-types --show unavailable

# Filter by GPU type
python lambda_labs_client.py --list-types --filter-type a100
python lambda_labs_client.py --list-types --filter-type h100
```

#### Launch an Instance
```bash
# Basic launch (will fail if unavailable)
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key"

# Launch with custom name
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key" --name "ML-Training"

# Launch in specific region
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key" --region us-east-1

# Launch multiple instances
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key" --quantity 2
```

### Auto-Retry Feature

The killer feature: automatically retry launching instances until they become available!

```bash
# Keep trying every 5 seconds until successful
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key" --wait

# Retry with custom interval (every 10 seconds)
python lambda_labs_client.py --launch gpu_8x_h100 --ssh-key "my-ssh-key" --wait --retry-interval 10

# Retry with maximum attempts
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key" --wait --max-retries 100

# Retry for specific region
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-ssh-key" --region us-west-1 --wait
```

Press `Ctrl+C` anytime to cancel the retry loop.

## Common Workflows

### 1. Check What's Available and Launch

```bash
# First, see what's available
python lambda_labs_client.py --list-types --show available

# Then launch an available instance
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-key"
```

### 2. Wait for High-Demand GPUs

```bash
# Set up a retry for an H100 instance
python lambda_labs_client.py --launch gpu_8x_h100 --ssh-key "my-key" --wait --retry-interval 30
```

### 3. Monitor Your Instances

```bash
# Check your running instances
python lambda_labs_client.py --list-instances
```

### 4. Launch in Preferred Region

```bash
# Try to launch in us-east-1, but fall back to any available region
python lambda_labs_client.py --launch gpu_1x_a100 --ssh-key "my-key" --region us-east-1 --wait
```

## SSH Key Management

Before launching instances, you need to have SSH keys configured in your Lambda Labs account. 

To see your available SSH keys:
```bash
python lambda_labs_client.py --launch gpu_1x_a100
# (without specifying --ssh-key, it will list available keys)
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
   python lambda_labs_client.py --launch gpu_8x_h100 --ssh-key "my-key" --wait --retry-interval 60
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