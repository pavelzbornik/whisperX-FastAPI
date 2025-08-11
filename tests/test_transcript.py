"""Tests for the transcript module."""

from unittest.mock import Mock

import pytest

from app.schemas import AlignedTranscription, AlignmentSegment, Word
from app.transcript import filter_aligned_transcription


class TestFilterAlignedTranscription:
    """Test cases for filter_aligned_transcription function."""

    def test_filter_aligned_transcription_all_complete_words(self):
        """Test filtering with all words having complete data."""
        # Create mock words with complete data
        word1 = Word(word="Hello", start=0.0, end=0.5, score=0.9, speaker=None)
        word2 = Word(word="world", start=0.6, end=1.0, score=0.8, speaker=None)
        word3 = Word(word="test", start=2.0, end=2.5, score=0.95, speaker=None)
        
        # Create segments with these words
        segment1 = AlignmentSegment(
            start=0.0,
            end=1.0,
            text="Hello world",
            words=[word1, word2]
        )
        
        segment2 = AlignmentSegment(
            start=2.0,
            end=2.5,
            text="test",
            words=[word3]
        )
        
        # Create aligned transcription
        transcription = AlignedTranscription(
            segments=[segment1, segment2],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # All segments should remain since all words are complete
        assert len(result.segments) == 2
        assert len(result.segments[0].words) == 2
        assert len(result.segments[1].words) == 1
        assert result.segments[0].text == "Hello world"
        assert result.segments[1].text == "test"

    def test_filter_aligned_transcription_with_incomplete_words(self):
        """Test filtering with some words having missing data."""
        # Create words with missing data
        complete_word = Word(word="Hello", start=0.0, end=0.5, score=0.9, speaker=None)
        missing_start = Word(word="world", start=None, end=1.0, score=0.8, speaker=None)
        missing_end = Word(word="test", start=2.0, end=None, score=0.95, speaker=None)
        missing_score = Word(word="data", start=3.0, end=3.5, score=None, speaker=None)
        complete_word2 = Word(word="good", start=4.0, end=4.5, score=0.85, speaker=None)
        
        # Create segment with mixed complete/incomplete words
        segment = AlignmentSegment(
            start=0.0,
            end=4.5,
            text="Hello world test data good",
            words=[complete_word, missing_start, missing_end, missing_score, complete_word2]
        )
        
        transcription = AlignedTranscription(
            segments=[segment],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # Only words with complete data should remain
        assert len(result.segments) == 1
        assert len(result.segments[0].words) == 2
        assert result.segments[0].words[0].word == "Hello"
        assert result.segments[0].words[1].word == "good"

    def test_filter_aligned_transcription_segment_with_no_valid_words(self):
        """Test filtering when a segment has no valid words."""
        # Create words all missing data
        missing_start = Word(word="word1", start=None, end=1.0, score=0.8, speaker=None)
        missing_end = Word(word="word2", start=2.0, end=None, score=0.95, speaker=None)
        missing_score = Word(word="word3", start=3.0, end=3.5, score=None, speaker=None)
        
        # Create valid word for another segment
        valid_word = Word(word="valid", start=5.0, end=5.5, score=0.9, speaker=None)
        
        segment1 = AlignmentSegment(
            start=0.0,
            end=4.0,
            text="word1 word2 word3",
            words=[missing_start, missing_end, missing_score]
        )
        
        segment2 = AlignmentSegment(
            start=5.0,
            end=5.5,
            text="valid",
            words=[valid_word]
        )
        
        transcription = AlignedTranscription(
            segments=[segment1, segment2],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # Only segment with valid words should remain
        assert len(result.segments) == 1
        assert result.segments[0].text == "valid"
        assert len(result.segments[0].words) == 1
        assert result.segments[0].words[0].word == "valid"

    def test_filter_aligned_transcription_empty_segments(self):
        """Test filtering with empty segments list."""
        transcription = AlignedTranscription(
            segments=[],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        assert len(result.segments) == 0
        assert len(result.word_segments) == 0

    def test_filter_aligned_transcription_preserves_segment_data(self):
        """Test that segment-level data is preserved during filtering."""
        valid_word = Word(word="test", start=1.0, end=2.0, score=0.9, speaker=None)
        
        segment = AlignmentSegment(
            start=0.5,
            end=2.5,
            text="Original text",
            words=[valid_word]
        )
        
        transcription = AlignedTranscription(
            segments=[segment],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # Verify segment data is preserved
        assert result.segments[0].start == 0.5
        assert result.segments[0].end == 2.5
        assert result.segments[0].text == "Original text"

    def test_filter_aligned_transcription_multiple_missing_attributes(self):
        """Test words missing multiple attributes."""
        # Word missing both start and score
        missing_multiple = Word(word="broken", start=None, end=1.0, score=None, speaker=None)
        # Word missing all three
        missing_all = Word(word="very_broken", start=None, end=None, score=None, speaker=None)
        # Complete word
        complete = Word(word="good", start=2.0, end=2.5, score=0.9, speaker=None)
        
        segment = AlignmentSegment(
            start=0.0,
            end=3.0,
            text="broken very_broken good",
            words=[missing_multiple, missing_all, complete]
        )
        
        transcription = AlignedTranscription(
            segments=[segment],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # Only the complete word should remain
        assert len(result.segments) == 1
        assert len(result.segments[0].words) == 1
        assert result.segments[0].words[0].word == "good"

    def test_filter_aligned_transcription_zero_values(self):
        """Test that zero values are considered valid (not None)."""
        # Words with zero values (which should be valid)
        zero_start = Word(word="start", start=0.0, end=1.0, score=0.9, speaker=None)
        zero_score = Word(word="score", start=1.0, end=2.0, score=0.0, speaker=None)
        zero_end = Word(word="end", start=2.0, end=0.0, score=0.8, speaker=None)  # Unusual but valid
        
        segment = AlignmentSegment(
            start=0.0,
            end=2.0,
            text="start score end",
            words=[zero_start, zero_score, zero_end]
        )
        
        transcription = AlignedTranscription(
            segments=[segment],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # All words should remain since zero is not None
        assert len(result.segments) == 1
        assert len(result.segments[0].words) == 3

    def test_filter_aligned_transcription_word_segments_empty(self):
        """Test that word_segments is always set to empty list."""
        valid_word = Word(word="test", start=1.0, end=2.0, score=0.9, speaker=None)
        segment = AlignmentSegment(
            start=1.0,
            end=2.0,
            text="test",
            words=[valid_word]
        )
        
        # Create transcription with proper word_segments structure
        transcription = AlignedTranscription(
            segments=[segment],
            word_segments=[]  # Keep this empty for the test
        )
        
        result = filter_aligned_transcription(transcription)
        
        # word_segments should always be empty list in result
        assert result.word_segments == []

    def test_filter_aligned_transcription_maintains_word_order(self):
        """Test that word order is maintained within segments."""
        words = [
            Word(word="First", start=0.0, end=0.5, score=0.9, speaker=None),
            Word(word="Second", start=0.6, end=1.0, score=0.8, speaker=None), 
            Word(word="Third", start=1.1, end=1.5, score=0.95, speaker=None),
        ]
        
        segment = AlignmentSegment(
            start=0.0,
            end=1.5,
            text="First Second Third",
            words=words
        )
        
        transcription = AlignedTranscription(
            segments=[segment],
            word_segments=[]
        )
        
        result = filter_aligned_transcription(transcription)
        
        # Word order should be maintained
        result_words = result.segments[0].words
        assert len(result_words) == 3
        assert result_words[0].word == "First"
        assert result_words[1].word == "Second"
        assert result_words[2].word == "Third"