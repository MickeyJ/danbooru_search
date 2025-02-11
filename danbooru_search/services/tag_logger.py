import csv
from pathlib import Path
from django.conf import settings
from datetime import datetime


class TagLogger:
    def __init__(self):
        self.log_dir = settings.BASE_DIR / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = None
        self.writer = None

    def start_new_log(self):
        """Start a new log file, replacing any existing one"""
        self.log_file = self.log_dir / "rejected_tags.csv"
        print(f"\nCreating log file at: {self.log_file}")

        # Open in write mode to clear/create file
        f = open(self.log_file, "w", newline="", encoding="utf-8")
        self.writer = csv.writer(f)

        # Write header
        self.writer.writerow(
            ["timestamp", "tag_name", "reason", "details", "post_count"]
        )
        print("Initialized CSV with headers")
        return f  # Return file handle to close in context manager

    def log_rejected_tag(self, tag_data, reason, details=""):
        """Log a rejected tag with its reason"""
        if self.writer:
            print(f"Logging rejected tag: {tag_data['name']} - {reason}")
            self.writer.writerow(
                [
                    datetime.now().isoformat(),
                    tag_data["name"],
                    reason,
                    details,
                    tag_data.get("post_count", 0),
                ]
            )
        else:
            print("Warning: Attempted to log tag but writer is not initialized")
