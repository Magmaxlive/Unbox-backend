from django.core.management.base import BaseCommand

from apps.blogs.models import Blog
from apps.core.sanitize import sanitize_rich_text


class Command(BaseCommand):
    help = (
        'Re-run the rich-text sanitiser over existing blog content. '
        'Use after changing the allowlist, or to clean rows saved before '
        'sanitising existed (or written outside the API).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report how many blogs would change without saving anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        checked = 0
        changed = 0

        for blog in Blog.objects.only('id', 'title', 'content').iterator():
            checked += 1
            cleaned = sanitize_rich_text(blog.content)

            if cleaned != blog.content:
                changed += 1
                self.stdout.write(f'  {"would clean" if dry_run else "cleaned"}: {blog.title}')

                if not dry_run:
                    # update() skips auto_now and activity logging: this is a
                    # maintenance fix, not a content edit by a user.
                    Blog.objects.filter(pk=blog.pk).update(content=cleaned)

        verb = 'would change' if dry_run else 'changed'
        self.stdout.write(self.style.SUCCESS(f'Checked {checked} blogs, {verb} {changed}.'))