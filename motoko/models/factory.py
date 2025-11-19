"""Model factory for easy model instantiation."""

from typing import Any

from .anthropic import AnthropicModel
from .base import BaseModel
from .gemini import GeminiModel


class ModelFactory:
    """Factory for creating model instances by name.

    Supports automatic detection of provider from model name.
    """

    # Model name prefixes for provider detection
    ANTHROPIC_MODELS = [
        "claude-sonnet-4",  # Sonnet 4.5 (latest)
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "claude-2",
        "claude-instant",
    ]

    GEMINI_MODELS = [
        "gemini-3",  # Gemini 3 Pro (latest)
        "gemini-2.0",
        "gemini-1.5",
        "gemini-1.0",
        "gemini-pro",
        "gemini-flash",
    ]

    @classmethod
    def create(
        cls, model_name: str, api_key: str | None = None, **kwargs: Any
    ) -> BaseModel:
        """Create a model instance from model name.

        Auto-detects provider from model name.

        Args:
            model_name: Model name (e.g., "claude-3-5-sonnet", "gemini-2.0-flash")
            api_key: API key (if None, uses environment variable)
            **kwargs: Additional model-specific parameters

        Returns:
            Model instance

        Raises:
            ValueError: If model provider cannot be determined

        Examples:
            >>> model = ModelFactory.create("claude-3-5-sonnet-20241022")
            >>> model = ModelFactory.create("gemini-2.0-flash-exp")
            >>> model = ModelFactory.create("claude-3-opus", temperature=0.7)
        """
        # Detect provider
        if any(model_name.startswith(prefix) for prefix in cls.ANTHROPIC_MODELS):
            return AnthropicModel(model_name=model_name, api_key=api_key, **kwargs)

        elif any(model_name.startswith(prefix) for prefix in cls.GEMINI_MODELS):
            return GeminiModel(model_name=model_name, api_key=api_key, **kwargs)

        else:
            raise ValueError(
                f"Unknown model: {model_name}. "
                f"Supported prefixes: {cls.ANTHROPIC_MODELS + cls.GEMINI_MODELS}"
            )

    @classmethod
    def create_anthropic(
        cls, model_name: str = "claude-sonnet-4-5-20250929", **kwargs: Any
    ) -> AnthropicModel:
        """Create Anthropic Claude model.

        Args:
            model_name: Claude model name
            **kwargs: Additional parameters

        Returns:
            AnthropicModel instance
        """
        return AnthropicModel(model_name=model_name, **kwargs)

    @classmethod
    def create_gemini(
        cls, model_name: str = "gemini-3-pro-preview", **kwargs: Any
    ) -> GeminiModel:
        """Create Google Gemini model.

        Args:
            model_name: Gemini model name
            **kwargs: Additional parameters

        Returns:
            GeminiModel instance
        """
        return GeminiModel(model_name=model_name, **kwargs)


# Convenience function
def create_model(model_name: str, **kwargs: Any) -> BaseModel:
    """Create a model instance from model name.

    Convenience function for ModelFactory.create().

    Args:
        model_name: Model name
        **kwargs: Additional parameters

    Returns:
        Model instance

    Examples:
        >>> model = create_model("claude-3-5-sonnet")
        >>> model = create_model("gemini-2.0-flash", temperature=0.5)
    """
    return ModelFactory.create(model_name, **kwargs)
