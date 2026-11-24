from django.core.management.base import BaseCommand

from apps.media_assets.models import Media_asset
from apps.media_assets.services import refresh_video_processing


class Command(BaseCommand):
    help = 'Check all processing videos with MediaConvert and apply finished results.'

    def handle(self, *args, **options):
        assets = Media_asset.objects.filter(
            media_type=Media_asset.MediaType.VIDEO,
            status=Media_asset.Status.PROCESSING,
        )

        counts = {'ready': 0, 'failed': 0, 'processing': 0}
        for asset in assets:
            refresh_video_processing(asset, force=True)
            counts[asset.status] = counts.get(asset.status, 0) + 1

        self.stdout.write(
            f"Checked {sum(counts.values())} video(s): "
            f"{counts['ready']} ready, {counts['failed']} failed, {counts['processing']} still processing."
        )


