#!/usr/bin/env python3
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
import json
import argparse
import time
import signal
from typing import Optional, List, Dict, Any
import requests
from datetime import datetime


class LambdaLabsClient:
    """Client for interacting with Lambda Labs API."""
    
    def __init__(self, api_key: str):
        """Initialize the client with an API key."""
        self.api_key = api_key
        self.base_url = "https://cloud.lambda.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an API request and handle errors."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = response.json()
            except:
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
    
    def launch_instance(self, 
                       region_name: str,
                       instance_type_name: str,
                       ssh_key_names: List[str],
                       name: Optional[str] = None,
                       file_system_names: Optional[List[str]] = None,
                       quantity: int = 1) -> List[str]:
        """Launch new instances."""
        data = {
            "region_name": region_name,
            "instance_type_name": instance_type_name,
            "ssh_key_names": ssh_key_names,
            "quantity": quantity
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
    
    def check_instance_availability_silent(self, instance_type_name: str, 
                                         preferred_region: Optional[str] = None) -> Optional[str]:
        """Silently check if an instance type is available and return the best region."""
        try:
            instance_types = self.get_instance_types()
            
            if instance_type_name not in instance_types:
                return None
            
            type_info = instance_types[instance_type_name]
            available_regions = type_info['regions_with_capacity_available']
            
            if not available_regions:
                return None
            
            # If preferred region is specified and available
            if preferred_region:
                for region in available_regions:
                    if region['name'] == preferred_region:
                        return preferred_region
            
            # Return first available region
            return available_regions[0]['name']
        except:
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
        
        if instance.get('jupyter_url'):
            print(f"  Jupyter URL: {instance['jupyter_url']}")
        
        # Show pricing
        price_cents = instance['instance_type']['price_cents_per_hour']
        price_dollars = price_cents / 100
        print(f"  Cost: ${price_dollars:.2f}/hour")


def print_instance_types(instance_types: Dict[str, Any], filter_type: Optional[str] = None, 
                        availability_filter: Optional[str] = None) -> None:
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
        
        instance_type = type_info['instance_type']
        regions = type_info['regions_with_capacity_available']
        
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
        
        specs = instance_type['specs']
        print(f"  Specs: {specs['gpus']} GPUs, {specs['vcpus']} vCPUs, "
              f"{specs['memory_gib']} GiB RAM, {specs['storage_gib']} GiB Storage")
        
        price_cents = instance_type['price_cents_per_hour']
        price_dollars = price_cents / 100
        print(f"  Cost: ${price_dollars:.2f}/hour")
        
        if is_available:
            print(f"  Status: ✅ AVAILABLE in {len(regions)} region(s)")
            print(f"  Regions: {', '.join([r['name'] for r in regions])}")
        else:
            print(f"  Status: ❌ UNAVAILABLE (no capacity in any region)")
    
    print(f"\n{'='*80}")
    
    total_count = available_count + unavailable_count
    if availability_filter is None:
        print(f"Summary: {available_count}/{total_count} instance types have available capacity")
    else:
        print(f"Showing: {shown_count} instance type(s)")
        print(f"Total: {available_count} available, {unavailable_count} unavailable")
    
    print(f"{'='*80}")


def check_instance_availability(instance_types: Dict[str, Any], 
                               desired_type: str,
                               preferred_region: Optional[str] = None) -> Optional[str]:
    """Check if a specific instance type is available and return the best region."""
    if desired_type not in instance_types:
        print(f"Instance type '{desired_type}' not found.")
        return None
    
    type_info = instance_types[desired_type]
    available_regions = type_info['regions_with_capacity_available']
    
    if not available_regions:
        print(f"Instance type '{desired_type}' is not available in any region.")
        return None
    
    # If preferred region is specified and available
    if preferred_region:
        for region in available_regions:
            if region['name'] == preferred_region:
                return preferred_region
    
    # Return first available region
    return available_regions[0]['name']


def launch_instance_with_retry(client: LambdaLabsClient, 
                              instance_type: str,
                              ssh_key: str,
                              preferred_region: Optional[str] = None,
                              name: Optional[str] = None,
                              quantity: int = 1,
                              retry_interval: int = 5,
                              max_retries: Optional[int] = None) -> List[str]:
    """Launch an instance with retry logic until successful."""
    attempt = 0
    start_time = time.time()
    
    # Set up signal handler for graceful exit
    def signal_handler(sig, frame):
        print("\n\nCancelled by user.")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"Starting launch attempts for '{instance_type}'...")
    print(f"Retry interval: {retry_interval} seconds")
    print(f"Max retries: {'unlimited' if max_retries is None else max_retries}")
    print("Press Ctrl+C to cancel\n")
    
    while True:
        attempt += 1
        elapsed = int(time.time() - start_time)
        elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempt #{attempt} (elapsed: {elapsed_str})")
        
        # Check availability
        region = client.check_instance_availability_silent(instance_type, preferred_region)
        
        if region:
            print(f"  ✅ Instance available in region '{region}'! Launching...")
            try:
                instance_ids = client.launch_instance(
                    region_name=region,
                    instance_type_name=instance_type,
                    ssh_key_names=[ssh_key],
                    name=name,
                    quantity=quantity
                )
                
                print(f"\n🎉 Successfully launched {len(instance_ids)} instance(s):")
                for instance_id in instance_ids:
                    print(f"  - {instance_id}")
                
                total_time = int(time.time() - start_time)
                print(f"\nTotal wait time: {total_time//60}m {total_time%60}s")
                return instance_ids
                
            except Exception as e:
                print(f"  ❌ Launch failed: {e}")
                # Continue retrying even if launch fails
        else:
            # Try to get more info about availability
            try:
                instance_types = client.get_instance_types()
                if instance_type in instance_types:
                    print(f"  ❌ No availability in any region")
                else:
                    print(f"  ❌ Instance type '{instance_type}' not found")
                    return []
            except:
                print(f"  ❌ Unable to check availability")
        
        # Check if we've hit max retries
        if max_retries is not None and attempt >= max_retries:
            print(f"\n❌ Maximum retries ({max_retries}) reached. Giving up.")
            return []
        
        # Wait before next attempt
        print(f"  ⏳ Waiting {retry_interval} seconds before next attempt...")
        time.sleep(retry_interval)


