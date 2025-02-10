from django.db import models
from django.utils import timezone


class UpdateStatus(models.Model):
    total_tags = models.IntegerField(default=0)
    processed_tags = models.IntegerField(default=0)
    current_page = models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True)
    last_backup = models.DateTimeField(null=True)
    is_updating = models.BooleanField(default=False)

    @property
    def progress_percentage(self):
        return (
            (self.processed_tags / self.total_tags * 100) if self.total_tags > 0 else 0
        )

    @property
    def estimated_time_remaining(self):
        if not self.start_time or self.processed_tags == 0:
            return None

        elapsed = (timezone.now() - self.start_time).total_seconds()
        tags_per_second = self.processed_tags / elapsed
        remaining_tags = self.total_tags - self.processed_tags

        return remaining_tags / tags_per_second if tags_per_second > 0 else None


class Tag(models.Model):
    name = models.CharField(max_length=255, unique=True)
    post_count = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    last_update_page = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["-post_count"]),
        ]

    def __str__(self):
        return self.name
