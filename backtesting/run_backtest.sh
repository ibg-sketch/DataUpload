#!/bin/bash
# Complete backtesting pipeline with advanced data

echo "=================================="
echo "BACKTESTING PIPELINE - FULL"
echo "=================================="

echo ""
echo "Step 1: Downloading OHLCV data..."
python3 backtesting/data_downloader.py

echo ""
echo "Step 2: Calculating indicators..."
python3 backtesting/indicator_calculator.py

echo ""
echo "Step 3: Downloading advanced data (OI, CVD, Liquidations, Funding)..."
python3 backtesting/advanced_data_downloader.py

echo ""
echo "Step 4: Merging all data sources..."
python3 backtesting/merge_all_data.py

echo ""
echo "Step 5: Optimizing formula with ALL indicators..."
echo "  (Use --quick flag for faster results)"
python3 backtesting/full_optimizer.py $@

echo ""
echo "=================================="
echo "✅ BACKTESTING COMPLETE"
echo "=================================="
echo ""
echo "Check backtesting/best_formula.json for results"
