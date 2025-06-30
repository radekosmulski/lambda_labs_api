"""
Lambda Labs API Client
A Python script to interact with Lambda Labs Cloud API for managing GPU instances.

Features:
- List running instances
- List all instance types (available and unavailable)
- Launch instances
- Automatic retry when instances are unavailable
"""

import os
import sys
import argparse
import time
import signal
import threading
from typing import Optional, List, Dict, Any
import requests
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich import print as rprint
from rich.live import Live
import questionary

console = Console()


class LambdaLabsClient:
    """Client for interacting with Lambda Labs API."""

    def __init__(self, api_key: str):
        """Initialize the client with an API key."""
        self.api_key = api_key
        self.base_url = "https://cloud.lambda.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an API request and handle errors."""
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(method=method, url=url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = response.json()
            except Exception:
                pass

            if error_data.get("error"):
                error = error_data["error"]
                print(f"API Error: {error.get('message', 'Unknown error')}")
                if error.get("suggestion"):
                    print(f"Suggestion: {error['suggestion']}")
            else:
                print(f"HTTP Error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            raise

    def list_instances(self) -> List[Dict[str, Any]]:
        """List all running instances."""
        response = self._make_request("GET", "/instances")
        return response.get("data", [])

    def get_instance_types(self) -> Dict[str, Any]:
        """Get available instance types with regional availability."""
        response = self._make_request("GET", "/instance-types")
        return response.get("data", {})

    def launch_instance(
        self,
        region_name: str,
        instance_type_name: str,
        ssh_key_names: List[str],
        name: Optional[str] = None,
        file_system_names: Optional[List[str]] = None,
        quantity: int = 1,
    ) -> List[str]:
        """Launch new instances."""
        data = {
            "region_name": region_name,
            "instance_type_name": instance_type_name,
            "ssh_key_names": ssh_key_names,
            "quantity": quantity,
        }

        if name:
            data["name"] = name

        if file_system_names:
            data["file_system_names"] = file_system_names
        else:
            data["file_system_names"] = []

        response = self._make_request("POST", "/instance-operations/launch", data)
        return response.get("data", {}).get("instance_ids", [])

    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        """List available SSH keys."""
        response = self._make_request("GET", "/ssh-keys")
        return response.get("data", [])

    def terminate_instance(self, instance_id: str) -> Dict[str, Any]:
        """Terminate a single instance by ID."""
        data = {"instance_ids": [instance_id]}
        response = self._make_request("POST", "/instance-operations/terminate", data)
        terminated = response.get("data", {}).get("terminated_instances", [])
        if terminated:
            return terminated[0]
        return {}

    def terminate_instances(self, instance_ids: List[str]) -> List[Dict[str, Any]]:
        """Terminate multiple instances by IDs."""
        data = {"instance_ids": instance_ids}
        response = self._make_request("POST", "/instance-operations/terminate", data)
        return response.get("data", {}).get("terminated_instances", [])

    def terminate_all_instances(self) -> List[Dict[str, Any]]:
        """Terminate all running instances."""
        # First get all running instances
        instances = self.list_instances()
        if not instances:
            return []

        # Extract instance IDs
        instance_ids = [instance["id"] for instance in instances]

        # Terminate them all
        return self.terminate_instances(instance_ids)

    def check_instance_availability_silent(
        self, instance_type_name: str, preferred_region: Optional[str] = None
    ) -> Optional[str]:
        """Silently check if an instance type is available and return the best region."""
        try:
            instance_types = self.get_instance_types()

            if instance_type_name not in instance_types:
                return None

            type_info = instance_types[instance_type_name]
            available_regions = type_info["regions_with_capacity_available"]

            if not available_regions:
                return None

            # If preferred region is specified and available
            if preferred_region:
                for region in available_regions:
                    if region["name"] == preferred_region:
                        return preferred_region

            # Return first available region
            return available_regions[0]["name"]
        except Exception:
            return None


def print_instances(instances: List[Dict[str, Any]]) -> None:
    """Pretty print instance information."""
    if not instances:
        print("No running instances found.")
        return

    print(f"\n{'='*80}")
    print(f"{'RUNNING INSTANCES':^80}")
    print(f"{'='*80}")

    for instance in instances:
        print(f"\nInstance: {instance.get('name', 'Unnamed')} (ID: {instance['id']})")
        print(f"  Status: {instance['status']}")
        print(f"  Type: {instance['instance_type']['description']}")
        print(f"  Region: {instance['region']['description']} ({instance['region']['name']})")
        print(f"  Public IP: {instance.get('ip', 'N/A')}")
        print(f"  Private IP: {instance.get('private_ip', 'N/A')}")
        print(f"  SSH Keys: {', '.join(instance.get('ssh_key_names', []))}")

        if instance.get("jupyter_url"):
            print(f"  Jupyter URL: {instance['jupyter_url']}")

        # Show pricing
        price_cents = instance["instance_type"]["price_cents_per_hour"]
        price_dollars = price_cents / 100
        print(f"  Cost: ${price_dollars:.2f}/hour")


def print_instance_types(
    instance_types: Dict[str, Any],
    filter_type: Optional[str] = None,
    availability_filter: Optional[str] = None,
) -> None:
    """Pretty print instance types with optional filtering."""
    print(f"\n{'='*80}")

    if availability_filter == "available":
        print(f"{'AVAILABLE INSTANCE TYPES':^80}")
    elif availability_filter == "unavailable":
        print(f"{'UNAVAILABLE INSTANCE TYPES':^80}")
    else:
        print(f"{'ALL INSTANCE TYPES':^80}")

    print(f"{'='*80}")

    available_count = 0
    unavailable_count = 0
    shown_count = 0

    for type_name, type_info in instance_types.items():
        if filter_type and filter_type.lower() not in type_name.lower():
            continue

        instance_type = type_info["instance_type"]
        regions = type_info["regions_with_capacity_available"]

        is_available = bool(regions)

        if is_available:
            available_count += 1
        else:
            unavailable_count += 1

        # Apply availability filter
        if availability_filter == "available" and not is_available:
            continue
        elif availability_filter == "unavailable" and is_available:
            continue

        shown_count += 1

        print(f"\n{instance_type['name']}:")
        print(f"  Description: {instance_type['description']}")
        print(f"  GPU: {instance_type['gpu_description']}")

        specs = instance_type["specs"]
        print(
            f"  Specs: {specs['gpus']} GPUs, {specs['vcpus']} vCPUs, "
            f"{specs['memory_gib']} GiB RAM, {specs['storage_gib']} GiB Storage"
        )

        price_cents = instance_type["price_cents_per_hour"]
        price_dollars = price_cents / 100
        print(f"  Cost: ${price_dollars:.2f}/hour")

        if is_available:
            print(f"  Status: ✅ AVAILABLE in {len(regions)} region(s)")
            print(f"  Regions: {', '.join([r['name'] for r in regions])}")
        else:
            print("  Status: ❌ UNAVAILABLE (no capacity in any region)")

    print(f"\n{'='*80}")

    total_count = available_count + unavailable_count
    if availability_filter is None:
        print(f"Summary: {available_count}/{total_count} instance types have available capacity")
    else:
        print(f"Showing: {shown_count} instance type(s)")
        print(f"Total: {available_count} available, {unavailable_count} unavailable")

    print(f"{'='*80}")


def check_instance_availability(
    instance_types: Dict[str, Any], desired_type: str, preferred_region: Optional[str] = None
) -> Optional[str]:
    """Check if a specific instance type is available and return the best region."""
    if desired_type not in instance_types:
        console.print(f"[red]Instance type '{desired_type}' not found.[/red]")
        return None

    type_info = instance_types[desired_type]
    available_regions = type_info["regions_with_capacity_available"]

    if not available_regions:
        console.print(f"[red]Instance type '{desired_type}' is not available in any region.[/red]")
        return None

    # If preferred region is specified and available
    if preferred_region:
        for region in available_regions:
            if region["name"] == preferred_region:
                return preferred_region

    # Return first available region
    return available_regions[0]["name"]


def launch_instance_with_retry(
    client: LambdaLabsClient,
    instance_type: str,
    ssh_key: str,
    preferred_region: Optional[str] = None,
    name: Optional[str] = None,
    quantity: int = 1,
    retry_interval: int = 5,
    max_retries: Optional[int] = None,
) -> List[str]:
    """Launch an instance with retry logic until successful."""
    attempt = 0
    start_time = time.time()

    # Set up signal handler for graceful exit
    def signal_handler(sig: int, frame: Any) -> None:
        console.print("\n\n[yellow]Cancelled by user.[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    console.print(f"\n[bold]Starting launch attempts for '{instance_type}'...[/bold]")
    console.print(f"Retry interval: [cyan]{retry_interval}[/cyan] seconds")
    console.print(f"Max retries: [cyan]{'unlimited' if max_retries is None else max_retries}[/cyan]")
    console.print("[dim]Press Ctrl+C to cancel[/dim]\n")

    while True:
        attempt += 1
        elapsed = int(time.time() - start_time)
        elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"

        timestamp = datetime.now().strftime('%H:%M:%S')
        console.print(f"[cyan]{timestamp}[/cyan] Attempt [bold]#{attempt}[/bold] (elapsed: {elapsed_str})")

        # Check availability with a spinner
        with console.status("Checking availability...", spinner="dots"):
            region = client.check_instance_availability_silent(instance_type, preferred_region)

        if region:
            console.print(f"  [green]✓[/green] Instance available in region '[bold]{region}[/bold]'!")
            try:
                instance_ids = client.launch_instance(
                    region_name=region,
                    instance_type_name=instance_type,
                    ssh_key_names=[ssh_key],
                    name=name,
                    quantity=quantity,
                )

                console.print(f"\n[green bold]✨ Successfully launched {len(instance_ids)} instance(s):[/green bold]")
                for instance_id in instance_ids:
                    console.print(f"  [green]•[/green] {instance_id}")

                total_time = int(time.time() - start_time)
                console.print(f"\n[dim]Total wait time: {total_time//60}m {total_time%60}s[/dim]")
                return instance_ids

            except Exception as e:
                console.print(f"  [red]✗[/red] Launch failed: {e}")
                # Continue retrying even if launch fails
        else:
            # Try to get more info about availability
            try:
                instance_types = client.get_instance_types()
                if instance_type in instance_types:
                    console.print("  [red]✗[/red] No availability in any region")
                else:
                    console.print(f"  [red]✗[/red] Instance type '{instance_type}' not found")
                    return []
            except Exception:
                console.print("  [red]✗[/red] Unable to check availability")

        # Check if we've hit max retries
        if max_retries is not None and attempt >= max_retries:
            console.print(f"\n[red]Maximum retries ({max_retries}) reached. Giving up.[/red]")
            return []

        # Wait before next attempt with a progress bar
        console.print(f"  [yellow]⏱[/yellow] Waiting {retry_interval} seconds...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Next attempt in...", total=retry_interval)
            for i in range(retry_interval):
                time.sleep(1)
                progress.update(task, advance=1, description=f"Next attempt in {retry_interval - i - 1}s")


def format_instance_choice(instance_type: str, instance_data: Dict[str, Any], for_display: bool = False) -> str:
    """Format instance type data for the selector display."""
    info = instance_data["instance_type"]
    specs = info["specs"]
    
    # Extract GPU memory from description (e.g., "H100 (80 GB SXM5)" -> "80 GB")
    gpu_desc = info.get("gpu_description", "")
    
    # Format pricing
    price_cents = info.get("price_cents_per_hour", 0)
    price_dollars = price_cents / 100
    
    # Format availability
    regions = instance_data.get("regions_with_capacity_available", [])
    is_available = bool(regions)
    
    if is_available:
        availability = f" ✓ Available ({len(regions)})"
    else:
        availability = " ✗ Unavailable"
    
    # Build the display string with fixed-width columns for alignment
    # Format components to match header widths exactly
    cpu_str = f"{specs.get('vcpus', 0)} vCPUs"
    ram_str = f"{specs.get('memory_gib', 0)} GB RAM"
    gpu_str = f"{specs.get('gpus', 0)}x {gpu_desc}"
    storage_str = f"{specs.get('storage_gib', 0)} GB SSD"
    price_str = f"${price_dollars:.2f}/hr"
    
    formatted = (
        f"{instance_type:<25} │ "
        f"{cpu_str:>10} │ "
        f"{ram_str:>12} │ "
        f"{gpu_str:<24} │ "
        f"{storage_str:>13} │ "
        f"{price_str:>11} │ "
        f"{availability:>15}"
    )
    
    return formatted


def select_instance_type(client: LambdaLabsClient, show_unavailable: bool = False) -> Optional[tuple[str, bool]]:
    """Interactive instance type selector with toggle support."""
    console.print("\n[bold]Fetching available instance types...[/bold]")
    
    with console.status("Loading instance types...", spinner="dots"):
        instance_types = client.get_instance_types()
    
    while True:
        # Filter and sort instances
        choices = []
        unavailable_count = 0
        available_count = 0
        
        # First, collect all instances with their availability status
        instances_list = []
        for instance_type, data in instance_types.items():
            has_capacity = bool(data.get("regions_with_capacity_available", []))
            
            if has_capacity:
                available_count += 1
            else:
                unavailable_count += 1
            
            if show_unavailable or has_capacity:
                instances_list.append((instance_type, data, has_capacity))
        
        # Sort instances: available first (sorted by name), then unavailable (sorted by name)
        instances_list.sort(key=lambda x: (not x[2], x[0]))
        
        # Format and add to choices, tracking availability
        availability_map = {}
        for instance_type, data, has_capacity in instances_list:
            formatted = format_instance_choice(instance_type, data, for_display=True)
            choices.append(questionary.Choice(title=formatted, value=instance_type))
            availability_map[instance_type] = has_capacity
        
        if not choices:
            console.print("[red]No instances found.[/red]")
            return None, False
        
        # Clear screen for cleaner display
        console.clear()
        
        # Add header
        console.print("[bold]Select an instance type:[/bold]")
        if show_unavailable:
            console.print(f"[dim]Showing all instances ({available_count} available, {unavailable_count} unavailable)[/dim]")
        else:
            console.print(f"[dim]Showing only available instances ({available_count} of {available_count + unavailable_count} total)[/dim]")
        console.print("[dim]Use arrow keys to navigate, Enter to select, Ctrl+C to cancel[/dim]")
        console.print("")
        
        # Display column headers
        headers = (
            f"   {'Instance Type':<25} │ "
            f"{'CPUs':>10} │ "
            f"{'RAM':>12} │ "
            f"{'GPU':<24} │ "
            f"{'Storage':>13} │ "
            f"{'Price':>11} │ "
            f"{'Status':>15}"
        )
        console.print(f"[bold cyan]{headers}[/bold cyan]")
        console.print("─" * 134)
        
        # Add toggle option at the end
        if not show_unavailable and unavailable_count > 0:
            choices.append(questionary.Choice(
                title=f"\n{'─' * 134}\n{'':>28}  → Show {unavailable_count} unavailable instance{'s' if unavailable_count != 1 else ''} ←",
                value="__TOGGLE__"
            ))
        elif show_unavailable:
            choices.append(questionary.Choice(
                title=f"\n{'─' * 134}\n{'':>28}  → Hide unavailable instances ←",
                value="__TOGGLE__"
            ))
        
        # Use questionary for selection
        try:
            selected = questionary.select(
                "",
                choices=choices,
                instruction=" ",
                qmark="",
                style=questionary.Style([
                    ('selected', 'bg:#0489D1 fg:#ffffff bold'),
                    ('pointer', 'fg:#0489D1 bold'),
                    ('highlighted', 'fg:#0489D1 bold'),
                    ('question', ''),
                ])
            ).ask()
            
            if selected == "__TOGGLE__":
                show_unavailable = not show_unavailable
                continue
            else:
                # Return instance type and whether it's available
                is_available = availability_map.get(selected, False)
                return selected, is_available
            
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Selection cancelled.[/yellow]")
            return None, False


def handle_launch(args: argparse.Namespace, client: LambdaLabsClient) -> None:
    """Handle the launch subcommand."""
    # If no instance type provided, show interactive selector
    if not args.instance_type:
        result = select_instance_type(client, show_unavailable=args.show_all)
        if not result or not result[0]:
            sys.exit(1)
        instance_type, is_available = result
        args.instance_type = instance_type
        console.print(f"\n[green]Selected:[/green] {instance_type}")
        
        # If instance is not available, automatically enable wait mode
        if not is_available:
            console.print("[yellow]Instance is not currently available. Enabling auto-retry mode...[/yellow]\n")
            args.wait = True
        else:
            console.print("")
    
    # Check if SSH key is provided
    ssh_keys = client.list_ssh_keys()
    
    if not args.ssh_key:
        if not ssh_keys:
            console.print("[red]Error:[/red] No SSH keys found in your account.")
            console.print("Please add an SSH key at: https://cloud.lambdaai.co/ssh-keys")
            sys.exit(1)
        elif len(ssh_keys) == 1:
            # Automatically use the only SSH key
            ssh_key = ssh_keys[0]['name']
            console.print(f"[dim]Using SSH key: {ssh_key}[/dim]")
        else:
            # Multiple keys - prompt for selection
            console.print("\n[yellow]Available SSH keys:[/yellow]")
            for idx, key in enumerate(ssh_keys, 1):
                console.print(f"  {idx}. {key['name']}")
            
            choice = Prompt.ask("\nSelect SSH key (number)")
            try:
                ssh_key = ssh_keys[int(choice) - 1]['name']
            except (ValueError, IndexError):
                console.print("[red]Invalid selection[/red]")
                sys.exit(1)
    else:
        ssh_key = args.ssh_key
        if ssh_key not in [k['name'] for k in ssh_keys]:
            console.print(f"[red]Error:[/red] SSH key '{ssh_key}' not found")
            console.print("\nAvailable SSH keys:")
            for key in ssh_keys:
                console.print(f"  - {key['name']}")
            sys.exit(1)
    
    if args.wait:
        # Use retry logic with rich progress
        instance_ids = launch_instance_with_retry(
            client=client,
            instance_type=args.instance_type,
            ssh_key=ssh_key,
            preferred_region=args.region,
            name=args.name,
            quantity=args.quantity,
            retry_interval=args.retry_interval,
            max_retries=args.max_retries,
        )
        
        if instance_ids:
            console.print("\n[green]Success![/green] Use 'lambda-labs list' to see instance details.")
    else:
        # Single attempt launch
        with console.status(f"Checking availability for '{args.instance_type}'..."):
            instance_types = client.get_instance_types()
            region = check_instance_availability(instance_types, args.instance_type, args.region)
        
        if not region:
            console.print(f"\n[red]'{args.instance_type}' is not available in any region.[/red]")
            console.print("\n[dim]Tip: Use --wait to keep retrying until available[/dim]")
            sys.exit(1)
        
        # Launch instance
        console.print(f"\n[green]✓[/green] Launching {args.quantity} '{args.instance_type}' instance(s) in '{region}'...")
        
        try:
            instance_ids = client.launch_instance(
                region_name=region,
                instance_type_name=args.instance_type,
                ssh_key_names=[ssh_key],
                name=args.name,
                quantity=args.quantity,
            )
            
            console.print(f"\n[green]Successfully launched {len(instance_ids)} instance(s):[/green]")
            for instance_id in instance_ids:
                console.print(f"  • {instance_id}")
            
            console.print("\n[dim]Use 'lambda-labs list' to see instance details[/dim]")
        except Exception as e:
            console.print(f"\n[red]Failed to launch instance:[/red] {e}")
            sys.exit(1)


def handle_terminate_interactive(client: LambdaLabsClient, instances: List[Dict[str, Any]]) -> None:
    """Interactive instance termination handler."""
    console.print("\n[bold]Select instances to terminate:[/bold]")
    console.print("[dim]Use arrow keys to navigate, Enter to select, Ctrl+C to cancel[/dim]\n")
    
    # Create choices for each instance
    choices = []
    for instance in instances:
        name = instance.get('name', 'Unnamed')
        instance_type = instance['instance_type']['name']
        region = instance['region']['name']
        
        # Format the display string
        display = (
            f"{instance['id']:<20} │ "
            f"{instance_type:<25} │ "
            f"{name if name != 'Unnamed' else '[no name]':<20} │ "
            f"{region:<12}"
        )
        choices.append(questionary.Choice(title=display, value=instance['id']))
    
    # Add "terminate all" option if multiple instances
    if len(instances) > 1:
        choices.append(questionary.Choice(
            title=f"\n{'─' * 82}\n→ TERMINATE ALL {len(instances)} INSTANCES ←",
            value="__ALL__"
        ))
    
    # Show column headers
    headers = (
        f"{'Instance ID':<20} │ "
        f"{'Type':<25} │ "
        f"{'Name':<20} │ "
        f"{'Region':<12}"
    )
    console.print(f"[bold cyan]{headers}[/bold cyan]")
    console.print("─" * 82)
    
    try:
        selected = questionary.select(
            "",
            choices=choices,
            instruction=" ",
            qmark="",
            style=questionary.Style([
                ('selected', 'bg:#E74C3C fg:#ffffff bold'),
                ('pointer', 'fg:#E74C3C bold'),
                ('highlighted', 'fg:#E74C3C bold'),
                ('question', ''),
            ])
        ).ask()
        
        if selected is None:
            console.print("\n[yellow]Termination cancelled.[/yellow]")
            return
        
        # Determine what to terminate
        if selected == "__ALL__":
            to_terminate = instances
            console.print(f"\n[red bold]Warning: This will terminate ALL {len(instances)} instances![/red bold]")
        else:
            to_terminate = [inst for inst in instances if inst['id'] == selected]
            console.print(f"\n[red]Will terminate instance: {selected}[/red]")
        
        # Show instances to be terminated
        for instance in to_terminate:
            name = instance.get('name', 'Unnamed')
            console.print(f"  • {instance['id']} - {instance['instance_type']['name']} - {name}")
        
        # Confirm termination
        if not Confirm.ask("\nAre you sure you want to terminate?", default=False):
            console.print("[yellow]Termination cancelled.[/yellow]")
            return
        
        # Terminate instances
        console.print("\n[bold]Terminating instances...[/bold]")
        if selected == "__ALL__":
            terminated = client.terminate_all_instances()
        else:
            terminated = client.terminate_instances([selected])
        
        if terminated:
            console.print(f"\n[green]Successfully terminated {len(terminated)} instance(s):[/green]")
            for instance in terminated:
                console.print(f"  ✓ {instance['id']}")
        else:
            console.print("[red]No instances were terminated.[/red]")
            
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Termination cancelled.[/yellow]")
        return


def manage_ssh_config(action: str, instance: Optional[Dict[str, Any]] = None, host_alias: Optional[str] = None) -> bool:
    """Manage SSH config entries for Lambda Labs instances."""
    ssh_config_path = Path.home() / ".ssh" / "config"
    
    # Create .ssh directory if it doesn't exist
    ssh_dir = ssh_config_path.parent
    if not ssh_dir.exists():
        ssh_dir.mkdir(mode=0o700)
    
    # Read existing config
    if ssh_config_path.exists():
        with open(ssh_config_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    if action == "add" and instance:
        # Get instance IP
        ip_address = instance.get('ip', '')
        if not ip_address:
            console.print("[red]Error: Instance has no IP address[/red]")
            return False
        
        # Use provided alias or generate one
        if not host_alias:
            host_alias = f"lambda-{instance['id'][:8]}"
        
        # Check if entry already exists
        for i, line in enumerate(lines):
            if line.strip() == f"Host {host_alias}":
                console.print(f"[yellow]SSH config entry '{host_alias}' already exists[/yellow]")
                return False
        
        # Add new entry
        entry = [
            f"\n# Lambda Labs instance {instance['id']}\n",
            f"Host {host_alias}\n",
            f"    HostName {ip_address}\n",
            f"    User ubuntu\n",
            f"    ForwardAgent yes\n",
            f"    StrictHostKeyChecking no\n",
            f"    UserKnownHostsFile /dev/null\n"
        ]
        
        lines.extend(entry)
        
        # Write back
        with open(ssh_config_path, 'w') as f:
            f.writelines(lines)
        
        # Ensure proper permissions
        ssh_config_path.chmod(0o600)
        
        console.print(f"[green]✓ Added SSH config entry '{host_alias}'[/green]")
        console.print(f"[dim]Config file: {ssh_config_path.expanduser()}[/dim]")
        console.print(f"[dim]You can now connect with: ssh {host_alias}[/dim]")
        return True
    
    elif action == "remove":
        # Find and remove Lambda Labs entries
        new_lines = []
        i = 0
        removed_count = 0
        
        while i < len(lines):
            # Check if this is a Lambda Labs entry
            if i > 0 and "Lambda Labs instance" in lines[i-1] and lines[i].strip().startswith("Host "):
                # Skip the comment line
                if i > 0 and lines[i-1].strip().startswith("#"):
                    i -= 1
                
                # Skip until next Host or end
                while i < len(lines) and not (lines[i].strip().startswith("Host ") and "Lambda Labs" not in lines[max(0, i-1)]):
                    i += 1
                removed_count += 1
            else:
                new_lines.append(lines[i])
                i += 1
        
        if removed_count > 0:
            # Write back
            with open(ssh_config_path, 'w') as f:
                f.writelines(new_lines)
            
            console.print(f"[green]✓ Removed {removed_count} Lambda Labs SSH config entries[/green]")
            return True
        else:
            console.print("[yellow]No Lambda Labs SSH config entries found[/yellow]")
            return False
    
    return False


def handle_ssh_config_interactive(client: LambdaLabsClient) -> None:
    """Interactive SSH config management."""
    choices = [
        questionary.Choice("Add SSH config for running instances", value="add"),
        questionary.Choice("Remove all Lambda Labs SSH configs", value="remove"),
        questionary.Choice("Back to main menu", value="back"),
    ]
    
    action = questionary.select(
        "SSH Config Management:",
        choices=choices,
        instruction=" ",
        qmark="",
        style=questionary.Style([
            ('selected', 'bg:#0489D1 fg:#ffffff bold'),
            ('pointer', 'fg:#0489D1 bold'),
            ('highlighted', 'fg:#0489D1 bold'),
            ('question', 'fg:#ffffff bold'),
        ])
    ).ask()
    
    if action == "back" or action is None:
        return
    
    if action == "add":
        # Get running instances
        instances = client.list_instances()
        if not instances:
            console.print("\n[yellow]No running instances to add SSH config for[/yellow]")
            return
        
        # Show instances to choose from
        console.print("\n[bold]Select instance to add SSH config:[/bold]\n")
        
        choices = []
        for instance in instances:
            name = instance.get('name', 'Unnamed')
            instance_type = instance['instance_type']['name']
            ip = instance.get('ip', 'No IP')
            
            display = f"{instance['id'][:16]}...  •  {instance_type:<25}  •  {name:<20}  •  {ip}"
            choices.append(questionary.Choice(title=display, value=instance))
        
        selected_instance = questionary.select(
            "",
            choices=choices,
            instruction=" ",
            qmark="",
        ).ask()
        
        if selected_instance:
            # Ask for custom alias
            alias = Prompt.ask(
                "\nEnter SSH alias (or press Enter for auto-generated)",
                default=f"lambda-{selected_instance['id'][:8]}"
            )
            
            manage_ssh_config("add", selected_instance, alias)
    
    elif action == "remove":
        if Confirm.ask("\nRemove all Lambda Labs SSH config entries?", default=False):
            manage_ssh_config("remove")


def show_main_menu(client: LambdaLabsClient) -> None:
    """Show interactive main menu with instance list."""
    console.clear()
    console.print("[bold]Lambda Labs Instance Manager[/bold]\n")
    
    # Show running instances
    try:
        instances = client.list_instances()
        if instances:
            console.print("[dim]Running instances:[/dim]")
            for instance in instances:
                name = instance.get('name', 'Unnamed')
                instance_type = instance['instance_type']['name']
                region = instance['region']['name']
                status = instance.get('status', 'unknown')
                
                # Color code the status
                if status.lower() == 'active':
                    status_display = f"[green]● {status}[/green]"
                elif status.lower() in ['booting', 'provisioning']:
                    status_display = f"[yellow]● {status}[/yellow]"
                elif status.lower() in ['terminated', 'terminating']:
                    status_display = f"[red]● {status}[/red]"
                else:
                    status_display = f"[dim]● {status}[/dim]"
                
                console.print(f"  ▸ [cyan]{instance['id']}[/cyan]  •  {instance_type:<25}  •  {name if name != 'Unnamed' else '[dim]no name[/dim]':<20}  •  {region:<12}  •  {status_display}")
            console.print("")
        else:
            console.print("[dim]No running instances[/dim]\n")
    except Exception:
        # If we can't fetch instances, just continue
        pass
    
    console.print("[dim]Select 'Refresh' to update instance status[/dim]\n")
    
    choices = [
        questionary.Choice("[Refresh]", value="refresh"),
        questionary.Choice("Launch a new instance", value="launch"),
        questionary.Choice("Terminate instances", value="terminate"),
        questionary.Choice("Manage SSH config", value="ssh_config"),
        questionary.Choice("Exit", value="exit"),
    ]
    
    action = questionary.select(
        "What would you like to do?",
        choices=choices,
        default="launch",  # Set default selection to "Launch a new instance"
        instruction=" ",
        qmark="",
        style=questionary.Style([
            ('selected', 'bg:#0489D1 fg:#ffffff bold'),
            ('pointer', 'fg:#0489D1 bold'),
            ('highlighted', 'fg:#0489D1 bold'),
            ('question', 'fg:#ffffff bold'),
        ])
    ).ask()
    
    if action == 'refresh':
        show_main_menu(client)
        return
    
    if action == "exit" or action is None:
        console.print("\n[dim]Goodbye![/dim]")
        sys.exit(0)
    
    # Create a namespace to simulate command line args
    from argparse import Namespace
    
    if action == "launch":
        args = Namespace(
            command="launch",
            instance_type=None,
            ssh_key=None,
            region=None,
            name=None,
            quantity=1,
            wait=False,
            retry_interval=5,
            max_retries=None,
            show_all=False
        )
        handle_launch(args, client)
    
    elif action == "terminate":
        instances = client.list_instances()
        if not instances:
            console.print("\n[yellow]No running instances to terminate.[/yellow]")
        else:
            handle_terminate_interactive(client, instances)
    
    elif action == "ssh_config":
        handle_ssh_config_interactive(client)
    
    # Ask if user wants to continue (default to Yes)
    console.print("\n")
    if Confirm.ask("Would you like to perform another action?", default=True):
        show_main_menu(client)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lambda Labs Instance Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  lambda-labs                            # Interactive main menu
  lambda-labs launch                     # Interactive instance selection
  lambda-labs launch gpu_1x_h100_pcie    # Launch specific instance type
  lambda-labs launch --wait              # Interactive selection with auto-retry
  lambda-labs list                       # List running instances
  lambda-labs terminate <instance-id>    # Terminate an instance
"""
    )
    
    # Global arguments
    parser.add_argument(
        "--api-key", 
        help="Lambda Labs API key (or set LAMBDA_API_KEY env var)"
    )
    
    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Launch command
    launch_parser = subparsers.add_parser(
        "launch", 
        help="Launch GPU instances",
        description="Launch one or more GPU instances"
    )
    launch_parser.add_argument(
        "instance_type",
        nargs="?",
        help="Instance type to launch (e.g., gpu_1x_h100_pcie). If not provided, shows interactive selector"
    )
    launch_parser.add_argument(
        "--ssh-key", 
        help="SSH key name (interactive selection if not provided)"
    )
    launch_parser.add_argument(
        "--region", 
        help="Preferred region for launching"
    )
    launch_parser.add_argument(
        "--name", 
        help="Name for the instance(s)"
    )
    launch_parser.add_argument(
        "--quantity", 
        type=int, 
        default=1, 
        help="Number of instances to launch (default: 1)"
    )
    launch_parser.add_argument(
        "--wait", 
        action="store_true", 
        help="Keep retrying if instance is unavailable"
    )
    launch_parser.add_argument(
        "--retry-interval", 
        type=int, 
        default=5, 
        help="Seconds between retry attempts (default: 5)"
    )
    launch_parser.add_argument(
        "--max-retries", 
        type=int, 
        help="Maximum number of retries (default: unlimited)"
    )
    launch_parser.add_argument(
        "--show-all", 
        action="store_true", 
        help="Show all instance types including unavailable ones in the selector"
    )

    # For now, keep the old commands working alongside the new ones
    # This is for backward compatibility
    parser.add_argument("--list-instances", action="store_true", help="(Deprecated) Use 'lambda-labs list' instead")
    parser.add_argument("--list-types", action="store_true", help="(Deprecated) Use 'lambda-labs list types' instead")
    parser.add_argument("--launch", help="(Deprecated) Use 'lambda-labs launch' instead")
    parser.add_argument("--terminate", nargs="*", help="(Deprecated) Use 'lambda-labs terminate' instead")
    parser.add_argument("--filter-type", help="Filter instance types by name")
    parser.add_argument("--show", choices=["all", "available", "unavailable"], default="all")
    parser.add_argument("--region", help="Preferred region")
    parser.add_argument("--ssh-key", help="SSH key name")
    parser.add_argument("--name", help="Instance name")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--retry-interval", type=int, default=5)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--force", action="store_true")
    
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key or os.environ.get("LAMBDA_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] API key not provided.")
        console.print("Use --api-key or set LAMBDA_API_KEY environment variable.")
        sys.exit(1)
    
    # Initialize client
    try:
        client = LambdaLabsClient(api_key)
    except Exception as e:
        console.print(f"[red]Error initializing client:[/red] {e}")
        sys.exit(1)

    # If no command provided, show interactive menu
    if not args.command and not any([args.launch, args.list_instances, args.list_types, args.terminate]):
        show_main_menu(client)
        return
    
    # Handle new subcommands
    if args.command == "launch":
        handle_launch(args, client)
        return
    
    # Handle legacy commands for backward compatibility
    try:
        if args.launch:
            console.print("[yellow]Note:[/yellow] --launch is deprecated. Use 'lambda-labs launch' instead.")
            # Convert to new format and handle
            args.instance_type = args.launch
            handle_launch(args, client)
            return
            
        if args.list_instances:
            instances = client.list_instances()
            print_instances(instances)

        if args.list_types:
            instance_types = client.get_instance_types()
            availability_filter = None if args.show == "all" else args.show
            print_instance_types(instance_types, args.filter_type, availability_filter)

        if args.launch:
            # Check SSH keys first
            if not args.ssh_key:
                print("\nAvailable SSH keys:")
                ssh_keys = client.list_ssh_keys()
                if not ssh_keys:
                    print("No SSH keys found. Please add an SSH key first.")
                    sys.exit(1)

                for key in ssh_keys:
                    print(f"  - {key['name']} (ID: {key['id']})")

                print("\nPlease specify an SSH key with --ssh-key")
                sys.exit(1)

            if args.wait:
                # Use retry logic
                instance_ids = launch_instance_with_retry(
                    client=client,
                    instance_type=args.launch,
                    ssh_key=args.ssh_key,
                    preferred_region=args.region,
                    name=args.name,
                    quantity=args.quantity,
                    retry_interval=args.retry_interval,
                    max_retries=args.max_retries,
                )

                if instance_ids:
                    print("\nUse --list-instances to see the details once they're running.")
            else:
                # Single attempt launch
                print(f"\nChecking availability for '{args.launch}'...")

                # Get available instance types
                instance_types = client.get_instance_types()

                # Check availability
                region = check_instance_availability(instance_types, args.launch, args.region)
                if not region:
                    print("\nTip: Use --wait to keep retrying until the instance becomes available")
                    sys.exit(1)

                # Launch instance
                print(
                    f"\nLaunching {args.quantity} '{args.launch}' instance(s) in region '{region}'..."
                )

                instance_ids = client.launch_instance(
                    region_name=region,
                    instance_type_name=args.launch,
                    ssh_key_names=[args.ssh_key],
                    name=args.name,
                    quantity=args.quantity,
                )

                print(f"\nSuccessfully launched {len(instance_ids)} instance(s):")
                for instance_id in instance_ids:
                    print(f"  - {instance_id}")

                print("\nUse --list-instances to see the details once they're running.")

        if args.terminate is not None:
            if not args.terminate:
                print("Error: Please specify instance IDs to terminate or use 'all'")
                print("Example: --terminate instance-id-1 instance-id-2")
                print("         --terminate all")
                sys.exit(1)

            # Check if terminating all instances
            if len(args.terminate) == 1 and args.terminate[0].lower() == "all":
                # Get all running instances
                instances = client.list_instances()
                if not instances:
                    print("No running instances to terminate.")
                    sys.exit(0)

                print(f"\n{'='*60}")
                print("INSTANCES TO TERMINATE:")
                print(f"{'='*60}")
                for instance in instances:
                    print(
                        f"{instance['id']}: {instance.get('name', 'Unnamed')} "
                        f"({instance['instance_type']['name']}, {instance['region']['name']})"
                    )
                print(f"{'='*60}")
                print(f"Total: {len(instances)} instance(s)")

                # Confirm termination
                if not args.force:
                    response = input(
                        "\nAre you sure you want to terminate ALL instances? (yes/no): "
                    )
                    if response.lower() != "yes":
                        print("Termination cancelled.")
                        sys.exit(0)

                # Terminate all instances
                print("\nTerminating all instances...")
                terminated = client.terminate_all_instances()

                if terminated:
                    print(f"\nSuccessfully terminated {len(terminated)} instance(s):")
                    for instance in terminated:
                        print(f"  - {instance['id']}")
                else:
                    print("No instances were terminated.")

            else:
                # Terminating specific instances
                instance_ids = args.terminate

                # Verify instances exist
                current_instances = client.list_instances()
                current_ids = {inst["id"] for inst in current_instances}

                invalid_ids = [id for id in instance_ids if id not in current_ids]
                if invalid_ids:
                    print("Error: The following instance IDs are not valid or not running:")
                    for id in invalid_ids:
                        print(f"  - {id}")
                    sys.exit(1)

                # Show instances to be terminated
                print(f"\n{'='*60}")
                print("INSTANCES TO TERMINATE:")
                print(f"{'='*60}")
                for inst in current_instances:
                    if inst["id"] in instance_ids:
                        print(
                            f"{inst['id']}: {inst.get('name', 'Unnamed')} "
                            f"({inst['instance_type']['name']}, {inst['region']['name']})"
                        )
                print(f"{'='*60}")

                # Confirm termination
                if not args.force:
                    response = input(
                        f"\nAre you sure you want to terminate {len(instance_ids)} instance(s)? (yes/no): "
                    )
                    if response.lower() != "yes":
                        print("Termination cancelled.")
                        sys.exit(0)

                # Terminate instances
                print("\nTerminating instances...")
                terminated = client.terminate_instances(instance_ids)

                if terminated:
                    print(f"\nSuccessfully terminated {len(terminated)} instance(s):")
                    for instance in terminated:
                        print(f"  - {instance['id']}")
                else:
                    print("No instances were terminated.")

        # If no operation specified, show usage
        if not any([args.list_instances, args.list_types, args.launch, args.terminate is not None]):
            parser.print_help()

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
