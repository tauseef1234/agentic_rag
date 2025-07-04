#!/bin/bash

# Run any setup steps or pre-processing tasks here
echo "Running ETL to move bank data from csvs to Neo4j..."

# Run the ETL script
python bank_bulk_csv_write.py
