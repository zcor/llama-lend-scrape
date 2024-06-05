import json
from collections import defaultdict
from ape import Contract
from datetime import datetime
import pandas as pd

def recursive_defaultdict():
    return defaultdict(recursive_defaultdict)

filename = 'data/debug_events_2024-06-05_09-12-17.json'
CONTRACT_ADDRESSES = {
    "wsteth": "0x100daa78fc509db39ef7d04de0c1abd299f4c6ce",
    "wbtc": "0x4e59541306910ad6dc1dac0ac9dfb29bd9f15c67",
    "sfrxeth": "0xec0820efafc41d8943ee8de495fc9ba8495b15cf",
    "weth": "0xa920de414ea4ab66b97da1bfe9e6eca7d4219635", 
    "tbtc": "0x1c91da0223c763d2e0173243eadaa0a2ea47e704",
    "ll_0": "0x1E0165DbD2019441aB7927C018701f3138114D71",
    "ll_1": "0xaade9230AA9161880E13a38C83400d3D1995267b",
    "ll_2": "0x413FD2511BAD510947a91f5c6c79EBD8138C29Fc",
    "ll_3": "0xEdA215b7666936DEd834f76f3fBC6F323295110A",
    "ll_4": "0xC510d73Ad34BeDECa8978B6914461aA7b50CF3Fc",
    "ll_5": "0xa5D9137d2A1Ee912469d911A8E74B6c77503bac8",
    "ll_6": "0xe438658874b0acf4D81c24172E137F0eE00621b8",
    "ll_7": "0x98Fc283d6636f6DCFf5a817A00Ac69A3ADd96907",
    "ll_8": "0x09dBDEB3b301A4753589Ac6dF8A178C7716ce16B",
    "ll_9": "0xcaD85b7fe52B1939DCEebEe9bCf0b2a5Aa0cE617",
    "ll_10": "0x4f87158350c296955966059C50263F711cE0817C"
}

# Enable to show trace for a single user
single_user = None

# Load the event data
with open(filename, 'r') as f:
    all_events = json.load(f)

# Skip users with weird behavior that break this
weird_users = ['0x0d59d4e24731c7304baefd9360ec9669764be28a', '0x67e5dbe8b910b307adfee1c119c63f417101300b', '0x287b490157733dc047cf80db5c9a84868d42c50a', '0x46e8c1d761e890166b51b647db8e8f917d9d8864']

# Dictionary to store user loan data by contract
user_loan_data = defaultdict(lambda: {
    "collateral": 0,
    "borrow_amount": 0,
    "status": "active"  # Default status
})

def parse_event_data(event, start, end, event_type):
    try:
        data = event["data"]["data"]
        if len(data) >= end:
            value = int(data[start:end], 16)
        else:
            print(f"Data length is shorter than expected for event: {event_type}, data: {data}")
            value = 0
    except ValueError:
        print(f"Failed to parse {event_type} data for event: {event}")
        value = 0
    return value

user_history = recursive_defaultdict()
for address, events in all_events.items():
    for event in events:
        contract = event['contract']
        event_type = event['event']
        block = event['blockNumber']
        if address not in weird_users:
            if event_type != 'UserState':
                existing = user_history[address][contract][block]['event']
                if event_type == 'Repay' and existing == 'Borrow':
                    user_history[address][contract][block]['event'] = 'same_block_borrow_repay'
                elif event_type == 'Liquidate':
                    if event['data']['topics'][1] == event['data']['topics'][2]:
                        user_history[address][contract][block]['event'] = "self-liquidation"
                    else:
                        user_history[address][contract][block]['event'] = "forced-liquidation"

                else:
                    user_history[address][contract][block]['event'] = event_type
            else:
                user_history[address][contract][block]['data'] = event['data']['data']

def crawl_dict(d, path=None):
    if path is None:
        path = []

    for key, value in d.items():
        new_path = path + [key]
        if isinstance(value, defaultdict):
            crawl_dict(value, new_path)
        else:
            # Ensure all elements in new_path are strings
            str_path = list(map(str, new_path))
            print("Path:", " -> ".join(str_path), "Value:", value)

row_items = []
for user, contracts in user_history.items():
    for contract, blocks in contracts.items():
        active_loan = None
        for block, items in blocks.items():
            if user == single_user:
                print(f"User: {user}, Contract: {contract}, Block: {block}")
                print(f"Event: {items.get('event')}, Data: {items.get('data')}")            
                print(items.get('event'))
                print(row_items[-1])
            if items.get('event') == 'Borrow':
                if active_loan is None:
                    active_loan = [user, contract, block]
            if items.get('event') == 'Repay' and items.get('data') == '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000':

                if active_loan is None:
                    print(row_items[-1])
                    print(user, contract, block)
                active_loan.append('repaid')
                active_loan.append(block)
                row_items.append(active_loan)
                active_loan = None
            if items.get('event') in ['self-liquidation','forced-liquidation']:
                if active_loan is None:
                    print(user, contract, block)
                active_loan.append(items.get('event'))
                active_loan.append(block)
                row_items.append(active_loan)
                active_loan = None
        if active_loan is not None:
            active_loan.append('active')
            row_items.append(active_loan)

assert len(row_items) > 0

# Define the column names
columns = ['Address', 'Asset', 'Start_Block', 'Status', 'End_Block']

# Load the list into a DataFrame
df = pd.DataFrame(row_items, columns=columns)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"data/parse_{timestamp}.csv"
df.to_csv(f'{filename}', index=False)
print(f"Saved to {filename}")

