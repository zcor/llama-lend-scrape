import pandas as pd
import numpy as np
import logging
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ape import Contract, chain, accounts
from ape.logging import logger as ape_logger

CONTRACT_ADDRESSES = {
    "wsteth": "0x100daa78fc509db39ef7d04de0c1abd299f4c6ce",
    "wbtc": "0x4e59541306910ad6dc1dac0ac9dfb29bd9f15c67",
    "sfrxeth": "0x8472a9a7632b173c8cf3a86d3afec50c35548e76",
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


# Configuration
TEST_MODE = False
TEST_RESOLUTION = 10
PROD_RESOLUTION = 50
start_time = time.time()
# Uncomment and just run a few to test
# CUTOFF = 5 
# Script interrupted?  Uncomment to skip ahead...
# SKIP = 2500 

# Set the logging level to CRITICAL to suppress lower-level messages
#ape_logger.set_level(logging.CRITICAL)


resolution = TEST_RESOLUTION if TEST_MODE else PROD_RESOLUTION
def main():
    """
    Main function to process user data, save it to a CSV file, and plot the data.
    It processes health, AMM prices, band bounds, and user state values over a range of blocks.
    """

    # Main loop
    liqs = pd.read_csv('data/parse_2024-06-05_09-13-00.csv')
    i = 0
    all_data = pd.DataFrame()

    for index, row in liqs.iterrows():
        #if i <= SKIP:
        #    i += 1
        #    continue

        #if i > CUTOFF:
        #    break

        # Configure blocks
        if row['Start_Block'] == row['End_Block']:
            # Flashloan?  Atta degen...
            unique_blocks = [start_block]

        # Loan still alive more than likely
        elif np.isnan(row['End_Block']):
            start_block = row['Start_Block']
            final_block = 19964792
            blocks = np.linspace(start_block, final_block, resolution, dtype=int)
            unique_blocks = np.unique(blocks)
        
        # Get data from the block before, since the final block has nothing
        else:
            start_block = row['Start_Block']
            end_block = row['End_Block'] -1
            blocks = np.linspace(start_block, end_block, resolution, dtype=int)

            # Short loans may pull blocks multiple times
            unique_blocks = np.unique(blocks)

        # Let's go
        data = process_user_data(i, row['Address'], Contract(CONTRACT_ADDRESSES[row['Asset']]), unique_blocks)
        all_data = pd.concat([all_data, pd.DataFrame(data)], ignore_index=True)

        # Display progress because the script is SLOW
        i += 1
        elapsed_time = time.time() - start_time
        avg_time_per_block = elapsed_time / i
        estimated_time_remaining = avg_time_per_block * (liqs.shape[0] - i)
        formatted_time_remaining = format_time(estimated_time_remaining)
        print(i, liqs.shape[0], f"{100 * i/liqs.shape[0]:.1f}%", elapsed_time, formatted_time_remaining)

        # Save partial in case of error or interrupt
        all_data.to_csv("tmp.csv", index=False)

    save_data_to_csv(all_data)
    print(f"Runtime: {format_time(time.time() - start_time)} ")


def process_user_data(i, user, controller, blocks):
    """
    Processes and collects data for a given user over a specified range of blocks.
    """

    print(f"Processing {user}")
    data = {
        'i': [],
        "user": [],
        "times": [],
        "amm_prices": [],
        "health_values": [],
        'lower_band_p': [],
        'upper_band_p': [],
        "lower_band": [],
        "upper_band": [],
        "user_state_calc": [],
        'us1':[],
        'us2':[],
        'us3':[],
        'us4':[]
    }

    blocks_processed = 0
    for block in blocks:

        t, h, n1, n2, amm_price, user_state = process_block(user, block, controller)
        amm = Contract(controller.amm())
        data['i'].append(i)
        data['user'].append(user)
        data["times"].append(t)
        data["health_values"].append(h)
        data["amm_prices"].append(amm_price)

        p_current_down = amm.p_oracle_down(n1) / 1e18 if n1 is not None else np.nan
        p_current_up = amm.p_oracle_up(n2) / 1e18 if n2 is not None else np.nan
        data["lower_band"].append(n1)
        data["lower_band_p"].append(p_current_down)
        data["upper_band"].append(n2)
        data["upper_band_p"].append(p_current_up)

        if user_state[0] is not None and user_state[1] is not None:
            data["user_state_calc"].append(user_state[1] / (user_state[0] + user_state[1]))
            data['us1'].append(user_state[0])
            data['us2'].append(user_state[1])
            data['us3'].append(user_state[2])
            data['us4'].append(user_state[3])
        else:
            data["user_state_calc"].append(None)
            data['us1'].append(None)
            data['us2'].append(None)
            data['us3'].append(None)
            data['us4'].append(None)

    return data


def process_block(user, block, controller):
    """
    Processes data for a given user at a specific block.

    :param user: User address to process.
    :param block: The block number to process.
    :param controller: Ape Contract with AMM
    :return: Tuple containing health, n1, n2, AMM price, and user state data at the given block.
    """
    block = int(block)
    amm = Contract(controller.amm())
    try:
        h = controller.health(user, True, block_identifier=block) / 1e18 * 100
        n1, n2 = amm.read_user_tick_numbers(user, block_identifier=block)
        amm_price = amm.active_band(block_identifier=block)
        user_state = controller.user_state(user, block_identifier=block)
    except Exception as e:
        print(f"{e} {amm} {controller}")
        h, n1, n2, amm_price, user_state = None, None, None, None, [None] * 4
    return block, h, n1, n2, amm_price, user_state


def save_data_to_csv(data):
    """
    Saves the provided data into a CSV file.

    :param data: Dictionary containing various time-series data.
    """
    # Prepare DataFrame
    #df = pd.DataFrame(data)
    df = data

    # Save to CSV
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"data/data{'_test' if TEST_MODE else '_prod'}/liquidations_{timestamp}.csv"
    df.to_csv(filename, index=False)
    print(f"\rData saved to {filename}")


def format_time(seconds):
    """
    Converts seconds into a more readable format (days, hours, minutes, seconds).

    :param seconds: Time in seconds.
    :return: Formatted time string.
    """
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_format = ""
    if days > 0:
        time_format += f"{int(days)}d "
    if hours > 0:
        time_format += f"{int(hours)}h "
    if minutes > 0:
        time_format += f"{int(minutes)}m "
    time_format += f"{int(seconds)}s"
    return time_format


if __name__ == "__main__":
    main()
