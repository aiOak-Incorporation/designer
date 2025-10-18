import gzip
import io
import os
import re
import tempfile
from typing import Optional

from django.core.files.storage import default_storage
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Restore the database from a compressed JSON backup stored in default storage (S3 if configured)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            dest="input",
            default=None,
            help="Path in storage to the .json.gz backup. Defaults to latest in backups/.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            dest="noinput",
            help="Do not prompt for confirmation.",
        )

    def _find_latest_backup(self) -> Optional[str]:
        prefix = "backups"
        if not default_storage.exists(prefix):
            return None
        _, files = default_storage.listdir(prefix)
        candidates = [
            f"{prefix}/{name}" for name in files if re.match(r"db-\\d{8}-\\d{6}\\.json\\.gz$", name)
        ]
        if not candidates:
            return None
        # Sort lexicographically; timestamp ensures correct order
        candidates.sort()
        return candidates[-1]

    def handle(self, *args, **options):
        input_path = options.get("input") or self._find_latest_backup()
        if not input_path:
            self.stderr.write("No backup found. Provide --input or create a backup first.")
            return

        if not options.get("noinput"):
            confirm = input(
                f"This will import data from {input_path} and may overwrite existing records. Continue? [y/N]: "
            ).strip().lower()
            if confirm not in {"y", "yes"}:
                self.stdout.write("Aborted.")
                return

        if not default_storage.exists(input_path):
            self.stderr.write(f"Backup not found: {input_path}")
            return

        # Read and decompress
        with default_storage.open(input_path, "rb") as f:
            compressed = f.read()
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as gz:
            json_bytes = gz.read()

        # Write to a temporary file and delegate to loaddata
        with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tmp:
            tmp.write(json_bytes)
            temp_path = tmp.name

        try:
            call_command("loaddata", temp_path, verbosity=1)
            self.stdout.write(self.style.SUCCESS(f"Restore completed from {input_path}"))
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
