"""This module provides functions to filter aligned transcriptions."""

from .schemas import AlignedTranscription, AlignmentSegment


def filter_aligned_transcription(
    aligned_transcription: AlignedTranscription,
) -> AlignedTranscription:
    """
    Filter an AlignedTranscription instance by removing words within each segment that have missing start, end, or score values.

    Args:
        aligned_transcription (AlignedTranscription): The AlignedTranscription instance to filter.

    Returns:
        AlignedTranscription: Filtered AlignedTranscription instance.
    """
    filtered_segments = []
    for segment in aligned_transcription.segments:
        filtered_words = [
            word
            for word in segment.words
            if all(
                [
                    word.start is not None,
                    word.end is not None,
                    word.score is not None,
                ]
            )
        ]
        if filtered_words:
            filtered_segment = AlignmentSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                words=filtered_words,
            )
            filtered_segments.append(filtered_segment)
    filtered_transcription = AlignedTranscription(
        segments=filtered_segments, word_segments=[]
    )
    return filtered_transcription
