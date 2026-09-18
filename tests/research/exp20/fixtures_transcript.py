"""Fixed timestamped transcript fixtures for EXP-20 Step 2."""

from .transcript_adapter import TranscriptObservation

FIXTURES = (
    TranscriptObservation(
        source_ref="fixture:transcript:001",
        raw_text=(
            "00:00:01.000 --> 00:00:03.500  Hello, world!  \n"
            "00:00:03.500 --> 00:00:05.000  This is the first segment.\n"
            "00:00:05.000 --> 00:00:07.250  Café au lait.\n"
        ),
        metadata={"fixture": "exp20", "kind": "timestamped_transcript"},
    ),
)