def main():
    parser = argparse.ArgumentParser(description="Lambda Labs API Client")
    parser.add_argument("--api-key", help="Lambda Labs API key (or set LAMBDA_API_KEY env var)")
    parser.add_argument("--list-instances", action="store_true", help="List running instances")
    parser.add_argument("--list-types", action="store_true", help="List all instance types")
    parser.add_argument("--filter-type", help="Filter instance types by name (e.g., 'a100', 'h100')")
    parser.add_argument("--show", choices=["all", "available", "unavailable"], default="all",
                       help="Show all, only available, or only unavailable instance types")
    parser.add_argument("--launch", help="Launch an instance of the specified type")
    parser.add_argument("--region", help="Preferred region for launching")
    parser.add_argument("--ssh-key", help="SSH key name to use for launch")
    parser.add_argument("--name", help="Name for the new instance")
    parser.add_argument("--quantity", type=int, default=1, help="Number of instances to launch")
    parser.add_argument("--wait", action="store_true", 
                       help="Keep retrying if instance is unavailable")
    parser.add_argument("--retry-interval", type=int, default=5, 
                       help="Seconds between retry attempts (default: 5)")
    parser.add_argument("--max-retries", type=int, 
                       help="Maximum number of retries (default: unlimited)")
    
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key or os.environ.get("LAMBDA_API_KEY")
    if not api_key:
        print("Error: API key not provided. Use --api-key or set LAMBDA_API_KEY environment variable.")
        sys.exit(1)
    
    # Initialize client
    try:
        client = LambdaLabsClient(api_key)
    except Exception as e:
        print(f"Error initializing client: {e}")
        sys.exit(1)
    
    # Handle different operations
    try:
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
                    max_retries=args.max_retries
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
                print(f"\nLaunching {args.quantity} '{args.launch}' instance(s) in region '{region}'...")
                
                instance_ids = client.launch_instance(
                    region_name=region,
                    instance_type_name=args.launch,
                    ssh_key_names=[args.ssh_key],
                    name=args.name,
                    quantity=args.quantity
                )
                
                print(f"\nSuccessfully launched {len(instance_ids)} instance(s):")
                for instance_id in instance_ids:
                    print(f"  - {instance_id}")
                
                print("\nUse --list-instances to see the details once they're running.")
        
        # If no operation specified, show usage
        if not any([args.list_instances, args.list_types, args.launch]):
            parser.print_help()
    
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()