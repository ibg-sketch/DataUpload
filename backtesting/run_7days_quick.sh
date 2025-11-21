#!/bin/bash
# Backtesting pipeline - QUICK MODE for 7 DAYS

echo "=========================================="
echo "BACKTESTING - QUICK MODE (Last 7 Days)"
echo "=========================================="
echo ""

# Calculate start date (7 days ago)
START_DATE=$(python3 -c "from datetime import datetime, timedelta; d = datetime.now() - timedelta(days=7); print(d.strftime('%Y-%m-%d'))")

echo "Period: $START_DATE to $(date +%Y-%m-%d)"
echo "Mode: QUICK (~500K combinations)"
echo "Estimated time: ~20-30 minutes"
echo ""

echo "Step 1/5: Downloading OHLCV data (BingX API)..."
python3 backtesting/bingx_data_downloader.py $START_DATE

if [ $? -ne 0 ]; then
    echo "❌ Error downloading OHLCV data"
    exit 1
fi

echo ""
echo "Step 2/5: Calculating indicators..."
python3 backtesting/indicator_calculator.py

if [ $? -ne 0 ]; then
    echo "❌ Error calculating indicators"
    exit 1
fi

echo ""
echo "Step 3/5: Downloading advanced data (OI, Liquidations, Funding)..."
python3 backtesting/advanced_data_downloader.py --start=$START_DATE

if [ $? -ne 0 ]; then
    echo "❌ Error downloading advanced data"
    exit 1
fi

echo ""
echo "Step 4/5: Merging all data sources..."
python3 backtesting/merge_all_data.py

if [ $? -ne 0 ]; then
    echo "❌ Error merging data"
    exit 1
fi

echo ""
echo "Step 5/5: Optimizing formula (QUICK MODE)..."
echo "This will take ~20-30 minutes..."
python3 backtesting/full_optimizer.py --quick

if [ $? -ne 0 ]; then
    echo "❌ Error during optimization"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ BACKTESTING COMPLETE"
echo "=========================================="
echo ""
echo "Results saved to: backtesting/best_formula_quick.json"
