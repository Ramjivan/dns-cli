
import os
import sys
import requests
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
CF_EMAIL = os.getenv("CF_EMAIL")
CF_API_KEY = os.getenv("CF_API_KEY")
CF_DOMAIN = os.getenv("CF_DOMAIN")

# --- Cloudflare API Setup ---
API_BASE_URL = "https://api.cloudflare.com/client/v4"
HEADERS = {
    "X-Auth-Email": CF_EMAIL,
    "X-Auth-Key": CF_API_KEY,
    "Content-Type": "application/json"
}

# --- Rich Console ---
console = Console()

def get_zone_id(domain):
    """Get the Zone ID for a given domain."""
    url = f"{API_BASE_URL}/zones?name={domain}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if data["result"]:
            return data["result"][0]["id"]
        else:
            console.print(f"[bold red]Error: Domain '{domain}' not found in your Cloudflare account.[/bold red]")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]API Request Error: {e}[/bold red]")
        sys.exit(1)

def get_dns_records(zone_id):
    """Get all DNS records for a given Zone ID."""
    url = f"{API_BASE_URL}/zones/{zone_id}/dns_records"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()["result"]
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]API Request Error: {e}[/bold red]")
        return []

def display_dns_records(records):
    """Display DNS records in a formatted table."""
    table = Table(title=f"DNS Records for {CF_DOMAIN}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Name", style="green")
    table.add_column("Content", style="yellow")
    table.add_column("TTL", style="blue")
    table.add_column("Priority", style="yellow")
    table.add_column("Proxy", style="red")

    for record in records:
        table.add_row(
            record["id"],
            record["type"],
            record["name"],
            record["content"],
            str(record["ttl"]),
            str(record.get("priority", "N/A")),
            "On" if record["proxied"] else "Off"
        )
    console.print(table)

def add_dns_record(zone_id):
    """Add a new DNS record."""
    console.print("\n[bold]Add a new DNS Record[/bold]")
    record_type = console.input("Enter record type (A, AAAA, CNAME, TXT, etc.): ").upper()
    name = console.input(f"Enter name (e.g., 'subdomain' for subdomain.{CF_DOMAIN}): ")
    content = console.input("Enter content (e.g., IP address or another domain): ")
    ttl_str = console.input("Enter TTL (in seconds, 1 for auto): ")
    ttl = int(ttl_str) if ttl_str else 1
    
    data = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl,
    }

    if record_type == 'MX':
        priority = int(console.input("Enter priority: "))
        data["priority"] = priority
    
    proxied_input = console.input("Enable Cloudflare proxy? (yes/no): ").lower()
    proxied = proxied_input == 'yes'
    data["proxied"] = proxied

    url = f"{API_BASE_URL}/zones/{zone_id}/dns_records"
    try:
        response = requests.post(url, headers=HEADERS, json=data)
        response.raise_for_status()
        console.print("\n[bold green]Successfully added DNS record.[/bold green]")
    except requests.exceptions.RequestException as e:
        error_message = e.response.json()["errors"][0]["message"]
        console.print(f"[bold red]Error adding DNS record: {error_message}[/bold red]")


def update_dns_record(zone_id, records):
    """Update an existing DNS record."""
    display_dns_records(records)
    record_id = console.input("\nEnter the ID of the record to update: ")

    # Find the record to pre-fill information
    record_to_update = next((r for r in records if r['id'] == record_id), None)
    if not record_to_update:
        console.print("[bold red]Record ID not found.[/bold red]")
        return

    console.print("\n[bold]Update DNS Record[/bold] (press Enter to keep current value)")

    record_type = console.input(f"Enter new type ({record_to_update['type']}): ") or record_to_update['type']
    name = console.input(f"Enter new name ({record_to_update['name']}): ") or record_to_update['name']
    content = console.input(f"Enter new content ({record_to_update['content']}): ") or record_to_update['content']
    ttl_str = console.input(f"Enter new TTL ({record_to_update['ttl']}): ")
    ttl = int(ttl_str) if ttl_str else record_to_update['ttl']
    
    data = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl,
    }

    if record_type == 'MX':
        default_priority = record_to_update.get('priority', '')
        priority_str = console.input(f"Enter new priority ({default_priority}): ")
        if priority_str:
            data["priority"] = int(priority_str)
        elif default_priority:
            data["priority"] = default_priority

    proxied_input = console.input(f"Enable Cloudflare proxy? ({'yes' if record_to_update['proxied'] else 'no'}): ").lower()
    proxied = (proxied_input == 'yes') if proxied_input else record_to_update['proxied']
    data["proxied"] = proxied


    url = f"{API_BASE_URL}/zones/{zone_id}/dns_records/{record_id}"
    try:
        response = requests.put(url, headers=HEADERS, json=data)
        response.raise_for_status()
        console.print("\n[bold green]Successfully updated DNS record.[/bold green]")
    except requests.exceptions.RequestException as e:
        error_message = e.response.json()["errors"][0]["message"]
        console.print(f"[bold red]Error updating DNS record: {error_message}[/bold red]")

def delete_dns_record(zone_id, records):
    """Delete a DNS record."""
    display_dns_records(records)
    record_id = console.input("\nEnter the ID of the record to delete: ")

    if not any(r['id'] == record_id for r in records):
        console.print("[bold red]Record ID not found.[/bold red]")
        return

    confirmation = console.input(f"Are you sure you want to delete record {record_id}? (yes/no): ").lower()
    if confirmation == 'yes':
        url = f"{API_BASE_URL}/zones/{zone_id}/dns_records/{record_id}"
        try:
            response = requests.delete(url, headers=HEADERS)
            response.raise_for_status()
            console.print("\n[bold green]Successfully deleted DNS record.[/bold green]")
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error deleting DNS record: {e}[/bold red]")
    else:
        console.print("Deletion cancelled.")

def main():
    """Main function to run the CLI tool."""
    if not all([CF_EMAIL, CF_API_KEY, CF_DOMAIN]):
        console.print("[bold red]Error: Missing credentials. Make sure CF_EMAIL, CF_API_KEY, and CF_DOMAIN are set in your .env file.[/bold red]")
        sys.exit(1)

    zone_id = get_zone_id(CF_DOMAIN)
    
    while True:
        console.print("\n[bold cyan]Cloudflare DNS Manager[/bold cyan]")
        console.print("1. List DNS Records")
        console.print("2. Add DNS Record")
        console.print("3. Update DNS Record")
        console.print("4. Delete DNS Record")
        console.print("5. Exit")
        choice = console.input("Enter your choice: ")

        if choice == '1':
            records = get_dns_records(zone_id)
            if records:
                display_dns_records(records)
        elif choice == '2':
            add_dns_record(zone_id)
        elif choice == '3':
            records = get_dns_records(zone_id)
            if records:
                update_dns_record(zone_id, records)
        elif choice == '4':
            records = get_dns_records(zone_id)
            if records:
                delete_dns_record(zone_id, records)
        elif choice == '5':
            console.print("Exiting.")
            break
        else:
            console.print("[bold red]Invalid choice. Please try again.[/bold red]")

if __name__ == "__main__":
    main()
