# Lambda Labs API Client

A modern Python client and CLI for managing GPU instances on Lambda Labs Cloud. Features an interactive interface with Rich terminal UI for seamless instance management.

## ✨ Features

- 🎨 **Interactive CLI** - Beautiful terminal UI with arrow-key navigation
- 📋 **Instance Management** - List, launch, and terminate GPU instances
- 🔄 **Auto-Retry** - Automatically retry launching unavailable instances
- 🖥️ **SSH Config Management** - Add instances to ~/.ssh/config for easy access
- 🎯 **Smart Selection** - Interactive instance type selector with hardware details
- 💰 **Cost Tracking** - See hourly pricing for all instance types
- 🔍 **Status Display** - Color-coded instance statuses (active, booting, etc.)

## 📦 Installation

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

## 🔑 Authentication

Get your API key from the [Lambda Labs API keys page](https://cloud.lambda.ai/api-keys).

### Setting up your API key

```bash
export LAMBDA_API_KEY="your-api-key-here"
```

Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent.

## 🚀 Quick Start

### Interactive Mode (Recommended)

Simply run without any arguments to enter the interactive interface:

```bash
lambda-labs
```

This opens an interactive menu where you can:
- View running instances with live status
- Launch new instances with guided selection
- Terminate instances
- Manage SSH configurations
- Refresh instance status

### Command Line Mode

You can also use direct commands:

```bash
# List running instances
lambda-labs list

# Launch an instance (interactive selection)
lambda-labs launch

# Launch a specific instance type
lambda-labs launch gpu_1x_a100 --ssh-key my-key

# Terminate instances
lambda-labs terminate <instance-id>
```

## 📖 Detailed Usage

### Interactive Features

#### Main Menu
```
Lambda Labs Instance Manager

Running instances:
  ▸ 1117df1d3dd949a0a8b0abdccd35eb7e  •  gpu_1x_a10  •  ML-Training  •  us-east-1  •  ● active

Select 'Refresh' to update instance status

What would you like to do?
 » Launch a new instance
   Terminate instances
   Manage SSH config
   Exit
```

#### Instance Selection
When launching, you'll see an interactive selector with detailed hardware specs:

```
Select an instance type:
──────────────────────────────────────────────────────────────────────
   Instance Type         GPU            CPUs    RAM      SSD      Price
──────────────────────────────────────────────────────────────────────
 » gpu_1x_a10           1x A10 (24 GB)   30    200 GB   512 GB   $0.75/hr
   gpu_1x_a100_sxm4     1x A100 (40 GB)  30    200 GB   512 GB   $1.29/hr
   gpu_8x_a100_80gb     8x A100 (80 GB)  124   1800 GB  3500 GB  $34.00/hr
```

### Command Line Examples

#### Launch with Auto-Retry
```bash
# Keep trying until an instance becomes available
lambda-labs launch gpu_1x_a100 --wait

# With custom retry interval (every 30 seconds)
lambda-labs launch gpu_8x_h100 --wait --retry-interval 30

# With maximum retry attempts
lambda-labs launch gpu_1x_a100 --wait --max-retries 100
```

#### Launch Multiple Instances
```bash
lambda-labs launch gpu_1x_a100 --quantity 3 --ssh-key my-key
```

#### Region-Specific Launch
```bash
lambda-labs launch gpu_1x_a100 --region us-west-1 --ssh-key my-key
```

### SSH Config Management

The tool can automatically add launched instances to your `~/.ssh/config`:

```bash
# After launching, you'll be prompted to add to SSH config
# Or manage SSH configs from the main menu

# Then connect easily:
ssh lambda-instance-name
```

## 🐍 Python API Usage

Use the client programmatically in your Python scripts:

```python
from lambda_labs_client import LambdaLabsClient

# Initialize client
client = LambdaLabsClient(api_key="your-api-key")

# List instances
instances = client.list_instances()
for instance in instances:
    print(f"{instance['name']}: {instance['status']}")

# Launch an instance
instance_ids = client.launch_instance(
    region_name="us-west-1",
    instance_type_name="gpu_1x_a100",
    ssh_key_names=["my-ssh-key"],
    name="ML-Training"
)

# Terminate instances
client.terminate_instance("instance-id")
```

## 📊 Instance Types

Common GPU instances available:

| Type | GPUs | VRAM | Use Case |
|------|------|------|----------|
| `gpu_1x_a10` | 1x A10 | 24 GB | Development, light training |
| `gpu_1x_a100` | 1x A100 | 40 GB | Training, fine-tuning |
| `gpu_2x_a100` | 2x A100 | 80 GB | Distributed training |
| `gpu_4x_a100` | 4x A100 | 160 GB | Large model training |
| `gpu_8x_a100_80gb` | 8x A100 | 640 GB | Large scale training |
| `gpu_1x_h100_pcie` | 1x H100 | 80 GB | Latest generation training |
| `gpu_8x_h100_sxm5` | 8x H100 | 640 GB | Cutting-edge AI workloads |

## 💡 Tips & Tricks

1. **High-Demand GPUs**: H100s are often fully booked. Use the auto-retry feature:
   ```bash
   lambda-labs launch gpu_8x_h100_sxm5 --wait --retry-interval 60
   ```

2. **Overnight Launches**: Set up a long-running retry before bed:
   ```bash
   lambda-labs launch gpu_8x_a100_80gb --wait --max-retries 500
   ```

3. **SSH Convenience**: Always add instances to SSH config for easy access

4. **Cost Awareness**: Check prices in the instance selector before launching

5. **Refresh Status**: Use the Refresh option in the main menu to update instance statuses

## 🛠️ Development

### Setup Development Environment
```bash
git clone https://github.com/radekosmulski/lambda_labs_api.git
cd lambda_labs_api
pip install -e .[dev]
```

### Run Tests
```bash
pytest
```

### Code Formatting
```bash
black lambda_labs_client/ --line-length 100
flake8 lambda_labs_client/
mypy lambda_labs_client/
```

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 💬 Support

- For Lambda Labs API issues: Contact [Lambda Labs support](https://lambdalabs.com/support)
- For client issues: Open a [GitHub issue](https://github.com/radekosmulski/lambda_labs_api/issues)

## 🔧 Troubleshooting

### API Key Issues
```bash
# Check if API key is set
echo $LAMBDA_API_KEY

# Verify API key works
lambda-labs list
```

### SSH Key Issues
Make sure you have SSH keys configured in your Lambda Labs account before launching instances.

### Connection Issues
If you can't connect to an instance:
1. Check the instance status is "active"
2. Verify the SSH key is correct
3. Ensure your IP is not blocked by firewalls

---

Built with ❤️ using [Rich](https://github.com/Textualize/rich) and [questionary](https://github.com/tmbo/questionary)