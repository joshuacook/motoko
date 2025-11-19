"""Basic chat example with different models."""

from motoko import Message, MessageRole, create_model

# Example 1: Using Claude with factory
print("=== Example 1: Claude via Factory ===")
claude = create_model("claude-3-5-sonnet-20241022")

messages = [Message(role=MessageRole.USER, content="Say hello in 5 words or less")]

response = claude.chat(messages=messages, system="You are a helpful assistant")
print(f"Claude: {response.text}")
print(f"Usage: {response.usage}")
print()

# Example 2: Using Gemini with factory
print("=== Example 2: Gemini via Factory ===")
gemini = create_model("gemini-2.0-flash-exp")

messages = [Message(role=MessageRole.USER, content="Say hello in 5 words or less")]

response = gemini.chat(messages=messages, system="You are a helpful assistant")
print(f"Gemini: {response.text}")
print(f"Usage: {response.usage}")
print()

# Example 3: Direct import
print("=== Example 3: Direct Import ===")
from motoko import AnthropicModel

model = AnthropicModel("claude-3-5-haiku-20241022")

messages = [Message(role=MessageRole.USER, content="What is 2+2?")]

response = model.chat(messages=messages)
print(f"Response: {response.text}")
print()

# Example 4: Model switching
print("=== Example 4: Model Switching ===")


def ask_question(model_name: str, question: str) -> str:
    """Ask the same question to different models."""
    model = create_model(model_name)
    messages = [Message(role=MessageRole.USER, content=question)]
    response = model.chat(messages=messages)
    return response.text


question = "What is the capital of France?"
for model_name in ["claude-3-5-sonnet-20241022", "gemini-2.0-flash-exp"]:
    answer = ask_question(model_name, question)
    print(f"{model_name}: {answer}")
print()

# Example 5: With parameters
print("=== Example 5: With Parameters ===")
creative_model = create_model("claude-3-opus-20240229", temperature=1.5)
conservative_model = create_model("claude-3-opus-20240229", temperature=0.2)

messages = [Message(role=MessageRole.USER, content="Write a 3-word story")]

print(f"Creative: {creative_model.chat(messages=messages).text}")
print(f"Conservative: {conservative_model.chat(messages=messages).text}")
