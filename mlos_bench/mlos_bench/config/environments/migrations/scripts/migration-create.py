#!/usr/bin/env python3
#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
Helper script to run the benchmark and store
the results and telemetry in CSV files.

Run:
    ./bench_run.py ./output-metrics.csv ./output-telemetry.csv`
"""

import argparse
from datetime import datetime, timedelta
from azure.cli.core import get_default_cli
import pandas
import time 

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
DBS_TO_MIGRATE = ["postgres"]
MIGRATION_NAME = "mlo-migratione54"

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

def _main(output_metrics: str, output_telemetry: str) -> None:

    # Get Resource ID for the source PostgreSQL Single Server
    command_str = f"postgres server show --name {SOURCE_SERVER_NAME} --resource-group {RESOURCE_GROUP} --query id -o tsv"
    SOURCE_SERVER_RESOURCE_ID = run_azure_cli_command(command_str).strip()

    # Create the migrationBody.json file for migration configuration
    migration_body = {
        "properties": {
            "sourceDbServerResourceId": SOURCE_SERVER_RESOURCE_ID,
            "secretParameters": {
                "adminCredentials": {
                    "sourceServerPassword": PASSWORD,
                    "targetServerPassword": PASSWORD
                },
                "sourceServerUserName": f"{ADMIN_USER}@{SOURCE_SERVER_NAME}",
                "targetServerUserName": ADMIN_USER
            },
            "dbsToMigrate": [
                DBS_TO_MIGRATE[0]
            ],
            "overwriteDbsInTarget": "true"
        }
    }

    with open("migrationBody.json", "w") as f:
        import json
        json.dump(migration_body, f, indent=4)

    # Run the migration from Single Server to Flexible Server
    command_str = f"""
    postgres flexible-server migration create \
      --subscription {SUBSCRIPTION_ID} \
      --resource-group {RESOURCE_GROUP} \
      --name {FLEXIBLE_SERVER_NAME} \
      --migration-name {MIGRATION_NAME} \
      --properties ./migrationBody.json \
      --migration-mode offline
    """
    run_azure_cli_command(command_str)

    START_TIME = datetime.now()

    # Monitor migration status every 30 seconds
    while True:
        # Get migration status
        command_str = f"""
        postgres flexible-server migration show \
          --subscription {SUBSCRIPTION_ID} \
          --resource-group {RESOURCE_GROUP} \
          --name {FLEXIBLE_SERVER_NAME} \
          --migration-name {MIGRATION_NAME} \
          --query currentStatus.state -o tsv
        """
        MIGRATION_STATUS = run_azure_cli_command(command_str).strip()

        print(f"Current migration status: {MIGRATION_STATUS}")

        # Check the migration state and take action accordingly
        if MIGRATION_STATUS in ["InProgress", "CleaningUp"]:
            print("Migration is still in progress... Checking again in 30 seconds.")
            time.sleep(30)
        elif MIGRATION_STATUS == "Succeeded":
            print("Migration succeeded!")
            break
        elif MIGRATION_STATUS in ["Failed", "Canceled", "ValidationFailed"]:
            print(f"Migration {MIGRATION_STATUS.lower()}. Please check the Azure portal for more details.")
            exit(1)
        else:
            print(f"Unexpected status: {MIGRATION_STATUS}")
            time.sleep(30)

    # Calculate the total time taken for migration
    END_TIME = datetime.now()
    TOTAL_TIME = (END_TIME - START_TIME).total_seconds()
    print(f"Total time taken for migration: {TOTAL_TIME} seconds.")

    df_metrics = pandas.DataFrame([
        {"metric": "total_time", "value": TOTAL_TIME},
    ])
    df_metrics.to_csv(output_metrics, index=False)

    timestamp = datetime.now()
    df_telemetry = pandas.DataFrame([
        {"timestamp": timestamp, "metric": "total_time", "value": TOTAL_TIME},
    ])
    df_telemetry.to_csv(output_telemetry, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the benchmark and save the results in CSV files.")
    parser.add_argument("output_metrics", help="CSV file to save the benchmark results to.")
    parser.add_argument("output_telemetry", help="CSV file for telemetry data.")
    args = parser.parse_args()
    _main(args.output_metrics, args.output_telemetry)
