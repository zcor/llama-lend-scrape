import os
import requests
import json
from datetime import datetime
from web3 import Web3

# Configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
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
    "ll_10": "0x4f87158350c296955966059C50263F711cE0817C",
}

# Event signatures
BORROW_EVENT_SIGNATURE = Web3.keccak(text="Borrow(address,uint256,uint256)").hex()
REPAY_EVENT_SIGNATURE = Web3.keccak(text="Repay(address,uint256,uint256)").hex()
LIQUIDATE_EVENT_SIGNATURE = Web3.keccak(
    text="Liquidate(address,address,uint256,uint256,uint256)"
).hex()
REMOVE_COLLATERAL_EVENT_SIGNATURE = Web3.keccak(
    text="RemoveCollateral(address,uint256)"
).hex()
USER_STATE_EVENT_SIGNATURE = Web3.keccak(
    text="UserState(address,uint256,uint256,int256,int256,uint256)"
).hex()


def fetch_logs(contract_address, topic):
    page = 1
    all_logs = []
    while True:
        url = f"https://api.etherscan.io/api"
        params = {
            "module": "logs",
            "action": "getLogs",
            "fromBlock": "0",
            "toBlock": "latest",
            "address": contract_address,
            "topic0": topic,
            "apikey": ETHERSCAN_API_KEY,
            "page": page,
            "offset": 1000,
        }
        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] == "1":
            all_logs.extend(data["result"])
            if len(data["result"]) < 1000:
                break
            page += 1
        else:
            break
    return all_logs


def main():
    all_events = {}
    total_liquidations = 0
    self_liquidations = 0

    for contract_name, contract_address in CONTRACT_ADDRESSES.items():
        print(f"Fetching events for contract: {contract_name}")

        # Fetch logs for each event type
        event_types = [
            ("Borrow", BORROW_EVENT_SIGNATURE),
            ("Repay", REPAY_EVENT_SIGNATURE),
            ("Liquidate", LIQUIDATE_EVENT_SIGNATURE),
            ("RemoveCollateral", REMOVE_COLLATERAL_EVENT_SIGNATURE),
            ("UserState", USER_STATE_EVENT_SIGNATURE),
        ]

        for event_name, event_signature in event_types:
            logs = fetch_logs(contract_address, event_signature)
            for log in logs:
                if event_name == "Liquidate":
                    liquidator = (
                        "0x" + log["topics"][1][26:] if len(log["topics"]) > 1 else None
                    )
                    user = (
                        "0x" + log["topics"][2][26:] if len(log["topics"]) > 2 else None
                    )
                    if liquidator and user:
                        is_self_liquidation = liquidator.lower() == user.lower()
                        if is_self_liquidation:
                            self_liquidations += 1
                        total_liquidations += 1
                else:
                    user = (
                        "0x" + log["topics"][1][26:] if len(log["topics"]) > 1 else None
                    )

                if user:
                    if user not in all_events:
                        all_events[user] = []
                    all_events[user].append(
                        {
                            "event": event_name,
                            "blockNumber": int(log["blockNumber"], 16),
                            "contract": contract_name,
                            "data": log,
                            "self_liquidation": (
                                is_self_liquidation
                                if event_name == "Liquidate"
                                else None
                            ),
                        }
                    )
                else:
                    print(log)

    # Sort events by block number for each user
    for user, events in all_events.items():
        all_events[user] = sorted(events, key=lambda x: x["blockNumber"])

    # Calculate and print the percentage of self-liquidations
    if total_liquidations > 0:
        percentage_self_liquidated = (self_liquidations / total_liquidations) * 100
        print(f"Total Liquidated Loans: {total_liquidations}")
        print(f"Self-Liquidated Loans: {self_liquidations}")
        print(f"Percentage of Self-Liquidated Loans: {percentage_self_liquidated:.2f}%")
    else:
        print("No liquidations found.")

    # Save events to a JSON file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"data/debug_events_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(all_events, f, indent=4)

    print(f"Events saved to {filename}")


if __name__ == "__main__":
    main()
