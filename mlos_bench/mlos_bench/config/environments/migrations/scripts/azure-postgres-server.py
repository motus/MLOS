#!/usr/bin/env python3
#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
Helper script to update the environment parameters from JSON.

Run:
    `./bench_setup.py ./input-params.json ./input-params-meta.json`
"""

import json
from azure.cli.core import get_default_cli

SUBSCRIPTION_ID="929287ae-832a-4946-8006-a6cc2a3f7244"
RESOURCE_GROUP="vaiscript"
LOCATION="eastus"
SOURCE_SERVER_NAME="mloserver-sourcetwo"
FLEXIBLE_SERVER_NAME="mloserver-targettwo"
ADMIN_USER="meruadmin"
PASSWORD="password@123"
SKU_NAME_SINGLE="GP_Gen5_2"
SKU_NAME_FLEXIBLE="Standard_D2s_v3"
SOURCE_DB_VERSION="11"
FLEXIBLE_DB_VERSION="16"

def run_azure_cli_command(command_str):
    print(f"Running command: {command_str}")
    args = command_str.split()
    cli = get_default_cli()
    cli.invoke(args)
    if cli.result.result:
        return cli.result.result
    elif cli.result.error:
        raise cli.result.error
    return True

def _main(fname_input: str, fname_meta: str, fname_output: str) -> None:
    print("running migration setup now...")

    # Set the Azure subscription
    
    command_str = f"account set --subscription {SUBSCRIPTION_ID}"
    run_azure_cli_command(command_str)

    # Create Resource Group
    command_str = f"group create --name {RESOURCE_GROUP} --location {LOCATION}"
    run_azure_cli_command(command_str)

    # Create the source server
    command_str = f"""
        postgres server create \
        --name {SOURCE_SERVER_NAME} \
        --resource-group {RESOURCE_GROUP} \
        --admin-user {ADMIN_USER} \
        --admin-password {PASSWORD} \
        --public 0.0.0.0-255.255.255.255 \
        --sku-name {SKU_NAME_SINGLE} \
        --version {SOURCE_DB_VERSION}
        """
    run_azure_cli_command(command_str)

    # Create the target server
    command_str = f"""
        postgres flexible-server create \
        --name {FLEXIBLE_SERVER_NAME} \
        --resource-group {RESOURCE_GROUP} \
        --admin-user {ADMIN_USER} \
        --admin-password {PASSWORD} \
        --public-access 0.0.0.0 \
        --sku-name {SKU_NAME_FLEXIBLE} \
        --tier GeneralPurpose \
        --version {FLEXIBLE_DB_VERSION}
        """
    run_azure_cli_command(command_str)

    # Key-value pairs of tunable parameters, e.g.,
    # {"shared_buffers": "128", ...}
    # with open(fname_input, "rt", encoding="utf-8") as fh_tunables:
    #     tunables_data = json.load(fh_tunables)

    # # Optional free-format metadata for tunable parameters, e.g.
    # # {"shared_buffers": {"suffix": "MB"}, ...} ?? what do we do with the meta data...
    # with open(fname_meta, "rt", encoding="utf-8") as fh_meta:
    #     tunables_meta = json.load(fh_meta)

    # with open(fname_output, "wt", encoding="utf-8", newline="") as fh_config:
    #     for key, val in tunables_data.items():
    #         meta = tunables_meta.get(key, {})
    #         name_suffix = meta.get("suffix", "")
    #         line = f"{key} = {val}{name_suffix}"
    #         fh_config.write(line + "\n")
    #         print(line)

    #         command_str = f"""
    #             postgres flexible-server parameter set \
    #             --server-name {FLEXIBLE_SERVER_NAME} \
    #             --resource-group {RESOURCE_GROUP} \
    #             --name {key} \
    #             --value {val}
    #             """
    #         run_azure_cli_command(command_str)