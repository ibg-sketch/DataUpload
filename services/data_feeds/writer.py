"""
Append-only CSV writer with rotation.
"""
import os
import csv
from pathlib import Path
from datetime import datetime
from typing import List
from .schemas import FeedRow


class FeedWriter:
    """Append-only CSV writer with automatic rotation"""
    
    def __init__(self, csv_path: str, rotate_mb: int = 200, keep_files: int = 14):
        """
        Args:
            csv_path: Path to CSV file
            rotate_mb: Rotate when file exceeds this size (MB)
            keep_files: Number of rotated files to keep
        """
        self.csv_path = Path(csv_path)
        self.rotate_bytes = rotate_mb * 1024 * 1024
        self.keep_files = keep_files
        
        # Ensure directory exists
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV with header if doesn't exist
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Create CSV with header if it doesn't exist"""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'oi', 'oi_pct', 'funding', 'basis',
                    'liq_long_usd', 'liq_short_usd', 'liq_ratio', 'obi_top',
                    'basis_pct', 'basis_provider',
                    'latency_ms', 'source_errors', 'provider_oi', 'provider_funding', 'provider_basis'
                ])
    
    def append_rows(self, rows: List[FeedRow]):
        """
        Append multiple rows to CSV.
        
        Args:
            rows: List of FeedRow objects
        """
        if not rows:
            return
        
        # Check if rotation needed
        self._check_rotation()
        
        # Append rows
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow([
                    row.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    row.symbol,
                    row.oi,
                    row.oi_pct,
                    row.funding,
                    row.basis,
                    row.liq_long_usd,
                    row.liq_short_usd,
                    row.liq_ratio,
                    row.obi_top,
                    row.basis_pct,
                    row.basis_provider,
                    row.latency_ms,
                    row.source_errors,
                    row.provider_oi,
                    row.provider_funding,
                    row.provider_basis
                ])
    
    def _check_rotation(self):
        """Rotate CSV if it exceeds size limit"""
        if not self.csv_path.exists():
            return
        
        file_size = self.csv_path.stat().st_size
        
        if file_size > self.rotate_bytes:
            self._rotate_file()
    
    def _rotate_file(self):
        """Rotate current CSV file"""
        # Get file size before rotation
        file_size = self.csv_path.stat().st_size
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rotated_name = f"{self.csv_path.stem}_{timestamp}.csv"
        rotated_path = self.csv_path.parent / rotated_name
        
        # Rename current file
        self.csv_path.rename(rotated_path)
        print(f"[WRITER] Rotated: {rotated_path.name} ({file_size / 1024 / 1024:.1f} MB)")
        
        # Create new file with header
        self._ensure_csv_exists()
        
        # Clean up old files
        self._cleanup_old_files()
    
    def _cleanup_old_files(self):
        """Remove old rotated files, keeping only the most recent N"""
        pattern = f"{self.csv_path.stem}_*.csv"
        rotated_files = sorted(
            self.csv_path.parent.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Remove files beyond keep_files limit
        for old_file in rotated_files[self.keep_files:]:
            old_file.unlink()
            print(f"[WRITER] Removed old file: {old_file.name}")
    
    def get_stats(self) -> dict:
        """Get writer statistics"""
        if not self.csv_path.exists():
            return {
                'exists': False,
                'size_mb': 0,
                'rows': 0,
                'rotated_files': 0
            }
        
        file_size = self.csv_path.stat().st_size
        
        # Count rows (excluding header)
        with open(self.csv_path, 'r') as f:
            row_count = sum(1 for _ in f) - 1
        
        # Count rotated files
        pattern = f"{self.csv_path.stem}_*.csv"
        rotated_count = len(list(self.csv_path.parent.glob(pattern)))
        
        return {
            'exists': True,
            'size_mb': file_size / 1024 / 1024,
            'rows': row_count,
            'rotated_files': rotated_count,
            'rotation_threshold_mb': self.rotate_bytes / 1024 / 1024
        }
