# Flacfixer

As a first python project I made this CLI script.
It properly removes pictures, oversized padding and id3 tags from flac files.

Requirements:

    python 3.5 +
    mutagen library (pip install mutagen)


Features:

    much faster than metaflac
    works on single files and folders (also checks subfolders)
    works independent of file extension
    accepts multiple input paths


Options:

    check-only mode for diagnostics
    save pictures to disk (no dupes will be saved)
    customisable padding size
    don't remove pictures
    don't remove id3 tags
    silent mode
