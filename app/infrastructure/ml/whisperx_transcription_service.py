"""WhisperX implementation of transcription service."""

import gc
import time
from typing import Any

import numpy as np
import torch
from opentelemetry.trace import Status, StatusCode
from whisperx import load_model

from app.core.logging import logger
from app.observability.metrics import get_metrics
from app.observability.tracing import get_tracer

# Get tracer and metrics
tracer = get_tracer(__name__)
metrics = get_metrics()


class WhisperXTranscriptionService:
    """
    WhisperX-based implementation of transcription service.

    This service wraps the WhisperX library to provide transcription
    functionality following the ITranscriptionService interface contract.
    """

    def __init__(self) -> None:
        """Initialize the transcription service."""
        self.model: Any = None
        self.logger = logger

    def transcribe(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        task: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        batch_size: int,
        chunk_size: int,
        model: str,
        device: str,
        device_index: int,
        compute_type: str,
        threads: int,
    ) -> dict[str, Any]:
        """
        Transcribe audio using WhisperX model with OpenTelemetry tracing.

        Args:
            audio: Audio data as numpy array (float32)
            task: Transcription task type ('transcribe' or 'translate')
            asr_options: ASR model options
            vad_options: Voice Activity Detection options
            language: Language code for transcription
            batch_size: Batch size for processing
            chunk_size: Chunk size for processing
            model: Model name/size to use
            device: Device to use ('cpu' or 'cuda')
            device_index: Device index for multi-GPU setups
            compute_type: Computation precision ('float16', 'int8', etc.)
            threads: Number of threads to use

        Returns:
            Dictionary containing transcription results
        """
        with tracer.start_as_current_span(
            "ml.transcribe",
            attributes={
                "ml.model": model,
                "ml.language": language,
                "ml.device": device,
                "ml.compute_type": compute_type,
                "ml.batch_size": batch_size,
                "ml.task": task,
            },
        ) as span:
            try:
                start_time = time.time()

                self.logger.debug(
                    "Starting transcription with Whisper model: %s on device: %s",
                    model,
                    device,
                )

                # Log GPU memory before loading model
                if torch.cuda.is_available():
                    gpu_mem_before = torch.cuda.memory_allocated() / 1024**2
                    self.logger.debug(
                        f"GPU memory before loading model - used: {gpu_mem_before:.2f} MB, "
                        f"available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
                    )
                    span.set_attribute("gpu.memory_before_mb", gpu_mem_before)

                # Set thread count
                faster_whisper_threads = 4
                if threads > 0:
                    torch.set_num_threads(threads)
                    faster_whisper_threads = threads

                self.logger.debug(
                    "Loading model with config - model: %s, device: %s, compute_type: %s, "
                    "threads: %d, task: %s, language: %s",
                    model,
                    device,
                    compute_type,
                    faster_whisper_threads,
                    task,
                    language,
                )

                # Load model
                model_load_start = time.time()
                span.add_event("model_loading_started", {"model_name": model})

                loaded_model = load_model(
                    model,
                    device,
                    device_index=device_index,
                    compute_type=compute_type,
                    asr_options=asr_options,
                    vad_options=vad_options,
                    language=language,
                    task=task,
                    threads=faster_whisper_threads,
                )

                model_load_duration = time.time() - model_load_start
                span.add_event(
                    "model_loaded",
                    {
                        "model_name": model,
                        "load_duration_seconds": model_load_duration,
                    },
                )
                span.set_attribute(
                    "ml.model_load_duration_seconds", model_load_duration
                )

                # Record model load metric
                metrics.ml_model_loads_total.add(1, {"model_name": model})

                self.logger.debug("Transcription model loaded successfully")

                # Transcribe
                inference_start = time.time()
                span.add_event("transcription_started")

                result = loaded_model.transcribe(
                    audio=audio,
                    batch_size=batch_size,
                    chunk_size=chunk_size,
                    language=language,
                )

                inference_duration = time.time() - inference_start
                span.add_event(
                    "transcription_completed",
                    {"inference_duration_seconds": inference_duration},
                )
                span.set_attribute("ml.inference_duration_seconds", inference_duration)

                # Record inference metric
                metrics.ml_inference_duration_seconds.record(
                    inference_duration, {"operation": "transcribe", "model": model}
                )

                # Add result attributes
                if isinstance(result, dict) and "segments" in result:
                    segment_count = len(result.get("segments", []))
                    span.set_attribute("ml.segments_count", segment_count)

                # Log GPU memory before cleanup
                if torch.cuda.is_available():
                    gpu_mem_after = torch.cuda.memory_allocated() / 1024**2
                    self.logger.debug(
                        f"GPU memory before cleanup: {gpu_mem_after:.2f} MB, "
                        f"available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
                    )
                    span.set_attribute("gpu.memory_after_mb", gpu_mem_after)

                # Clean up model
                gc.collect()
                torch.cuda.empty_cache()
                del loaded_model

                # Log GPU memory after cleanup
                if torch.cuda.is_available():
                    gpu_mem_cleaned = torch.cuda.memory_allocated() / 1024**2
                    self.logger.debug(
                        f"GPU memory after cleanup: {gpu_mem_cleaned:.2f} MB, "
                        f"available: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.2f} MB"
                    )

                total_duration = time.time() - start_time
                span.set_attribute("ml.total_duration_seconds", total_duration)
                span.set_status(Status(StatusCode.OK))

                self.logger.debug("Completed transcription")
                return result  # type: ignore[no-any-return]

            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def load_model(
        self,
        model_name: str,
        device: str,
        device_index: int,
        compute_type: str,
        asr_options: dict[str, Any],
        vad_options: dict[str, Any],
        language: str,
        task: str,
        threads: int,
    ) -> None:
        """
        Load WhisperX model.

        Args:
            model_name: Name/size of the model to load
            device: Device to load model on ('cpu' or 'cuda')
            device_index: Device index for multi-GPU setups
            compute_type: Computation precision
            asr_options: ASR model options
            vad_options: Voice Activity Detection options
            language: Target language
            task: Task type
            threads: Number of threads to use
        """
        self.logger.info(f"Loading model {model_name} on {device}")

        faster_whisper_threads = 4
        if threads > 0:
            torch.set_num_threads(threads)
            faster_whisper_threads = threads

        self.model = load_model(
            model_name,
            device,
            device_index=device_index,
            compute_type=compute_type,
            asr_options=asr_options,
            vad_options=vad_options,
            language=language,
            task=task,
            threads=faster_whisper_threads,
        )

    def unload_model(self) -> None:
        """Unload WhisperX model and free GPU memory."""
        if self.model:
            del self.model
            self.model = None
            gc.collect()
            torch.cuda.empty_cache()
            self.logger.debug("Model unloaded and GPU memory cleared")
