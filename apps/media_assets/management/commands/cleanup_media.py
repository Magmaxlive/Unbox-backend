from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.media_assets import storage, transcoding
from apps.media_assets.models import Media_asset
from apps.media_assets.services import refresh_video_processing

Status = Media_asset.Status
MediaType = Media_asset.MediaType

# Not referenced by any content (reverse relations of the foreign keys):
#   Blog.cover_image      -> related_name='blog_cover_image'
#   Video.thumbnail       -> related_name='video_thumbnails'
#   Video.media_asset     -> related_name='videos'
UNREFERENCED = {
    'blog_cover_image__isnull': True,
    'video_thumbnails__isnull': True,
    'videos__isnull': True,
}

STUCK_PROCESSING_HOURS = 1


def asset_keys(asset):
    """Every S3 key belonging to an asset: the original plus generated versions."""
    keys = [asset.storage_key]

    if asset.media_type == MediaType.VIDEO:
        # outputs live in a folder (MP4 + poster frames), plus a public copy if published
        prefix = transcoding.output_prefix(asset)
        keys.extend(storage.list_keys(prefix))
        keys.extend(storage.list_keys(f'public/{prefix}'))
    else:
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
        '--include-unused, ready images and videos no content uses). Run with --dry-run first.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be removed without deleting anything.')
        parser.add_argument('--stale-hours', type=int, default=24,
                            help='Abandoned uploads older than this many hours (default 24).')
        parser.add_argument('--failed-days', type=int, default=7,
                            help='Failed assets older than this many days (default 7).')
        parser.add_argument('--include-unused', action='store_true',
                            help='Also remove ready images and videos that no blog or video uses.')
        parser.add_argument('--unused-days', type=int, default=30,
                            help='Only unused assets older than this many days (default 30).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        stuck_cutoff = now - timedelta(hours=STUCK_PROCESSING_HOURS)

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run: nothing will be deleted.'))
            self.stdout.write(self.style.WARNING(
                '  (processing videos are not re-checked with MediaConvert in a dry run, '
                'so "Stuck processing" may include some that have actually finished)'
            ))
        else:
            # a video "stuck" in processing may simply have finished with nobody
            # looking: apply MediaConvert's real result before judging it stuck
            for asset in Media_asset.objects.filter(
                media_type=MediaType.VIDEO,
                status=Status.PROCESSING,
                updated_at__lt=stuck_cutoff,
            ):
                refresh_video_processing(asset, force=True)

        # (label, queryset, detach_from_videos)
        groups = [
            (
                'Abandoned uploads',
                Media_asset.objects.filter(
                    status__in=[Status.PENDING, Status.UPLOADING],
                    created_at__lt=now - timedelta(hours=options['stale_hours']),
                ),
                True,
            ),
            (
                'Stuck processing',
                Media_asset.objects.filter(
                    status=Status.PROCESSING,
                    updated_at__lt=stuck_cutoff,
                ),
                True,
            ),
            (
                'Failed uploads',
                Media_asset.objects.filter(
                    status=Status.FAILED,
                    updated_at__lt=now - timedelta(days=options['failed_days']),
                ),
                True,
            ),
        ]

        if options['include_unused']:
            unused_cutoff = now - timedelta(days=options['unused_days'])
            groups.append((
                'Unused images',
                Media_asset.objects.filter(
                    status=Status.READY,
                    media_type=MediaType.IMAGE,
                    created_at__lt=unused_cutoff,
                    **UNREFERENCED,
                ),
                False,
            ))
            groups.append((
                'Unused videos',
                Media_asset.objects.filter(
                    status=Status.READY,
                    media_type=MediaType.VIDEO,
                    created_at__lt=unused_cutoff,
                    **UNREFERENCED,
                ),
                False,
            ))

        for label, queryset, detach in groups:
            self._clean_group(label, queryset, dry_run, detach)

    def _clean_group(self, label, queryset, dry_run, detach_from_videos):
        from apps.videos.models import Video   # avoid importing videos at load time

        removed = 0
        total_bytes = 0
        removed_assets = []

        fields = ('id', 'storage_key', 'variants', 'file_size', 'media_type', 'created_at', 'multipart_upload_id')
        for asset in queryset.only(*fields).iterator():
            if dry_run:
                removed += 1
                total_bytes += asset.file_size or 0
                continue

            # Re-apply the group's conditions while deleting: if the asset changed
            # since the list was made (e.g. just attached to a blog), skip it.
            try:
                with transaction.atomic():
                    still_matches = queryset.filter(pk=asset.pk)
                    if not still_matches.exists():
                        continue

                    if detach_from_videos:
                        # an unfinished, stuck or failed file on a draft: detach it so it can
                        # be removed; the video then asks for a new upload before submitting
                        Video.objects.filter(media_asset_id=asset.pk).update(media_asset=None, duration=None)

                    deleted_count, _ = still_matches.delete()
            except ProtectedError:
                continue

            if deleted_count:
                removed += 1
                total_bytes += asset.file_size or 0
                removed_assets.append(asset)

        # Rows first, files second: a failure here leaves harmless orphan files,
        # never a database row pointing at deleted files.
        keys_to_delete = []
        for asset in removed_assets:
            # unfinished multipart uploads: discard the parts S3 is holding
            if asset.multipart_upload_id:
                try:
                    storage.abort_multipart_upload(asset.storage_key, asset.multipart_upload_id)
                except Exception as error:
                    self.stdout.write(self.style.ERROR(
                        f'  {label}: could not abort the upload for {asset.storage_key}: {error}'
                    ))
            try:
                keys_to_delete.extend(asset_keys(asset))
            except Exception as error:   # listing a video's folder failed
                self.stdout.write(self.style.ERROR(f'  {label}: could not list files for {asset.pk}: {error}'))
                keys_to_delete.append(asset.storage_key)

        if keys_to_delete:
            try:
                storage.delete_objects(keys_to_delete)
            except Exception as error:  # report, but the rows are already gone
                self.stdout.write(self.style.ERROR(
                    f'  {label}: could not delete {len(keys_to_delete)} file(s) from storage: {error}'
                ))

        verb = 'would be removed' if dry_run else 'removed'
        self.stdout.write(f'{label}: {removed} {verb} ({format_size(total_bytes)})')