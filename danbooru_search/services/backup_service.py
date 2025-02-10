import os
from pathlib import Path
from django.conf import settings
from ..models import Tag
from asgiref.sync import sync_to_async
from django.utils import timezone
import shutil


class BackupService:
    def __init__(self):
        self.backup_path = settings.BASE_DIR / "backups"
        self.backup_path.mkdir(exist_ok=True)

    async def create_backup(self):
        """Create a backup of the current database"""
        tag_count = await sync_to_async(Tag.objects.count)()
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"db_backup_{tag_count}_{timestamp}.sqlite3"
        backup_file = self.backup_path / backup_name

        await sync_to_async(shutil.copy2)(
            settings.DATABASES["default"]["NAME"], backup_file
        )
        return backup_file

    async def restore_latest_backup(self):
        """Restore the most recent backup with more tags than current DB"""
        current_count = await sync_to_async(Tag.objects.count)()

        backups = []
        for backup in self.backup_path.glob("db_backup_*.sqlite3"):
            try:
                tag_count = int(backup.stem.split("_")[-2])
                backups.append((backup, tag_count))
            except (ValueError, IndexError):
                continue

        if not backups:
            return False, "No valid backups found"

        latest_backup, backup_count = max(
            backups, key=lambda x: (x[1], x[0].stat().st_mtime)
        )

        if backup_count <= current_count:
            return False, "Current database has more tags than backup"

        await sync_to_async(shutil.copy2)(
            latest_backup, settings.DATABASES["default"]["NAME"]
        )
        return True, f"Restored backup with {backup_count} tags"
