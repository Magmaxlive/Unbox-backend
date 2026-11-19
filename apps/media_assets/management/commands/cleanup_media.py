from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import ProtectedError
from django.utils import timezone

from apps.media_assets import storage
from apps.media_assets.models import Media_asset

Status = Media_asset.Status

# Not referenced by any content (reverse relations of the foreign keys):
#   Blog.cover_image      -> related_name='blog_cover_image'
#   Video.thumbnail       -> related_name='video_thumbnails'
#   Video.media_asset     -> related_name='videos'
UNREFERENCED = {
    'blog_cover_image__isnull': True,
    'video_thumbnails__isnull': True,
    'videos__isnull': True,
}


def asset_keys(asset):
    """Every S3 key belonging to an asset: the original plus generated versions."""
    keys = [asset.storage_key]
    for variant in (asset.variants or {}).values():
        if isinstance(variant, dict) and variant.get('key'):
            keys.append(variant['key'])
    return [key for key in keys if key]


def format_size(num_bytes):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num_bytes < 1024:
            return f'{num_bytes:.0f} {unit}'
        num_bytes /= 1024
    return f'{num_bytes:.1f} TB'


class Command(BaseCommand):
    help = (
        'Remove abandoned, stuck and failed media uploads (and, with '
        '--include-unused, ready images no content uses). Run with --dry-run first.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be removed without deleting anything.')
        parser.add_argument('--stale-hours', type=int, default=24,
                            help='Abandoned uploads older than this many hours (default 24).')
        parser.add_argument('--failed-days', type=int, default=7,
                            help='Failed assets older than this many days (default 7).')
        parser.add_argument('--include-unused', action='store_true',
                            help='Also remove ready images that no blog or video uses.')
        parser.add_argument('--unused-days', type=int, default=30,
                            help='Only unused images older than this many days (default 30).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        groups = [
            (
                'Abandoned uploads',
                Media_asset.objects.filter(
                    status__in=[Status.PENDING, Status.UPLOADING],
                    created_at__lt=now - timedelta(hours=options['stale_hours']),
                ),
            ),
            (
                'Stuck processing',
                Media_asset.objects.filter(
                    status=Status.PROCESSING,
                    updated_at__lt=now - timedelta(hours=1),
                ),
            ),
            (
                'Failed uploads',
                Media_asset.objects.filter(
                    status=Status.FAILED,
                    updated_at__lt=now - timedelta(days=options['failed_days']),
                ),
            ),
        ]

        if options['include_unused']:
            groups.append((
                'Unused images',
                Media_asset.objects.filter(
                    status=Status.READY,
                    media_type=Media_asset.MediaType.IMAGE,
                    created_at__lt=now - timedelta(days=options['unused_days']),
                    **UNREFERENCED,
                ),
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run: nothing will be deleted.'))

        for label, queryset in groups:
            self._clean_group(label, queryset, dry_run)

    def _clean_group(self, label, queryset, dry_run):
        removed = 0
        total_bytes = 0
        keys_to_delete = []

        for asset in queryset.only('id', 'storage_key', 'variants', 'file_size').iterator():
            if dry_run:
                removed += 1
                total_bytes += asset.file_size or 0
                continue

            # Re-apply the group's conditions while deleting: if the asset changed
            # since the list was made (e.g. just attached to a blog), skip it.
            try:
                deleted_count, _ = queryset.filter(pk=asset.pk).delete()
            except ProtectedError:
                continue

            if deleted_count:
                removed += 1
                total_bytes += asset.file_size or 0
                keys_to_delete.extend(asset_keys(asset))

        # Rows first, files second: a failure here leaves harmless orphan files,
        # never a database row pointing at deleted files.
        if keys_to_delete:
            try:
                storage.delete_objects(keys_to_delete)
            except Exception as error:  # report, but the rows are already gone
                self.stdout.write(self.style.ERROR(
                    f'  {label}: could not delete {len(keys_to_delete)} file(s) from storage: {error}'
                ))

        verb = 'would be removed' if dry_run else 'removed'
        self.stdout.write(f'{label}: {removed} {verb} ({format_size(total_bytes)})')


        

