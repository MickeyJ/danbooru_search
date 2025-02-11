import asyncio
from asgiref.sync import sync_to_async
from django.core.management import call_command
from django.db.models import Count
from django.utils import timezone
from django.core.cache import cache

from ..models import Tag, UpdateStatus, CommonWord
from .word_checker import is_likely_typo, get_common_words
from .backup_service import BackupService
from .api_service import DanbooruAPI
from .tag_logger import TagLogger


class TagUpdater:
    def __init__(self):
        self.status = None
        self.common_words = None
        self.api = DanbooruAPI()
        self.backup_service = BackupService()
        self.tag_logger = TagLogger()
        self.tags_per_page = 1000
        self.total_tags_processed = 0
        self.log_file = None

    async def initialize(self):
        """Initialize required data and services"""
        # Start new log file
        self.log_file = self.tag_logger.start_new_log()

        # Check and initialize word database if empty
        if await sync_to_async(CommonWord.objects.count)() == 0:
            print("Initializing word database...")
            await sync_to_async(lambda: call_command("init_wordlist"))()

        # Get common words
        self.common_words = await get_common_words()

        # Initialize or get update status
        self.status = await sync_to_async(lambda: UpdateStatus.objects.first())()
        if not self.status:
            self.status = await sync_to_async(UpdateStatus.objects.create)()

        # Set initial status values
        self.status.total_tags = 200000  # Approximate
        self.status.start_time = timezone.now()
        self.status.is_updating = True
        await sync_to_async(lambda: self.status.save())()

    async def check_duplicates(self):
        """Check for duplicate tags in database"""
        duplicates = await sync_to_async(
            lambda: list(
                Tag.objects.values("name")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )
        )()
        return duplicates

    def is_valid_tag(self, tag_data):
        """
        Check if a tag is valid and should be included.
        Returns (is_valid, reason) tuple.
        """
        # Skip deprecated tags
        if tag_data.get("is_deprecated", False):
            self.tag_logger.log_rejected_tag(tag_data, "deprecated")
            return False, "deprecated"

        # Check for typos and known words
        has_known_word = False
        has_typo = False
        typo_words = []

        if "words" in tag_data:
            for word in tag_data["words"]:
                word = word.lower()
                is_typo, _ = is_likely_typo(word, self.common_words)
                if is_typo:
                    has_typo = True
                    typo_words.append(word)
                    break
                elif word in self.common_words:
                    has_known_word = True

        # Skip if there's a typo
        if has_typo:
            self.tag_logger.log_rejected_tag(
                tag_data, "typo", f"Possible typos: {', '.join(typo_words)}"
            )
            return False, "typo"

        # Skip if no words are known
        if tag_data["words"] and not has_known_word:
            self.tag_logger.log_rejected_tag(
                tag_data, "unknown_words", f"Words: {', '.join(tag_data['words'])}"
            )
            return False, "no known words"

        return True, None

    async def process_tag_batch(self, tags):
        """Process a batch of tags from the API"""
        new_tags = []
        invalid_tags = []
        deprecated_count = 0
        typo_count = 0

        for tag_data in tags:
            is_valid, reason = self.is_valid_tag(tag_data)

            if not is_valid:
                if reason == "deprecated":
                    deprecated_count += 1
                elif reason in ["typo", "no known words"]:
                    typo_count += 1
                else:
                    invalid_tags.append(tag_data["name"])
                continue

            new_tags.append(
                Tag(
                    name=tag_data["name"],
                    post_count=tag_data["post_count"],
                )
            )

        return new_tags, invalid_tags, deprecated_count, typo_count

    async def _bulk_update_tags(self, tags):
        """Bulk update tags in database"""
        await sync_to_async(Tag.objects.bulk_create)(tags, ignore_conflicts=True)

    async def _update_last_page(self, page):
        """Update the last successful page number"""
        if await sync_to_async(Tag.objects.exists)():
            first_tag = await sync_to_async(lambda: Tag.objects.first())()
            first_tag.last_update_page = page
            await sync_to_async(lambda: first_tag.save())()

    async def perform_update(self):
        """Main update process"""
        try:
            # Initialize
            await self.initialize()

            # Check for duplicates
            duplicates = await self.check_duplicates()
            if duplicates:
                print("\n!!! EXISTING DUPLICATES FOUND !!!")
                for dup in duplicates:
                    print(f"Tag: {dup['name']}, Count: {dup['count']}")
                return

            # Create backup if needed
            if (
                not self.status.last_backup
                or (timezone.now() - self.status.last_backup).days >= 1
            ):
                await self.backup_service.create_backup()
                self.status.last_backup = timezone.now()
                await sync_to_async(lambda: self.status.save())()

            # Get starting page
            last_page = await sync_to_async(
                lambda: (
                    Tag.objects.first().last_update_page if Tag.objects.exists() else 0
                )
            )()
            page = last_page + 1

            # Main update loop
            while True:
                try:
                    # Get tags from API
                    tags = await self.api.get_tags_page(page, self.tags_per_page)
                    if not tags:
                        break

                    # Process batch
                    new_tags, invalid_tags, deprecated_count, typo_count = (
                        await self.process_tag_batch(tags)
                    )

                    # Handle invalid tags
                    if invalid_tags:
                        print(f"\n!!! Found {len(invalid_tags)} invalid tags !!!")
                        return

                    # Save valid tags
                    if new_tags:
                        await self._bulk_update_tags(new_tags)
                        await self._update_last_page(page)

                    # Update status
                    self.total_tags_processed += len(tags)
                    self.status.processed_tags += len(tags)
                    self.status.current_page = page
                    await sync_to_async(lambda: self.status.save())()

                    # Rate limiting
                    await asyncio.sleep(1)
                    page += 1

                except Exception as e:
                    print(f"Error processing page {page}: {str(e)}")
                    raise

        finally:
            self.status.is_updating = False
            await sync_to_async(lambda: self.status.save())()
            if self.log_file:
                self.log_file.close()
